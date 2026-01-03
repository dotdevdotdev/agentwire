"""
AgentWire WebSocket server.

Multi-room voice web interface for AI coding agents.
"""

import asyncio
import base64
import io
import json
import logging
import re
import shutil
import ssl
import struct
import tempfile
import time
import uuid
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import Config, load_config
from .templates import get_template
from .worktree import ensure_worktree, get_project_type, get_session_path, parse_session_name, remove_worktree

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


@dataclass
class RoomConfig:
    """Runtime configuration for a room."""

    voice: str = "default"
    exaggeration: float = 0.5
    cfg_weight: float = 0.5
    machine: str | None = None
    path: str | None = None
    claude_session_id: str | None = None  # Claude Code session UUID for forking
    bypass_permissions: bool = True  # Default True for backwards compat with existing sessions


@dataclass
class PendingPermission:
    """A permission request waiting for user decision."""

    request: dict  # The permission request from Claude Code
    event: asyncio.Event = field(default_factory=asyncio.Event)  # Signals when user responds
    decision: dict | None = None  # The user's decision


@dataclass
class Room:
    """Active room with connected clients."""

    name: str
    config: RoomConfig
    clients: set = field(default_factory=set)
    locked_by: str | None = None
    last_output: str = ""
    output_task: asyncio.Task | None = None
    played_says: set = field(default_factory=set)
    last_question: str | None = None  # Track AskUserQuestion to avoid duplicates
    pending_permission: PendingPermission | None = None  # Active permission request


