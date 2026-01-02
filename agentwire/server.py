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
from .worktree import ensure_worktree, get_project_type, get_session_path, parse_session_name

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
        self.app.router.add_get("/api/voices", self.api_voices)
        self.app.router.add_delete("/api/sessions/{name:.+}", self.api_close_session)
        self.app.router.add_get("/api/sessions/archive", self.api_archived_sessions)
        self.app.router.add_get("/api/machines", self.api_machines)
        self.app.router.add_post("/api/machines", self.api_add_machine)
        self.app.router.add_get("/api/config", self.api_get_config)
        self.app.router.add_post("/api/config", self.api_save_config)
        self.app.router.add_post("/api/config/reload", self.api_reload_config)
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

    async def handle_room(self, request: web.Request) -> web.Response:
        """Serve a room page."""
        name = request.match_info["name"]
        room_config = self._get_room_config(name)
        voices = await self._get_voices()

        html = self._render_template(
            "room.html",
            room_name=name,
            config=room_config,
            voices=voices,
            current_voice=room_config.voice,
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

            # Create session
            success = self.agent.create_session(name, str(work_dir))
            if not success:
                return web.json_response({"error": "Failed to create session"})

            # Save room config
            configs = self._load_room_configs()
            configs[name] = {"voice": voice}
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

            # Check content type
            content_type = image_field.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return web.json_response({"error": "File must be an image"})

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