class AgentWireServer:
    """Main server managing rooms, WebSockets, and agent sessions."""

    def __init__(self, config: Config):
        self.config = config
        self.rooms: dict[str, Room] = {}
        self.tts = None
        self.stt = None
        self.agent = None
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Configure HTTP and WebSocket routes."""
        self.app.router.add_get("/", self.handle_dashboard)
        self.app.router.add_get("/room/{name:.+}", self.handle_room)
        self.app.router.add_get("/ws/{name:.+}", self.handle_websocket)
        self.app.router.add_get("/api/sessions", self.api_sessions)
        self.app.router.add_post("/api/create", self.api_create_session)
        self.app.router.add_post("/api/room/{name:.+}/config", self.api_room_config)
        self.app.router.add_post("/transcribe", self.handle_transcribe)
        self.app.router.add_post("/upload", self.handle_upload)
        self.app.router.add_post("/send/{name:.+}", self.handle_send)
        self.app.router.add_post("/api/say/{name:.+}", self.api_say)
        self.app.router.add_post("/api/answer/{name:.+}", self.api_answer)
        self.app.router.add_post("/api/room/{name:.+}/recreate", self.api_recreate_session)
        self.app.router.add_post("/api/room/{name:.+}/spawn-sibling", self.api_spawn_sibling)
        self.app.router.add_post("/api/room/{name:.+}/fork", self.api_fork_session)
        self.app.router.add_post("/api/room/{name:.+}/restart-service", self.api_restart_service)
        self.app.router.add_get("/api/voices", self.api_voices)
        self.app.router.add_delete("/api/sessions/{name:.+}", self.api_close_session)
        self.app.router.add_get("/api/sessions/archive", self.api_archived_sessions)
        self.app.router.add_get("/api/machines", self.api_machines)
        self.app.router.add_post("/api/machines", self.api_add_machine)
        self.app.router.add_delete("/api/machines/{machine_id}", self.api_remove_machine)
        self.app.router.add_get("/api/config", self.api_get_config)
        self.app.router.add_post("/api/config", self.api_save_config)
        self.app.router.add_post("/api/config/reload", self.api_reload_config)
        # Permission request handling (from Claude Code hook)
        # Note: respond route must come first as aiohttp matches in order
        self.app.router.add_post("/api/permission/{name:.+}/respond", self.api_permission_respond)
        self.app.router.add_post("/api/permission/{name:.+}", self.api_permission_request)
        self.app.router.add_static("/static", Path(__file__).parent / "static")

    async def init_backends(self):
        """Initialize TTS, STT, and agent backends."""
        # Convert config to dict for backend factories
        config_dict = {
            "tts": {
                "backend": self.config.tts.backend,
                "url": self.config.tts.url,
            },
            "stt": {
                "backend": self.config.stt.backend,
                "model_path": str(self.config.stt.model_path)
                if self.config.stt.model_path
                else None,
                "language": self.config.stt.language,
            },
            "agent": {
                "command": self.config.agent.command,
            },
            "machines": {
                "file": str(self.config.machines.file),
            },
            "projects": {
                "dir": str(self.config.projects.dir),
            },
        }

        # Import and initialize backends
        from .agents import get_agent_backend
        from .stt import get_stt_backend
        from .tts import get_tts_backend

        self.tts = get_tts_backend(config_dict)
        try:
            self.stt = get_stt_backend(self.config)
        except ValueError as e:
            logger.warning(f"STT backend not available: {e}")
            from .stt import NoSTT

            self.stt = NoSTT()
        self.agent = get_agent_backend(config_dict)

        logger.info(f"TTS backend: {type(self.tts).__name__}")
        logger.info(f"STT backend: {type(self.stt).__name__}")

    async def close_backends(self):
        """Clean up backend resources."""
        if self.tts:
            await self.tts.close()

    async def cleanup_old_uploads(self):
        """Delete uploads older than cleanup_days."""
        uploads_dir = self.config.uploads.dir
        cleanup_days = self.config.uploads.cleanup_days

        if cleanup_days <= 0 or not uploads_dir.exists():
            return

        cutoff = time.time() - (cleanup_days * 86400)
        cleaned = 0

        for f in uploads_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"Failed to clean up {f}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old upload(s)")

    def _load_room_configs(self) -> dict[str, dict]:
        """Load room configurations from file."""
        rooms_file = self.config.rooms.file
        if rooms_file.exists():
            try:
                with open(rooms_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load rooms config: {e}")
        return {}

    def _save_room_configs(self, configs: dict[str, dict]):
        """Save room configurations to file."""
        rooms_file = self.config.rooms.file
        rooms_file.parent.mkdir(parents=True, exist_ok=True)
        with open(rooms_file, "w") as f:
            json.dump(configs, f, indent=2)

    def _get_room_config(self, name: str) -> RoomConfig:
        """Get or create room configuration."""
        configs = self._load_room_configs()
        if name in configs:
            cfg = configs[name]
            return RoomConfig(
                voice=cfg.get("voice", self.config.tts.default_voice),
                exaggeration=cfg.get("exaggeration", 0.5),
                cfg_weight=cfg.get("cfg_weight", 0.5),
                machine=cfg.get("machine"),
                path=cfg.get("path"),
                claude_session_id=cfg.get("claude_session_id"),
                bypass_permissions=cfg.get("bypass_permissions", True),  # Default True
            )
        return RoomConfig(voice=self.config.tts.default_voice)

    async def _get_voices(self) -> list[str]:
        """Get available TTS voices."""
        if self.tts:
            try:
                return await self.tts.get_voices()
            except Exception:
                pass
        return [self.config.tts.default_voice]

    def _render_template(self, name: str, **kwargs) -> str:
        """Render a template with Jinja2-style variable substitution."""
        template = get_template(name)

        # Handle {% for %} loops
        for_pattern = r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}"
        while True:
            match = re.search(for_pattern, template, re.DOTALL)
            if not match:
                break
            var_name = match.group(1)
            list_name = match.group(2)
            body = match.group(3)
            items = kwargs.get(list_name, [])
            result = ""
            for item in items:
                item_body = body
                # Replace {{ var }}
                item_body = item_body.replace("{{ " + var_name + " }}", str(item))
                # Handle {% if var == value %}
                if_pattern = (
                    r"\{%\s*if\s+"
                    + var_name
                    + r"\s*==\s*(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}"
                )
                for if_match in re.finditer(if_pattern, item_body, re.DOTALL):
                    compare_var = if_match.group(1)
                    compare_val = kwargs.get(compare_var, compare_var)
                    if_body = if_match.group(2)
                    if str(item) == str(compare_val):
                        item_body = item_body.replace(if_match.group(0), if_body)
                    else:
                        item_body = item_body.replace(if_match.group(0), "")
                result += item_body
            template = template[: match.start()] + result + template[match.end() :]

        # Handle {% if %} conditionals
        if_pattern = r"\{%\s*if\s+(.+?)\s*%\}(.*?)\{%\s*endif\s*%\}"
        while True:
            match = re.search(if_pattern, template, re.DOTALL)
            if not match:
                break
            condition = match.group(1)
            body = match.group(2)
            # Simple condition evaluation
            try:
                # Handle config.attr style
                if "." in condition:
                    parts = condition.split(".")
                    obj = kwargs.get(parts[0])
                    for part in parts[1:]:
                        obj = getattr(obj, part, None) if obj else None
                    result = body if obj else ""
                else:
                    result = body if kwargs.get(condition) else ""
            except Exception:
                result = ""
            template = template[: match.start()] + result + template[match.end() :]

        # Replace {{ var }} placeholders
        for key, value in kwargs.items():
            template = template.replace("{{ " + key + " }}", str(value))
            # Handle object attributes
            if hasattr(value, "__dict__"):
                for attr, attr_val in vars(value).items():
                    template = template.replace(
                        "{{ " + key + "." + attr + " }}", str(attr_val or "")
                    )

        return template

    # HTTP Handlers

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        """Serve the dashboard page."""
        voices = await self._get_voices()
        html = self._render_template(
            "dashboard.html",
            version=__version__,
            voices=voices,
            default_voice=self.config.tts.default_voice,
        )
        return web.Response(
            text=html,
            content_type="text/html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    # System sessions that get special treatment (restart instead of fork/new/recreate)
    SYSTEM_SESSIONS = {"agentwire", "agentwire-portal", "agentwire-tts"}

    def _is_system_session(self, name: str) -> bool:
        """Check if this is a system session (agentwire services)."""
        # Extract base session name (without @machine suffix)
        base_name = name.split("@")[0]
        return base_name in self.SYSTEM_SESSIONS

    async def handle_room(self, request: web.Request) -> web.Response:
        """Serve a room page."""
        name = request.match_info["name"]
        room_config = self._get_room_config(name)
        voices = await self._get_voices()
        is_system_session = self._is_system_session(name)

        html = self._render_template(
            "room.html",
            room_name=name,
            config=room_config,
            voices=voices,
            current_voice=room_config.voice,
            is_system_session=is_system_session,
            is_project_session=not is_system_session,
            is_system_session_js="true" if is_system_session else "false",
        )
        return web.Response(
            text=html,
            content_type="text/html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for a room."""
        name = request.match_info["name"]
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Get or create room
        if name not in self.rooms:
            self.rooms[name] = Room(name=name, config=self._get_room_config(name))

        room = self.rooms[name]
        client_id = str(id(ws))
        room.clients.add(ws)
        logger.info(f"[{name}] Client connected (total: {len(room.clients)})")

        # Send current output immediately on connect
        try:
            output = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.agent.get_output(name, lines=100)
            )
            if output:
                room.last_output = output
                await ws.send_json({"type": "output", "data": output})
        except Exception as e:
            logger.debug(f"Initial output fetch failed for {name}: {e}")

        # Start output polling if not running
        if room.output_task is None or room.output_task.done():
            room.output_task = asyncio.create_task(self._poll_output(room))

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_ws_message(room, ws, client_id, data)
                    except json.JSONDecodeError:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            room.clients.discard(ws)
            if room.locked_by == client_id:
                room.locked_by = None
                await self._broadcast(room, {"type": "room_unlocked"})

        return ws

    async def _handle_ws_message(
        self, room: Room, ws: web.WebSocketResponse, client_id: str, data: dict
    ):
        """Handle incoming WebSocket messages."""
        msg_type = data.get("type")

        if msg_type == "recording_started":
            # Try to lock the room
            if room.locked_by is None:
                room.locked_by = client_id
                # Notify others
                for client in room.clients:
                    if client != ws:
                        try:
                            await client.send_json({"type": "room_locked"})
                        except Exception:
                            pass

        elif msg_type == "recording_stopped":
            # Unlock will happen after TTS completes or on disconnect
            pass

    # Patterns for say command detection
    SAY_PATTERN = re.compile(r'(?:remote-)?say\s+(?:"([^"]+)"|\'([^\']+)\')', re.IGNORECASE)
    ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*m|\x1b\].*?\x07')

    # Pattern to detect AskUserQuestion UI blocks
    # Format: ☐ Header\n\nQuestion?\n\n❯ 1. Label\n     Description\n  2. Label...
    ASK_PATTERN = re.compile(
        r'\s*☐\s+(.+?)\s*\n\s*\n'  # ☐ Header
        r'(.+?\?)\s*\n'            # Question text ending with ?
        r'\s*\n'                   # Blank line
        r'((?:[❯\s]+\d+\.\s+.+\n(?:\s{3,}.+\n)?)+)',  # Options block
        re.MULTILINE
    )

    def _parse_ask_options(self, options_block: str) -> list[dict]:
        """Parse numbered options from AskUserQuestion block."""
        options = []
        current_option = None

        for line in options_block.split('\n'):
            line = self.ANSI_PATTERN.sub('', line)
            option_match = re.match(r'[❯\s]*(\d+)\.\s+(.+)', line)
            if option_match:
                if current_option:
                    options.append(current_option)
                current_option = {
                    'number': int(option_match.group(1)),
                    'label': option_match.group(2).strip(),
                    'description': '',
                }
            elif current_option and line.strip():
                current_option['description'] = line.strip()

        if current_option:
            options.append(current_option)

        return options

    async def _poll_output(self, room: Room):
        """Poll agent output and broadcast to room clients."""
        while room.clients:
            try:
                # Run sync get_output in thread pool to avoid blocking
                output = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.agent.get_output(room.name, lines=100)
                )
                if output != room.last_output:
                    old_output = room.last_output
                    room.last_output = output
                    await self._broadcast(room, {"type": "output", "data": output})

                    # Notify clients that agent is actively working
                    if old_output:  # Skip first poll
                        await self._broadcast(room, {"type": "activity"})

                    # Detect say commands in NEW content only
                    # If output doesn't start with old_output (terminal scrolled),
                    # skip say detection to avoid re-playing old commands
                    if old_output and output.startswith(old_output):
                        new_content = output[len(old_output):]
                    elif not old_output:
                        # First poll - don't play historical say commands
                        new_content = ""
                    else:
                        # Terminal scrolled/changed - skip to avoid duplicates
                        new_content = ""

                    for match in self.SAY_PATTERN.finditer(new_content):
                        say_text = match.group(1) or match.group(2)
                        if not say_text:
                            continue
                        # Strip ANSI codes
                        say_text = self.ANSI_PATTERN.sub('', say_text).strip()

                        # Skip if empty or already played
                        if not say_text or say_text in room.played_says:
                            continue

                        room.played_says.add(say_text)

                        # Keep played_says from growing indefinitely (as list for order)
                        if len(room.played_says) > 100:
                            # Convert to list, keep last 50, convert back
                            room.played_says = set(list(room.played_says)[-50:])

                        logger.info(f"[{room.name}] TTS: {say_text[:50]}...")

                        # Generate and broadcast TTS
                        await self._say_to_room(room.name, say_text)

                # Detect AskUserQuestion blocks (check full output - questions persist)
                clean_output = self.ANSI_PATTERN.sub('', output)
                ask_match = self.ASK_PATTERN.search(clean_output)

                if ask_match:
                    header = ask_match.group(1)
                    question = ask_match.group(2).strip()
                    options_block = ask_match.group(3)
                    options = self._parse_ask_options(options_block)

                    question_key = f"{header}:{question}"

                    if question_key != room.last_question and options:
                        room.last_question = question_key
                        logger.info(f"[{room.name}] Question: {question[:50]}...")

                        await self._broadcast(room, {
                            "type": "question",
                            "header": header,
                            "question": question,
                            "options": options,
                        })

                elif room.last_question and not ask_match:
                    # Question was answered (UI disappeared)
                    room.last_question = None
                    await self._broadcast(room, {"type": "question_answered"})

            except Exception as e:
                logger.debug(f"Output poll error for {room.name}: {e}")

            await asyncio.sleep(0.5)

    async def _broadcast(self, room: Room, message: dict):
        """Broadcast message to all room clients."""
        dead_clients = set()
        for client in room.clients:
            try:
                await client.send_json(message)
            except Exception:
                dead_clients.add(client)
        room.clients -= dead_clients

    # API Handlers

    async def api_sessions(self, request: web.Request) -> web.Response:
        """List all active sessions."""
        try:
            sessions = self.agent.list_sessions()
            room_configs = self._load_room_configs()

            result = []
            for name in sessions:
                project, branch, machine = parse_session_name(name)

                # Get path for session
                if branch:
                    path = get_session_path(
                        name,
                        self.config.projects.dir,
                        self.config.projects.worktrees.suffix,
                    )
                else:
                    path = self.config.projects.dir / project

                config = room_configs.get(name, {})
                result.append(
                    {
                        "name": name,
                        "path": str(path),
                        "machine": machine,
                        "voice": config.get("voice", self.config.tts.default_voice),
                        "type": get_project_type(path) if path.exists() else "scratch",
                    }
                )

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return web.json_response([])

    async def api_create_session(self, request: web.Request) -> web.Response:
        """Create a new agent session."""
        try:
            data = await request.json()
            name = data.get("name", "").strip()
            custom_path = data.get("path")
            voice = data.get("voice", self.config.tts.default_voice)
            bypass_permissions = data.get("bypass_permissions", True)  # Default True

            if not name:
                return web.json_response({"error": "Session name is required"})

            # Parse session name
            project, branch, machine = parse_session_name(name)

            # Determine working directory
            if custom_path:
                work_dir = Path(custom_path).expanduser()
            elif branch and self.config.projects.worktrees.enabled:
                work_dir = get_session_path(
                    name,
                    self.config.projects.dir,
                    self.config.projects.worktrees.suffix,
                )
                # Ensure worktree exists
                project_path = self.config.projects.dir / project
                if not ensure_worktree(
                    project_path,
                    branch,
                    work_dir,
                    self.config.projects.worktrees.auto_create_branch,
                ):
                    return web.json_response({
                        "error": f"Failed to create worktree. Is '{project}' a git repo?"
                    })
            else:
                work_dir = self.config.projects.dir / project

            # Generate Claude session ID for tracking/forking
            claude_session_id = str(uuid.uuid4())

            # Create session with session ID and bypass_permissions
            success = self.agent.create_session(
                name, str(work_dir),
                options={
                    "session_id": claude_session_id,
                    "bypass_permissions": bypass_permissions,
                    "room_name": name,  # Pass room name for AGENTWIRE_ROOM env var
                }
            )
            if not success:
                return web.json_response({"error": "Failed to create session"})

            # Save room config with Claude session ID and bypass_permissions
            configs = self._load_room_configs()
            configs[name] = {
                "voice": voice,
                "claude_session_id": claude_session_id,
                "bypass_permissions": bypass_permissions,
            }
            if custom_path:
                configs[name]["path"] = custom_path
            self._save_room_configs(configs)

            return web.json_response({"success": True, "name": name})

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return web.json_response({"error": str(e)})

    def _load_archive(self) -> list[dict]:
        """Load archived sessions from file."""
        archive_file = Path.home() / ".agentwire" / "archive.json"
        if archive_file.exists():
            try:
                with open(archive_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_archive(self, archive: list[dict]):
        """Save archived sessions to file."""
        archive_file = Path.home() / ".agentwire" / "archive.json"
        archive_file.parent.mkdir(parents=True, exist_ok=True)
        with open(archive_file, "w") as f:
            json.dump(archive, f, indent=2)

    async def api_close_session(self, request: web.Request) -> web.Response:
        """Close/kill a session and archive it."""
        name = request.match_info["name"]
        try:
            # Get session info before closing
            room_configs = self._load_room_configs()
            session_config = room_configs.get(name, {})

            project, branch, machine = parse_session_name(name)
            if branch:
                path = get_session_path(
                    name,
                    self.config.projects.dir,
                    self.config.projects.worktrees.suffix,
                )
            else:
                path = self.config.projects.dir / project

            # Kill the tmux session
            success = self.agent.kill_session(name)
            if not success:
                return web.json_response({"error": "Failed to close session"})

            # Archive the session
            import time
            archive = self._load_archive()
            archive.insert(0, {
                "name": name,
                "path": str(path),
                "machine": machine,
                "voice": session_config.get("voice", self.config.tts.default_voice),
                "closed_at": int(time.time()),
            })
            # Keep last 50 archived sessions
            archive = archive[:50]
            self._save_archive(archive)

            # Clean up room if exists
            if name in self.rooms:
                room = self.rooms[name]
                if room.output_task:
                    room.output_task.cancel()
                del self.rooms[name]

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Failed to close session: {e}")
            return web.json_response({"error": str(e)})

    async def api_archived_sessions(self, request: web.Request) -> web.Response:
        """Get list of archived sessions."""
        archive = self._load_archive()
        return web.json_response(archive)

    async def api_room_config(self, request: web.Request) -> web.Response:
        """Update room configuration."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            configs = self._load_room_configs()

            if name not in configs:
                configs[name] = {}

            for key in ["voice", "exaggeration", "cfg_weight"]:
                if key in data:
                    configs[name][key] = data[key]

            self._save_room_configs(configs)

            # Update live room if exists
            if name in self.rooms:
                room = self.rooms[name]
                if "voice" in data:
                    room.config.voice = data["voice"]
                if "exaggeration" in data:
                    room.config.exaggeration = data["exaggeration"]
                if "cfg_weight" in data:
                    room.config.cfg_weight = data["cfg_weight"]

            return web.json_response({"success": True})
        except Exception as e:
            return web.json_response({"error": str(e)})

    async def api_voices(self, request: web.Request) -> web.Response:
        """Get available TTS voices."""
        voices = await self._get_voices()
        return web.json_response(voices)

    async def api_machines(self, request: web.Request) -> web.Response:
        """Get list of all machines (local + configured remotes)."""
        import socket

        machines = []

        # Always include local machine first
        machines.append({
            "id": "local",
            "host": socket.gethostname(),
            "local": True,
            "status": "online",
        })

        # Add configured remote machines
        machines_file = self.config.machines.file
        if machines_file.exists():
            try:
                with open(machines_file) as f:
                    data = json.load(f)
                    for m in data.get("machines", []):
                        m["local"] = False
                        # Check if reachable (quick SSH check)
                        m["status"] = await self._check_machine_status(m)
                        machines.append(m)
            except (json.JSONDecodeError, IOError):
                pass

        return web.json_response(machines)

    async def _check_machine_status(self, machine: dict) -> str:
        """Check if a remote machine is reachable via SSH."""
        host = machine.get("host", "")
        user = machine.get("user", "")
        ssh_target = f"{user}@{host}" if user else host

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "ssh", "-o", "ConnectTimeout=2", "-o", "BatchMode=yes",
                    ssh_target, "echo ok",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                ),
                timeout=3.0
            )
            await proc.wait()
            return "online" if proc.returncode == 0 else "offline"
        except (asyncio.TimeoutError, Exception):
            return "offline"

    async def api_add_machine(self, request: web.Request) -> web.Response:
        """Add a new machine to the registry."""
        try:
            data = await request.json()
            machine_id = data.get("id", "").strip()
            host = data.get("host", "").strip()
            user = data.get("user", "").strip()
            projects_dir = data.get("projects_dir", "").strip()

            if not machine_id or not host:
                return web.json_response({"error": "ID and host are required"})

            machines_file = self.config.machines.file
            machines_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing machines
            machines = []
            if machines_file.exists():
                try:
                    with open(machines_file) as f:
                        machines = json.load(f).get("machines", [])
                except (json.JSONDecodeError, IOError):
                    pass

            # Check for duplicate ID
            if any(m.get("id") == machine_id for m in machines):
                return web.json_response({"error": f"Machine '{machine_id}' already exists"})

            # Add new machine
            new_machine = {"id": machine_id, "host": host}
            if user:
                new_machine["user"] = user
            if projects_dir:
                new_machine["projects_dir"] = projects_dir

            machines.append(new_machine)

            # Save
            with open(machines_file, "w") as f:
                json.dump({"machines": machines}, f, indent=2)

            # Reload agent backend to pick up new machines
            if self.agent and hasattr(self.agent, '_load_machines'):
                self.agent._load_machines()

            return web.json_response({"success": True, "machine": new_machine})
        except Exception as e:
            return web.json_response({"error": str(e)})

    async def api_remove_machine(self, request: web.Request) -> web.Response:
        """Remove a machine from the registry."""
        machine_id = request.match_info["machine_id"]

        try:
            # Can't remove local machine
            if machine_id == "local":
                return web.json_response({"error": "Cannot remove local machine"})

            machines_file = self.config.machines.file
            if not machines_file.exists():
                return web.json_response({"error": "No machines configured"})

            # Load machines
            try:
                with open(machines_file) as f:
                    data = json.load(f)
                    machines = data.get("machines", [])
            except (json.JSONDecodeError, IOError) as e:
                return web.json_response({"error": f"Failed to read machines file: {e}"})

            # Check if machine exists
            machine = next((m for m in machines if m.get("id") == machine_id), None)
            if not machine:
                return web.json_response({"error": f"Machine '{machine_id}' not found"})

            # Remove from machines list
            machines = [m for m in machines if m.get("id") != machine_id]

            # Save updated machines file
            with open(machines_file, "w") as f:
                json.dump({"machines": machines}, f, indent=2)
                f.write("\n")

            # Clean up rooms.json entries for this machine
            rooms_file = self.config.rooms.file
            rooms_removed = []
            if rooms_file.exists():
                try:
                    with open(rooms_file) as f:
                        rooms_data = json.load(f)

                    # Find rooms matching *@machine_id pattern
                    rooms_to_remove = [
                        room for room in rooms_data.keys()
                        if room.endswith(f"@{machine_id}")
                    ]

                    if rooms_to_remove:
                        for room in rooms_to_remove:
                            del rooms_data[room]
                            rooms_removed.append(room)
                        with open(rooms_file, "w") as f:
                            json.dump(rooms_data, f, indent=2)
                            f.write("\n")
                except (json.JSONDecodeError, IOError):
                    pass

            # Reload agent backend to pick up changes
            if self.agent and hasattr(self.agent, '_load_machines'):
                self.agent._load_machines()

            return web.json_response({
                "success": True,
                "machine_id": machine_id,
                "rooms_removed": rooms_removed,
            })

        except Exception as e:
            logger.error(f"Failed to remove machine: {e}")
            return web.json_response({"error": str(e)})

    async def api_get_config(self, request: web.Request) -> web.Response:
        """Get config file contents."""
        config_path = Path.home() / ".agentwire" / "config.yaml"
        content = ""
        if config_path.exists():
            try:
                content = config_path.read_text()
            except IOError as e:
                return web.json_response({"error": str(e)})
        else:
            # Return default config template
            content = """# AgentWire Configuration
server:
  host: "0.0.0.0"
  port: 8765

tts:
  backend: "chatterbox"
  url: "http://localhost:8100"
  default_voice: "bashbunni"

stt:
  backend: "whisperkit"  # whisperkit | whispercpp | openai | none

projects:
  dir: "~/projects"
  worktrees:
    enabled: true
    suffix: "-worktrees"
"""
        return web.json_response({
            "path": str(config_path),
            "content": content,
            "exists": config_path.exists(),
        })

    async def api_save_config(self, request: web.Request) -> web.Response:
        """Save config file contents."""
        try:
            data = await request.json()
            content = data.get("content", "")

            # Validate YAML syntax
            import yaml
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                return web.json_response({"error": f"Invalid YAML: {e}"})

            config_path = Path.home() / ".agentwire" / "config.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(content)

            return web.json_response({"success": True})
        except Exception as e:
            return web.json_response({"error": str(e)})

    async def api_reload_config(self, request: web.Request) -> web.Response:
        """Reload configuration from disk."""
        try:
            from .config import reload_config
            self.config = reload_config()

            # Reinitialize backends with new config
            await self.init_backends()

            return web.json_response({"success": True})
        except Exception as e:
            return web.json_response({"error": str(e)})

    async def handle_transcribe(self, request: web.Request) -> web.Response:
        """Transcribe audio to text."""
        try:
            reader = await request.multipart()
            audio_field = await reader.next()

            if audio_field is None:
                return web.json_response({"error": "No audio data"})

            # Read audio data
            audio_data = await audio_field.read()

            if not audio_data:
                return web.json_response({"error": "Empty audio data"})

            # Save webm to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_data)
                webm_path = f.name

            # Convert webm to wav (16kHz mono for Whisper)
            wav_path = webm_path.replace(".webm", ".wav")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-i", webm_path,
                    "-ar", "16000", "-ac", "1", "-y", wav_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()

                if proc.returncode != 0 or not Path(wav_path).exists():
                    logger.error("Failed to convert webm to wav (ffmpeg returned %d)", proc.returncode)
                    return web.json_response({"error": "Audio conversion failed"})

                # Transcribe the wav file
                logger.debug("Transcribing %s", wav_path)
                text = await self.stt.transcribe(Path(wav_path))
                return web.json_response({"text": text})
            finally:
                Path(webm_path).unlink(missing_ok=True)
                Path(wav_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return web.json_response({"error": str(e)})

    async def handle_upload(self, request: web.Request) -> web.Response:
        """Upload an image file for attachment to messages."""
        try:
            reader = await request.multipart()
            image_field = await reader.next()

            if image_field is None:
                return web.json_response({"error": "No image data"})

            # Check content type (try property, header, and filename extension)
            content_type = getattr(image_field, 'content_type', None) or image_field.headers.get("Content-Type", "")
            filename = image_field.filename or ""
            logger.debug(f"Upload content_type: {content_type}, filename: {filename}")

            # Fallback: detect from filename extension
            if not content_type or not content_type.startswith("image/"):
                ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
                ext_to_mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
                if ext in ext_to_mime:
                    content_type = ext_to_mime[ext]
                    logger.debug(f"Detected content_type from extension: {content_type}")

            if not content_type.startswith("image/"):
                return web.json_response({"error": f"File must be an image (got {content_type or 'unknown'})"})

            # Read image data
            image_data = await image_field.read()

            if not image_data:
                return web.json_response({"error": "Empty image data"})

            # Check file size
            max_bytes = self.config.uploads.max_size_mb * 1024 * 1024
            if len(image_data) > max_bytes:
                return web.json_response({
                    "error": f"File too large (max {self.config.uploads.max_size_mb}MB)"
                })

            # Ensure uploads directory exists
            uploads_dir = self.config.uploads.dir
            uploads_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            ext = content_type.split("/")[-1]
            if ext == "jpeg":
                ext = "jpg"
            filename = f"{int(time.time())}-{uuid.uuid4().hex[:8]}.{ext}"
            filepath = uploads_dir / filename

            # Save file
            filepath.write_bytes(image_data)
            logger.info(f"Uploaded image: {filepath}")

            return web.json_response({
                "path": str(filepath),
                "filename": filename
            })

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return web.json_response({"error": str(e)})

    async def handle_send(self, request: web.Request) -> web.Response:
        """Send text to an agent session."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            text = data.get("text", "").strip()

            if not text:
                return web.json_response({"error": "No text provided"})

            success = self.agent.send_input(name, text)

            if not success:
                return web.json_response({"error": "Failed to send to session"})

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Send failed: {e}")
            return web.json_response({"error": str(e)})

    # TTS Integration

    def _prepend_silence(self, wav_data: bytes, ms: int = 300) -> bytes:
        """Prepend silence to WAV audio to prevent first syllable cutoff.

        Works with any WAV format (PCM, IEEE Float, etc.) by directly
        manipulating the raw bytes.

        Args:
            wav_data: Original WAV file bytes
            ms: Milliseconds of silence to prepend

        Returns:
            New WAV bytes with silence prepended
        """
        try:
            # Parse WAV header to get format info
            # RIFF header: 12 bytes, fmt chunk: variable, data chunk: variable
            if len(wav_data) < 44 or wav_data[:4] != b'RIFF' or wav_data[8:12] != b'WAVE':
                return wav_data

            # Find fmt chunk
            pos = 12
            sample_rate = 24000  # default
            bytes_per_sample = 4  # default for float32
            channels = 1

            while pos < len(wav_data) - 8:
                chunk_id = wav_data[pos:pos+4]
                chunk_size = struct.unpack('<I', wav_data[pos+4:pos+8])[0]

                if chunk_id == b'fmt ':
                    # fmt chunk: format(2), channels(2), sample_rate(4), byte_rate(4), block_align(2), bits_per_sample(2)
                    channels = struct.unpack('<H', wav_data[pos+10:pos+12])[0]
                    sample_rate = struct.unpack('<I', wav_data[pos+12:pos+16])[0]
                    bits_per_sample = struct.unpack('<H', wav_data[pos+22:pos+24])[0]
                    bytes_per_sample = bits_per_sample // 8

                elif chunk_id == b'data':
                    # Found data chunk - insert silence here
                    data_start = pos + 8
                    original_data = wav_data[data_start:data_start + chunk_size]

                    # Calculate silence
                    silence_samples = int(sample_rate * ms / 1000)
                    silence_bytes = b'\x00' * (silence_samples * bytes_per_sample * channels)

                    # New data size
                    new_data_size = len(silence_bytes) + len(original_data)
                    new_file_size = len(wav_data) - chunk_size + new_data_size - 8

                    # Rebuild WAV
                    result = bytearray(wav_data[:4])  # RIFF
                    result += struct.pack('<I', new_file_size)  # New file size
                    result += wav_data[8:pos+4]  # Up to data chunk id
                    result += struct.pack('<I', new_data_size)  # New data size
                    result += silence_bytes  # Prepended silence
                    result += original_data  # Original audio

                    return bytes(result)

                pos += 8 + chunk_size
                if chunk_size % 2:  # Chunks are word-aligned
                    pos += 1

            return wav_data
        except Exception as e:
            logger.warning(f"Failed to prepend silence: {e}")
            return wav_data

    async def _say_to_room(self, room_name: str, text: str):
        """Generate TTS audio and send to room clients (internal)."""
        await self.speak(room_name, text)

    async def api_say(self, request: web.Request) -> web.Response:
        """POST /api/say/{room} - Generate TTS and broadcast to room."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            text = data.get("text", "").strip()

            if not text:
                return web.json_response({"error": "No text provided"}, status=400)

            # Ensure room exists (create if not)
            if name not in self.rooms:
                self.rooms[name] = Room(name=name, config=self._get_room_config(name))

            room = self.rooms[name]

            # Track this text to avoid duplicate TTS from output polling
            room.played_says.add(text)
            if len(room.played_says) > 50:
                room.played_says = set(list(room.played_says)[-25:])

            logger.info(f"[{name}] API say: {text[:50]}...")

            # Generate and broadcast TTS
            await self.speak(name, text)

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Say API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_answer(self, request: web.Request) -> web.Response:
        """POST /api/answer/{room} - Answer an AskUserQuestion prompt."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            answer = data.get("answer", "").strip()
            is_custom = data.get("custom", False)
            option_number = data.get("option_number")  # For "type something" flow

            if not answer:
                return web.json_response({"error": "No answer provided"}, status=400)

            # Three modes:
            # 1. Regular option: just send the number key (no Enter)
            # 2. "Type something" option: send number key, wait, send text + Enter
            # 3. Legacy custom: just send text + Enter (for "Other" without number)
            if option_number:
                # "Type something" flow: select option first (no Enter), then type
                self.agent.send_keys(name, str(option_number))
                await asyncio.sleep(0.5)  # Wait for Claude to show text input
                success = self.agent.send_input(name, answer)  # text + Enter
            elif is_custom:
                # Legacy custom answer: type the text and press Enter
                success = self.agent.send_input(name, answer)
            else:
                # Just send the number key - AskUserQuestion responds to single keypress
                success = self.agent.send_keys(name, str(answer))

            if not success:
                return web.json_response({"error": "Failed to send answer"}, status=500)

            # Notify clients the question was answered
            if name in self.rooms:
                room = self.rooms[name]
                room.last_question = None
                await self._broadcast(room, {"type": "question_answered"})

            logger.info(f"[{name}] Answered: {answer}")
            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Answer API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_permission_request(self, request: web.Request) -> web.Response:
        """POST /api/permission/{room} - Handle permission request from Claude Code hook.

        This endpoint is called by the permission hook script when Claude Code
        needs permission for an action. It broadcasts the request to connected
        clients and waits for a response.
        """
        name = request.match_info["name"]
        try:
            data = await request.json()
            tool_name = data.get("tool_name", "unknown")
            tool_input = data.get("tool_input", {})
            message = data.get("message", "")

            logger.info(f"[{name}] Permission request: {tool_name}")

            # Ensure room exists
            if name not in self.rooms:
                self.rooms[name] = Room(name=name, config=self._get_room_config(name))

            room = self.rooms[name]

            # Create pending permission request
            room.pending_permission = PendingPermission(request=data)

            # Broadcast permission request to all clients (Task 3.1)
            await self._broadcast(room, {
                "type": "permission_request",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "message": message,
            })

            # Generate TTS announcement (Task 3.6)
            await self._announce_permission_request(name, tool_name, tool_input)

            # Wait for user decision with 5 minute timeout
            try:
                await asyncio.wait_for(room.pending_permission.event.wait(), timeout=300)
            except asyncio.TimeoutError:
                logger.warning(f"[{name}] Permission request timed out")
                room.pending_permission = None
                await self._broadcast(room, {"type": "permission_timeout"})
                return web.json_response({
                    "decision": "deny",
                    "message": "Permission request timed out (5 minutes)"
                })

            # Return the decision to the hook script
            decision = room.pending_permission.decision
            room.pending_permission = None

            logger.info(f"[{name}] Permission decision: {decision}")
            return web.json_response(decision)

        except Exception as e:
            logger.error(f"Permission request failed: {e}")
            return web.json_response(
                {"decision": "deny", "message": str(e)},
                status=500
            )

    async def api_permission_respond(self, request: web.Request) -> web.Response:
        """POST /api/permission/{room}/respond - User responds to permission request.

        Called by the portal UI when user clicks Allow or Deny.
        """
        name = request.match_info["name"]
        try:
            data = await request.json()
            decision = data.get("decision", "deny")

            logger.info(f"[{name}] Permission response: {decision}")

            if name not in self.rooms:
                return web.json_response({"error": "Room not found"}, status=404)

            room = self.rooms[name]

            if not room.pending_permission:
                return web.json_response({"error": "No pending permission request"}, status=400)

            # Store decision and signal the waiting request
            room.pending_permission.decision = {"decision": decision}
            if decision == "deny":
                room.pending_permission.decision["message"] = data.get("message", "User denied permission")
            room.pending_permission.event.set()

            # Broadcast permission_resolved to all clients (Task 3.7)
            await self._broadcast(room, {
                "type": "permission_resolved",
                "decision": decision,
            })

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Permission respond failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _announce_permission_request(self, room_name: str, tool_name: str, tool_input: dict):
        """Generate TTS announcement for permission request (Task 3.6)."""
        # Build a natural announcement message
        if tool_name == "Edit":
            file_path = tool_input.get("file_path", "a file")
            # Extract just the filename for brevity
            filename = Path(file_path).name if file_path else "a file"
            text = f"Claude wants to edit {filename}"
        elif tool_name == "Write":
            file_path = tool_input.get("file_path", "a file")
            filename = Path(file_path).name if file_path else "a file"
            text = f"Claude wants to write to {filename}"
        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            # Truncate long commands
            if len(command) > 50:
                command = command[:47] + "..."
            text = f"Claude wants to run a command: {command}"
        else:
            text = f"Claude wants to use {tool_name}"

        await self._say_to_room(room_name, text)

    async def api_recreate_session(self, request: web.Request) -> web.Response:
        """POST /api/room/{name}/recreate - Destroy session/worktree and create fresh one.

        Workflow:
        1. Kill the tmux session (and Claude Code within it)
        2. Remove the git worktree (if applicable)
        3. Git pull latest in the main project directory
        4. Create new worktree with timestamp-based branch
        5. Spawn new tmux session with Claude Code
        """
        import subprocess

        name = request.match_info["name"]
        try:
            logger.info(f"[{name}] Recreating session...")

            # Parse session name
            project, branch, machine = parse_session_name(name)
            projects_dir = self.config.projects.dir
            project_path = projects_dir / project

            # Step 1: Kill the current session gracefully
            logger.info(f"[{name}] Killing current session...")
            self.agent.send_keys(name, "/exit")
            await asyncio.sleep(1)
            self.agent.kill_session(name)
            await asyncio.sleep(0.5)

            # Step 2: Remove old worktree (if this was a worktree session)
            if branch and self.config.projects.worktrees.enabled:
                old_worktree_path = get_session_path(
                    name,
                    projects_dir,
                    self.config.projects.worktrees.suffix,
                )
                logger.info(f"[{name}] Removing worktree at {old_worktree_path}...")
                if old_worktree_path.exists():
                    # Use git worktree remove
                    removed = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: remove_worktree(project_path, old_worktree_path)
                    )
                    if not removed:
                        # Force remove if git worktree remove fails
                        logger.warning(f"[{name}] git worktree remove failed, forcing...")
                        subprocess.run(
                            ["git", "worktree", "remove", "--force", str(old_worktree_path)],
                            cwd=project_path,
                            capture_output=True,
                        )

            # Step 3: Git pull latest in main project
            logger.info(f"[{name}] Pulling latest in {project_path}...")
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["git", "pull"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                )
            )
            if result.returncode != 0:
                logger.warning(f"[{name}] git pull failed: {result.stderr}")
                # Continue anyway - might be offline or no remote

            # Step 4: Create new session (worktree or simple)
            if self.config.projects.worktrees.enabled:
                # Create worktree with timestamp-based branch
                new_branch = f"session-{int(time.time())}"
                new_session_name = f"{project}/{new_branch}"
                if machine:
                    new_session_name = f"{new_session_name}@{machine}"

                new_worktree_path = get_session_path(
                    new_session_name,
                    projects_dir,
                    self.config.projects.worktrees.suffix,
                )

                logger.info(f"[{name}] Creating worktree at {new_worktree_path}...")
                worktree_created = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ensure_worktree(
                        project_path,
                        new_branch,
                        new_worktree_path,
                        self.config.projects.worktrees.auto_create_branch,
                    )
                )

                if not worktree_created:
                    return web.json_response(
                        {"error": f"Failed to create worktree for '{new_branch}'"},
                        status=500
                    )

                work_dir = str(new_worktree_path)
            else:
                # Simple session without worktree
                new_session_name = project
                if machine:
                    new_session_name = f"{new_session_name}@{machine}"
                work_dir = str(project_path)

            # Step 5: Create new tmux session with new Claude session ID
            # Get old config for inheriting settings
            configs = self._load_room_configs()
            old_config = configs.get(name, {})
            bypass_permissions = old_config.get("bypass_permissions", True)

            claude_session_id = str(uuid.uuid4())
            logger.info(f"[{name}] Creating new session '{new_session_name}'...")
            success = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.agent.create_session(
                    new_session_name, work_dir,
                    options={
                        "session_id": claude_session_id,
                        "bypass_permissions": bypass_permissions,
                        "room_name": new_session_name,
                    }
                )
            )

            if not success:
                return web.json_response(
                    {"error": "Failed to create new session"},
                    status=500
                )

            # Clean up old room state
            if name in self.rooms:
                room = self.rooms[name]
                if room.output_task:
                    room.output_task.cancel()
                del self.rooms[name]

            # Save new room config with session ID and inherited settings
            configs[new_session_name] = {
                "voice": old_config.get("voice", self.config.tts.default_voice),
                "claude_session_id": claude_session_id,
                "bypass_permissions": bypass_permissions,
            }
            self._save_room_configs(configs)

            logger.info(f"[{name}] Session recreated as '{new_session_name}'")
            return web.json_response({"success": True, "session": new_session_name})

        except Exception as e:
            logger.error(f"Recreate session API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_spawn_sibling(self, request: web.Request) -> web.Response:
        """POST /api/room/{name}/spawn-sibling - Create a new session in same project.

        Creates a parallel session in a new worktree without destroying the current one.
        Useful for working on multiple features in the same project simultaneously.
        """
        name = request.match_info["name"]
        try:
            logger.info(f"[{name}] Spawning sibling session...")

            # Parse session name to get project and machine
            project, _, machine = parse_session_name(name)
            projects_dir = self.config.projects.dir
            project_path = projects_dir / project

            if not self.config.projects.worktrees.enabled:
                return web.json_response(
                    {"error": "Worktrees are disabled in config"},
                    status=400
                )

            # Create new worktree with timestamp-based branch
            new_branch = f"session-{int(time.time())}"
            new_session_name = f"{project}/{new_branch}"
            if machine:
                new_session_name = f"{new_session_name}@{machine}"

            new_worktree_path = get_session_path(
                new_session_name,
                projects_dir,
                self.config.projects.worktrees.suffix,
            )

            logger.info(f"[{name}] Creating sibling worktree at {new_worktree_path}...")
            worktree_created = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: ensure_worktree(
                    project_path,
                    new_branch,
                    new_worktree_path,
                    self.config.projects.worktrees.auto_create_branch,
                )
            )

            if not worktree_created:
                return web.json_response(
                    {"error": f"Failed to create worktree for '{new_branch}'"},
                    status=500
                )

            # Create new tmux session with session ID
            # Get old config for inheriting settings
            configs = self._load_room_configs()
            old_config = configs.get(name, {})
            bypass_permissions = old_config.get("bypass_permissions", True)

            claude_session_id = str(uuid.uuid4())
            logger.info(f"[{name}] Creating sibling session '{new_session_name}'...")
            success = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.agent.create_session(
                    new_session_name, str(new_worktree_path),
                    options={
                        "session_id": claude_session_id,
                        "bypass_permissions": bypass_permissions,
                        "room_name": new_session_name,
                    }
                )
            )

            if not success:
                return web.json_response(
                    {"error": "Failed to create session"},
                    status=500
                )

            # Save room config with session ID and inherited settings
            configs[new_session_name] = {
                "voice": old_config.get("voice", self.config.tts.default_voice),
                "claude_session_id": claude_session_id,
                "bypass_permissions": bypass_permissions,
            }
            self._save_room_configs(configs)

            logger.info(f"[{name}] Sibling session created: '{new_session_name}'")
            return web.json_response({"success": True, "session": new_session_name})

        except Exception as e:
            logger.error(f"Spawn sibling API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_fork_session(self, request: web.Request) -> web.Response:
        """POST /api/room/{name}/fork - Fork the Claude Code session.

        Creates a new session that continues from the current conversation context.
        Uses Claude Code's --resume --fork-session to fork the session.
        """
        name = request.match_info["name"]
        try:
            # Get current room config to find Claude session ID
            room_config = self._get_room_config(name)
            if not room_config.claude_session_id:
                return web.json_response(
                    {"error": "No Claude session ID found. Session may have been created before fork support was added."},
                    status=400
                )

            logger.info(f"[{name}] Forking session from {room_config.claude_session_id}...")

            # Parse session name to get project and machine
            project, _, machine = parse_session_name(name)
            projects_dir = self.config.projects.dir
            project_path = projects_dir / project

            if not self.config.projects.worktrees.enabled:
                return web.json_response(
                    {"error": "Worktrees are disabled in config"},
                    status=400
                )

            # Find next available fork number
            configs = self._load_room_configs()
            fork_num = 1
            while True:
                candidate = f"{project}-fork-{fork_num}"
                if machine:
                    candidate = f"{candidate}@{machine}"
                if candidate not in configs and not self.agent.session_exists(candidate):
                    break
                fork_num += 1

            new_branch = f"fork-{fork_num}"
            new_session_name = f"{project}-fork-{fork_num}"
            if machine:
                new_session_name = f"{new_session_name}@{machine}"

            new_worktree_path = get_session_path(
                new_session_name,
                projects_dir,
                self.config.projects.worktrees.suffix,
            )

            logger.info(f"[{name}] Creating fork worktree at {new_worktree_path}...")
            worktree_created = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: ensure_worktree(
                    project_path,
                    new_branch,
                    new_worktree_path,
                    self.config.projects.worktrees.auto_create_branch,
                )
            )

            if not worktree_created:
                return web.json_response(
                    {"error": f"Failed to create worktree for '{new_branch}'"},
                    status=500
                )

            # Copy Claude session file to worktree's project directory
            # Claude stores sessions per-project path, so we need to copy the source session
            def copy_session_file():
                claude_dir = Path.home() / ".claude" / "projects"
                # Encode paths like Claude does: /foo/bar -> -foo-bar
                orig_encoded = str(project_path).replace("/", "-")
                if orig_encoded.startswith("-"):
                    orig_encoded = orig_encoded  # Keep leading dash
                new_encoded = str(new_worktree_path).replace("/", "-")

                orig_session_file = claude_dir / orig_encoded / f"{room_config.claude_session_id}.jsonl"
                new_project_dir = claude_dir / new_encoded

                if orig_session_file.exists():
                    new_project_dir.mkdir(parents=True, exist_ok=True)
                    new_session_file = new_project_dir / f"{room_config.claude_session_id}.jsonl"
                    shutil.copy2(orig_session_file, new_session_file)
                    logger.info(f"[{name}] Copied session file to {new_session_file}")
                    return True
                else:
                    logger.warning(f"[{name}] Original session file not found: {orig_session_file}")
                    return False

            await asyncio.get_event_loop().run_in_executor(None, copy_session_file)

            # Create new session with fork - new session ID but forking from original
            # Inherit bypass_permissions from parent room
            new_claude_session_id = str(uuid.uuid4())
            logger.info(f"[{name}] Creating forked session '{new_session_name}'...")
            success = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.agent.create_session(
                    new_session_name, str(new_worktree_path),
                    options={
                        "session_id": new_claude_session_id,
                        "fork_from": room_config.claude_session_id,
                        "bypass_permissions": room_config.bypass_permissions,
                        "room_name": new_session_name,
                    }
                )
            )

            if not success:
                return web.json_response(
                    {"error": "Failed to create forked session"},
                    status=500
                )

            # Save room config with new session ID and inherited settings
            configs = self._load_room_configs()
            configs[new_session_name] = {
                "voice": room_config.voice,
                "claude_session_id": new_claude_session_id,
                "bypass_permissions": room_config.bypass_permissions,
            }
            self._save_room_configs(configs)

            logger.info(f"[{name}] Session forked as '{new_session_name}'")
            return web.json_response({"success": True, "session": new_session_name})

        except Exception as e:
            logger.error(f"Fork session API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_restart_service(self, request: web.Request) -> web.Response:
        """POST /api/room/{name}/restart-service - Restart a system service.

        For system sessions (agentwire, agentwire-portal, agentwire-tts),
        this properly restarts the service.
        """
        import subprocess

        name = request.match_info["name"]
        base_name = name.split("@")[0]

        if base_name not in self.SYSTEM_SESSIONS:
            return web.json_response(
                {"error": f"'{name}' is not a system session"},
                status=400
            )

        try:
            logger.info(f"[{name}] Restarting service...")

            if base_name == "agentwire-portal":
                # Special case: we are the portal, need to restart ourselves
                # Schedule restart after responding
                # Can't use `agentwire portal start` as it tries to attach to terminal
                async def delayed_restart():
                    await asyncio.sleep(1)
                    logger.info("Portal restarting...")
                    # Kill the tmux session (which kills us)
                    subprocess.run(
                        ["tmux", "kill-session", "-t", "agentwire-portal"],
                        capture_output=True
                    )
                    await asyncio.sleep(0.5)
                    # Create new tmux session with portal serve command
                    subprocess.run(
                        ["tmux", "new-session", "-d", "-s", "agentwire-portal"],
                        capture_output=True
                    )
                    subprocess.run(
                        ["tmux", "send-keys", "-t", "agentwire-portal",
                         "agentwire portal serve", "Enter"],
                        capture_output=True
                    )

                asyncio.create_task(delayed_restart())
                return web.json_response({
                    "success": True,
                    "message": "Portal restarting in 1 second..."
                })

            elif base_name == "agentwire-tts":
                # Restart TTS server
                result = subprocess.run(
                    ["agentwire", "tts", "stop"],
                    capture_output=True, text=True
                )
                await asyncio.sleep(0.5)
                subprocess.Popen(
                    ["agentwire", "tts", "start"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return web.json_response({
                    "success": True,
                    "message": "TTS server restarted"
                })

            elif base_name == "agentwire":
                # Restart the orchestrator session - kill Claude and restart it
                self.agent.send_keys(name, "/exit")
                await asyncio.sleep(1)

                # Send the agent command to restart Claude
                agent_cmd = self.agent.agent_command
                self.agent.send_input(name, agent_cmd)

                return web.json_response({
                    "success": True,
                    "message": "Orchestrator session restarted"
                })

            return web.json_response({"error": "Unknown system session"}, status=400)

        except Exception as e:
            logger.error(f"Restart service API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def speak(self, room_name: str, text: str):
        """Generate TTS audio and send to room clients."""
        if room_name not in self.rooms:
            return

        room = self.rooms[room_name]
        if not room.clients:
            return

        # Notify clients TTS is starting (include text for display)
        await self._broadcast(room, {"type": "tts_start", "text": text})

        try:
            # Generate audio
            logger.info(f"[{room_name}] TTS voice: {room.config.voice}")
            audio_data = await self.tts.generate(
                text=text,
                voice=room.config.voice,
                exaggeration=room.config.exaggeration,
                cfg_weight=room.config.cfg_weight,
            )

            if audio_data:
                # Prepend silence to prevent first syllable cutoff
                audio_data = self._prepend_silence(audio_data, ms=300)
                # Send base64 encoded audio
                audio_b64 = base64.b64encode(audio_data).decode()
                await self._broadcast(room, {"type": "audio", "data": audio_b64})

        except Exception as e:
            logger.error(f"TTS failed for {room_name}: {e}")
        finally:
            # Unlock room after TTS
            if room.locked_by:
                room.locked_by = None
                await self._broadcast(room, {"type": "room_unlocked"})


async def run_server(config: Config):
    """Run the AgentWire server."""
    server = AgentWireServer(config)
    await server.init_backends()

    # Cleanup old uploads on startup
    await server.cleanup_old_uploads()

    # Setup SSL if configured
    ssl_context = None
    if config.server.ssl.enabled:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(
            config.server.ssl.cert, config.server.ssl.key
        )

    runner = web.AppRunner(server.app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        config.server.host,
        config.server.port,
        ssl_context=ssl_context,
    )

    protocol = "https" if ssl_context else "http"
    logger.info(f"Starting AgentWire server at {protocol}://{config.server.host}:{config.server.port}")

    try:
        await site.start()
        # Keep running
        while True:
            await asyncio.sleep(3600)
    finally:
        await server.close_backends()
        await runner.cleanup()


def main(config_path: str | None = None, **overrides):
    """Entry point for running the server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(config_path)

    # Apply CLI overrides
    if overrides.get("port"):
        config.server.port = overrides["port"]
    if overrides.get("host"):
        config.server.host = overrides["host"]
    if overrides.get("no_tts"):
        config.tts.backend = "none"
    if overrides.get("no_stt"):
        config.stt.backend = "none"

    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
