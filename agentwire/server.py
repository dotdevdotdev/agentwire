"""
AgentWire WebSocket server.

Multi-room voice web interface for AI coding agents.
"""

import asyncio
import base64
import fcntl
import json
import logging
import os
import pty
import re
import shlex
import ssl
import struct
import subprocess
import tempfile
import termios
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp_jinja2
import jinja2
from aiohttp import web

from .config import Config, load_config
from .worktree import get_project_type, parse_session_name

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


def _is_allowed_in_restricted_mode(tool_name: str, tool_input: dict) -> bool:
    """Check if command is allowed in restricted mode.

    Allows:
    - AskUserQuestion tool (for interactive prompts)
    - Bash: say "message" or remote-say "message"

    Rejects any shell operators, redirects, or multi-line commands.
    """
    # Allow AskUserQuestion tool
    if tool_name == "AskUserQuestion":
        return True

    if tool_name != "Bash":
        return False

    command = tool_input.get("command", "").strip()

    # Reject multi-line commands immediately
    if '\n' in command:
        return False

    # Match: (say|remote-say) followed by quoted string and nothing else
    # Allows: say "hello world"
    #         say 'hello world'
    #         remote-say "done"
    # Rejects: say "hi" && rm -rf /
    #          say "hi" > /tmp/log
    #          say $(cat /etc/passwd)
    pattern = r'^(say|remote-say)\s+(["\']).*\2\s*$'

    return bool(re.match(pattern, command))


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
    restricted: bool = False  # Restricted mode: only say/remote-say allowed


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
    last_output_timestamp: float = 0.0  # Last time output changed (server-side activity tracking)
    is_active: bool = False  # Current active/idle state for transition detection


class AgentWireServer:
    """Main server managing rooms, WebSockets, and agent sessions."""

    def __init__(self, config: Config):
        self.config = config
        self.rooms: dict[str, Room] = {}
        self.session_activity: dict[str, dict] = {}  # Global activity tracking for all sessions
        self.tts = None
        self.stt = None
        self.agent = None
        self.app = web.Application()
        self._setup_jinja2()
        self._setup_routes()

    def _setup_jinja2(self):
        """Configure Jinja2 template environment."""
        templates_dir = Path(__file__).parent / "templates"
        aiohttp_jinja2.setup(
            self.app,
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

    def _setup_routes(self):
        """Configure HTTP and WebSocket routes."""
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/", self.handle_dashboard)
        self.app.router.add_get("/room/{name:.+}", self.handle_room)
        self.app.router.add_get("/ws/{name:.+}", self.handle_websocket)
        self.app.router.add_get("/ws/terminal/{name:.+}", self.handle_terminal_ws)
        self.app.router.add_get("/api/sessions", self.api_sessions)
        self.app.router.add_get("/api/machine/{machine_id}/status", self.api_machine_status)
        self.app.router.add_get("/api/check-path", self.api_check_path)
        self.app.router.add_get("/api/check-branches", self.api_check_branches)
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
        # Template management
        self.app.router.add_get("/api/templates", self.api_list_templates)
        self.app.router.add_get("/api/templates/{name}", self.api_get_template)
        self.app.router.add_post("/api/templates", self.api_create_template)
        self.app.router.add_delete("/api/templates/{name}", self.api_delete_template)
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
                restricted=cfg.get("restricted", False),  # Default False
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

    async def run_agentwire_cmd(self, args: list[str]) -> tuple[bool, dict]:
        """Run agentwire CLI command, parse JSON output.

        Args:
            args: Command arguments (e.g., ["new", "-s", "myapp/feature"])

        Returns:
            Tuple of (success, result_dict). On success, result_dict contains
            the parsed JSON output. On failure, result_dict contains an "error" key.
        """
        proc = await asyncio.create_subprocess_exec(
            "agentwire", *args, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            try:
                return True, json.loads(stdout.decode())
            except json.JSONDecodeError as e:
                return False, {"error": f"Failed to parse JSON output: {e}"}
        return False, {"error": stderr.decode().strip() or f"Command failed with exit code {proc.returncode}"}

    async def _run_ssh_command(self, machine_id: str, command: str) -> str:
        """Run command on remote machine via SSH.

        Args:
            machine_id: The machine ID from machines.json
            command: Shell command to run remotely

        Returns:
            stdout output if successful, empty string on failure
        """
        machines_file = self.config.machines.file
        if not machines_file.exists():
            return ""

        try:
            with open(machines_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return ""

        machine = next((m for m in data.get("machines", []) if m.get("id") == machine_id), None)
        if not machine:
            return ""

        host = machine.get("host", "")
        user = machine.get("user", "")
        ssh_target = f"{user}@{host}" if user else host

        try:
            proc = await asyncio.create_subprocess_exec(
                "ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                ssh_target, command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode() if proc.returncode == 0 else ""
        except Exception:
            return ""

    # HTTP Handlers

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint for network diagnostics."""
        return web.json_response({"status": "ok", "version": __version__})

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        """Serve the dashboard page."""
        voices = await self._get_voices()
        context = {
            "version": __version__,
            "voices": voices,
            "default_voice": self.config.tts.default_voice,
        }
        response = aiohttp_jinja2.render_template("dashboard.html", request, context)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    # System sessions that get special treatment (restart instead of fork/new/recreate)
    SYSTEM_SESSIONS = {"agentwire", "agentwire-portal", "agentwire-tts"}

    def _is_system_session(self, name: str) -> bool:
        """Check if this is a system session (agentwire services)."""
        # Extract base session name (without @machine suffix)
        base_name = name.split("@")[0]
        return base_name in self.SYSTEM_SESSIONS

    def _get_session_activity_status(self, room: Room) -> str:
        """Calculate activity status based on last output timestamp.

        Returns:
            "active" if output changed within threshold, "idle" otherwise
        """
        if room.last_output_timestamp == 0.0:
            return "idle"

        time_since_last_output = time.time() - room.last_output_timestamp
        threshold = self.config.server.activity_threshold_seconds

        return "active" if time_since_last_output <= threshold else "idle"

    def _get_global_session_activity(self, session_name: str) -> str:
        """Get session activity from global tracking dict.

        Returns:
            "active" if session has recent output, "idle" otherwise
        """
        activity_info = self.session_activity.get(session_name)
        if not activity_info:
            return "idle"

        last_timestamp = activity_info.get("last_output_timestamp", 0.0)
        if last_timestamp == 0.0:
            return "idle"

        time_since_last_output = time.time() - last_timestamp
        threshold = self.config.server.activity_threshold_seconds

        return "active" if time_since_last_output <= threshold else "idle"

    async def handle_room(self, request: web.Request) -> web.Response:
        """Serve a room page."""
        name = request.match_info["name"]
        room_config = self._get_room_config(name)
        voices = await self._get_voices()
        is_system_session = self._is_system_session(name)

        context = {
            "room_name": name,
            "config": room_config,
            "voices": voices,
            "current_voice": room_config.voice,
            "is_system_session": is_system_session,
            "is_project_session": not is_system_session,
            "is_system_session_js": "true" if is_system_session else "false",
        }
        response = aiohttp_jinja2.render_template("room.html", request, context)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

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

    async def handle_terminal_ws(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket endpoint for interactive terminal via tmux attach.

        Provides bidirectional communication between browser terminal (xterm.js)
        and tmux session. Handles terminal input, output, and resize commands.
        """
        room_name = request.match_info["name"]
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        proc = None
        master_fd = None
        tmux_to_ws_task = None
        ws_to_tmux_task = None

        try:
            # Parse session name for local vs remote
            project, branch, machine = parse_session_name(room_name)
            session_name = f"{project}/{branch}" if branch else project

            # Build tmux attach command
            if machine:
                # Remote session via SSH with PTY allocation
                cmd = ["ssh", "-t", machine, "tmux", "attach", "-t", session_name]
                logger.info(f"[Terminal] Attaching to {room_name}: {' '.join(cmd)}")

                # For remote, use subprocess with PTY via ssh -t
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                # Local session - use PTY
                cmd = ["tmux", "attach", "-t", session_name]
                logger.info(f"[Terminal] Attaching to {room_name}: {' '.join(cmd)}")

                # Create PTY for local tmux attach
                master_fd, slave_fd = pty.openpty()

                # Spawn process with slave PTY as stdin/stdout/stderr
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    preexec_fn=os.setsid,  # Create new session
                )

                # Close slave fd in parent - child keeps it open
                os.close(slave_fd)

                # Make master fd non-blocking for async reads
                os.set_blocking(master_fd, False)

                # Send initial window size to trigger tmux redraw
                # Default to 80x24 if browser hasn't sent resize yet
                winsize = struct.pack("HHHH", 24, 80, 0, 0)
                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                logger.info(f"[Terminal] Set initial PTY size to 80x24 (fd={master_fd})")

            # Task: Forward tmux stdout → WebSocket
            async def forward_tmux_to_ws():
                """Read from tmux and send to WebSocket."""
                loop = asyncio.get_event_loop()
                data_queue = asyncio.Queue()
                reader_registered = False

                def on_readable():
                    """Called when PTY master FD has data to read."""
                    try:
                        data = os.read(master_fd, 8192)
                        logger.info(f"[Terminal] on_readable callback: read {len(data) if data else 0} bytes")
                        if data:
                            # Schedule putting data in queue from event loop
                            asyncio.create_task(data_queue.put(data))
                    except OSError as e:
                        logger.info(f"[Terminal] PTY read error: {e}")
                        # Signal EOF
                        asyncio.create_task(data_queue.put(None))

                try:
                    if master_fd is not None:
                        # Local: register reader once for PTY master
                        loop.add_reader(master_fd, on_readable)
                        reader_registered = True
                        logger.info(f"[Terminal] Registered PTY reader for {room_name} (fd={master_fd})")

                    while True:
                        if master_fd is not None:
                            # Local: read from queue populated by on_readable
                            data = await data_queue.get()
                            if data is None:  # EOF signal
                                logger.info(f"[Terminal] Received EOF from PTY for {room_name}")
                                break
                            logger.info(f"[Terminal] Read {len(data)} bytes from PTY for {room_name}")
                            if not ws.closed:
                                await ws.send_bytes(data)
                                logger.info(f"[Terminal] Sent {len(data)} bytes to WebSocket for {room_name}")
                        else:
                            # Remote: read from subprocess stdout
                            data = await proc.stdout.read(8192)
                            if not data:
                                break
                            if not ws.closed:
                                await ws.send_bytes(data)
                except asyncio.CancelledError:
                    logger.debug(f"[Terminal] tmux→ws task cancelled for {room_name}")
                except Exception as e:
                    logger.error(f"[Terminal] Error forwarding tmux→ws for {room_name}: {e}")
                finally:
                    if master_fd is not None and reader_registered:
                        try:
                            loop.remove_reader(master_fd)
                            logger.info(f"[Terminal] Unregistered PTY reader for {room_name}")
                        except Exception:
                            pass

            # Task: Forward WebSocket → tmux stdin
            async def forward_ws_to_tmux():
                """Read from WebSocket and write to tmux stdin."""
                loop = asyncio.get_event_loop()
                try:
                    async for msg in ws:
                        if msg.type == web.WSMsgType.TEXT:
                            try:
                                payload = json.loads(msg.data)
                                msg_type = payload.get("type")

                                if msg_type == "input":
                                    # Terminal input from browser
                                    input_data = payload.get("data", "")
                                    if input_data:
                                        if master_fd is not None:
                                            # Local: write to PTY master
                                            os.write(master_fd, input_data.encode())
                                        elif proc.stdin:
                                            # Remote: write to subprocess stdin
                                            proc.stdin.write(input_data.encode())
                                            await proc.stdin.drain()

                                elif msg_type == "resize":
                                    # Terminal resize
                                    cols = payload.get("cols", 80)
                                    rows = payload.get("rows", 24)
                                    logger.debug(f"[Terminal] Resize {room_name} to {cols}x{rows}")

                                    if master_fd is not None:
                                        # Local: use TIOCSWINSZ ioctl to resize PTY
                                        winsize = struct.pack("HHHH", rows, cols, 0, 0)
                                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                                    else:
                                        # Remote: send tmux resize-window command
                                        resize_cmd = f"tmux resize-window -t {session_name} -x {cols} -y {rows}\n"
                                        resize_proc = await asyncio.create_subprocess_exec(
                                            "ssh", machine, "sh", "-c", resize_cmd,
                                            stdout=asyncio.subprocess.DEVNULL,
                                            stderr=asyncio.subprocess.DEVNULL,
                                        )
                                        await resize_proc.wait()

                            except json.JSONDecodeError:
                                logger.warning(f"[Terminal] Invalid JSON from WebSocket: {msg.data}")
                            except Exception as e:
                                logger.error(f"[Terminal] Error handling message: {e}")

                        elif msg.type == web.WSMsgType.ERROR:
                            logger.error(f"[Terminal] WebSocket error: {ws.exception()}")
                            break

                except asyncio.CancelledError:
                    logger.debug(f"[Terminal] ws→tmux task cancelled for {room_name}")
                except Exception as e:
                    logger.error(f"[Terminal] Error forwarding ws→tmux for {room_name}: {e}")

            # Start both forwarding tasks
            tmux_to_ws_task = asyncio.create_task(forward_tmux_to_ws())
            ws_to_tmux_task = asyncio.create_task(forward_ws_to_tmux())

            # Wait for either task to complete (disconnect or error)
            done, pending = await asyncio.wait(
                [tmux_to_ws_task, ws_to_tmux_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            logger.info(f"[Terminal] Disconnected from {room_name}")

        except FileNotFoundError:
            logger.error(f"[Terminal] tmux command not found")
            if not ws.closed:
                await ws.send_json({
                    "type": "error",
                    "message": "tmux not found on system"
                })

        except Exception as e:
            logger.error(f"[Terminal] Error attaching to {room_name}: {e}")
            if not ws.closed:
                await ws.send_json({
                    "type": "error",
                    "message": f"Failed to attach: {str(e)}"
                })

        finally:
            # Clean up subprocess
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                except Exception as e:
                    logger.debug(f"[Terminal] Error terminating process: {e}")

            # Ensure tasks are cancelled
            for task in [tmux_to_ws_task, ws_to_tmux_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Close PTY master fd if used
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except Exception as e:
                    logger.debug(f"[Terminal] Error closing master fd: {e}")

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
    # Multi-tab format: ←  ☐ Tab1  ☐ Tab2  ✔ Submit  →\n\nQuestion?...
    ASK_PATTERN = re.compile(
        r'☐\s+(\S+)'              # ☐ followed by first word only (active tab name)
        r'.*?\n\s*\n'             # Rest of header line + blank line
        r'((?:.+\n)+?)'           # Question text (one or more lines, non-greedy)
        r'\s*\n'                  # Blank line before options
        r'((?:[❯\s]+\d+\.\s+.+\n(?:\s{3,}.+\n)?)+)',  # Options block
        re.MULTILINE | re.DOTALL
    )

    # Simple format without ☐ header (e.g., "Ready to submit?\n\n❯ 1. Submit\n  2. Cancel")
    ASK_PATTERN_SIMPLE = re.compile(
        r'\n([^\n☐❯]+\?)\s*\n'    # Question ending with ? (not containing ☐ or ❯)
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
                    timestamp = time.time()
                    room.last_output_timestamp = timestamp  # Update activity timestamp

                    # Also update global activity tracking (persists across room create/destroy)
                    self.session_activity[room.name] = {
                        "last_output_timestamp": timestamp,
                        "last_output": output,
                    }

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

                # Try simple pattern if main pattern doesn't match
                # (e.g., "Ready to submit your answers?\n\n❯ 1. Submit")
                header = None
                question = None
                options_block = None

                if ask_match:
                    header = ask_match.group(1)
                    question = ask_match.group(2).strip()
                    options_block = ask_match.group(3)
                else:
                    simple_match = self.ASK_PATTERN_SIMPLE.search(clean_output)
                    if simple_match:
                        question = simple_match.group(1).strip()
                        options_block = simple_match.group(2)
                        # Generate header from question (first word or "Confirm")
                        header = question.split()[0].rstrip('?') if question else "Confirm"

                if question and options_block:
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

                # Check for activity status transitions
                current_status = self._get_session_activity_status(room)
                new_is_active = current_status == "active"

                # Broadcast transition event if state changed
                if new_is_active != room.is_active:
                    room.is_active = new_is_active
                    await self._broadcast(room, {
                        "type": "session_activity",
                        "session": room.name,
                        "active": new_is_active
                    })
                    logger.info(f"[{room.name}] Activity transition: {'active' if new_is_active else 'idle'}")

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
        """List all active sessions grouped by machine."""
        try:
            sessions = self.agent.list_sessions()
            room_configs = self._load_room_configs()

            # Load machines for status checks
            machines_dict = {}
            if hasattr(self.agent, 'machines'):
                for m in self.agent.machines:
                    machines_dict[m.get('id')] = m

            # Group sessions by machine (None = local)
            local_sessions = []
            machine_sessions = {}  # machine_id -> list of sessions

            for name in sessions:
                project, branch, machine_id = parse_session_name(name)

                config = room_configs.get(name, {})

                # Use path from room config if available (set during creation)
                path = config.get("path", str(self.config.projects.dir / project))

                # Calculate activity status from global tracking (works even without active room)
                activity_status = self._get_global_session_activity(name)

                session_data = {
                    "name": name,
                    "path": path,
                    "machine": machine_id,
                    "voice": config.get("voice", self.config.tts.default_voice),
                    "type": get_project_type(Path(path)) if Path(path).exists() else "scratch",
                    "bypass_permissions": config.get("bypass_permissions", True),
                    "restricted": config.get("restricted", False),
                    "activity": activity_status,
                }

                if machine_id is None:
                    local_sessions.append(session_data)
                else:
                    if machine_id not in machine_sessions:
                        machine_sessions[machine_id] = []
                    machine_sessions[machine_id].append(session_data)

            # Build machine list with status
            machines = []
            for machine_id, sessions_list in machine_sessions.items():
                machine_config = machines_dict.get(machine_id, {})

                # Check machine status via SSH
                status = await self._check_machine_status(machine_config)

                machines.append({
                    "id": machine_id,
                    "host": machine_config.get("host", machine_id),
                    "status": status,
                    "session_count": len(sessions_list),
                    "sessions": sessions_list,
                })

            # Return hierarchical structure
            result = {
                "local": {
                    "session_count": len(local_sessions),
                    "sessions": local_sessions,
                },
                "machines": machines,
            }

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return web.json_response({"local": {"session_count": 0, "sessions": []}, "machines": []})

    async def api_machine_status(self, request: web.Request) -> web.Response:
        """Get status for a specific machine.

        Returns online/offline status and session count for a machine.

        URL params:
            machine_id: The machine ID to check

        Response:
            {
                "status": "online" | "offline",
                "session_count": <int>
            }
        """
        machine_id = request.match_info["machine_id"]

        try:
            # Load machines config
            machines_dict = {}
            if hasattr(self.agent, 'machines'):
                for m in self.agent.machines:
                    machines_dict[m.get('id')] = m

            machine_config = machines_dict.get(machine_id)
            if not machine_config:
                return web.json_response(
                    {"status": "offline", "session_count": 0},
                    status=404
                )

            # Check machine status
            status = await self._check_machine_status(machine_config)

            # Count sessions for this machine
            sessions = self.agent.list_sessions()
            session_count = 0
            for name in sessions:
                _, _, session_machine = parse_session_name(name)
                if session_machine == machine_id:
                    session_count += 1

            return web.json_response({
                "status": status,
                "session_count": session_count,
            })
        except Exception as e:
            logger.error(f"Failed to get machine status for {machine_id}: {e}")
            return web.json_response(
                {"status": "offline", "session_count": 0},
                status=500
            )

    async def api_check_path(self, request: web.Request) -> web.Response:
        """Check if a path exists and is a git repo.

        Query params:
            path: The path to check
            machine: Machine ID ('local' or remote machine ID)

        Returns:
            {exists: bool, is_git: bool, current_branch: str|null}
        """
        path = request.query.get("path", "")
        machine = request.query.get("machine", "local")

        if not path:
            return web.json_response({
                "exists": False,
                "is_git": False,
                "current_branch": None
            })

        if machine and machine != "local":
            # Remote path check via SSH
            result = await self._run_ssh_command(
                machine,
                f"test -d {shlex.quote(path)} && echo exists"
            )
            exists = "exists" in result
            is_git = False
            current_branch = None

            if exists:
                result = await self._run_ssh_command(
                    machine,
                    f"test -d {shlex.quote(path)}/.git && echo git"
                )
                is_git = "git" in result

                if is_git:
                    result = await self._run_ssh_command(
                        machine,
                        f"cd {shlex.quote(path)} && git rev-parse --abbrev-ref HEAD"
                    )
                    current_branch = result.strip() if result else None
        else:
            # Local path check
            expanded = Path(path).expanduser().resolve()
            exists = expanded.exists() and expanded.is_dir()
            is_git = exists and (expanded / ".git").exists()
            current_branch = None

            if is_git:
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=expanded,
                    capture_output=True,
                    text=True
                )
                current_branch = result.stdout.strip() if result.returncode == 0 else None

        return web.json_response({
            "exists": exists,
            "is_git": is_git,
            "current_branch": current_branch
        })

    async def api_check_branches(self, request: web.Request) -> web.Response:
        """Get existing branch names matching a prefix.

        Query params:
            path: The git repo path
            machine: Machine ID ('local' or remote machine ID)
            prefix: Branch name prefix to filter by

        Returns:
            {existing: [branch names]}
        """
        path = request.query.get("path", "")
        machine = request.query.get("machine", "local")
        prefix = request.query.get("prefix", "")

        if not path:
            return web.json_response({"existing": []})

        if machine and machine != "local":
            # Remote branch check via SSH
            cmd = f"cd {shlex.quote(path)} && git branch --list {shlex.quote(prefix + '*')} --format='%(refname:short)'"
            result = await self._run_ssh_command(machine, cmd)
            branches = result.strip().split('\n') if result else []
        else:
            # Local branch check
            expanded = Path(path).expanduser().resolve()
            if not expanded.exists():
                return web.json_response({"existing": []})

            result = subprocess.run(
                ["git", "branch", "--list", f"{prefix}*", "--format=%(refname:short)"],
                cwd=expanded,
                capture_output=True,
                text=True
            )
            branches = result.stdout.strip().split('\n') if result.returncode == 0 else []

        # Filter out empty strings
        branches = [b for b in branches if b]

        return web.json_response({"existing": branches})

    async def api_create_session(self, request: web.Request) -> web.Response:
        """Create a new agent session via CLI.

        Request body:
            name: Base session/project name (required)
            path: Custom project path (optional, ignored if worktree=true)
            voice: TTS voice for this room
            bypass_permissions: Whether to skip permission prompts
            restricted: Whether to use restricted mode (only say/remote-say allowed)
            machine: Machine ID ('local' or remote machine ID)
            worktree: Whether to create a worktree session
            branch: Branch name for worktree sessions
            template: Template name to apply (optional)

        Session naming:
            - worktree + branch: project/branch (or project/branch@machine)
            - just machine: name@machine
            - neither: just name
        """
        try:
            data = await request.json()
            name = data.get("name", "").strip()
            custom_path = data.get("path")
            voice = data.get("voice", self.config.tts.default_voice)
            bypass_permissions = data.get("bypass_permissions", True)  # Default True
            restricted = data.get("restricted", False)  # Default False
            machine = data.get("machine", "local")
            worktree = data.get("worktree", False)
            branch = data.get("branch", "").strip()
            template_name = data.get("template")

            if not name:
                return web.json_response({"error": "Session name is required"})

            # Build session name for CLI based on parameters
            if machine and machine != "local":
                # Remote session
                if worktree and branch:
                    cli_session = f"{name}/{branch}@{machine}"
                else:
                    cli_session = f"{name}@{machine}"
            else:
                # Local session
                if worktree and branch:
                    cli_session = f"{name}/{branch}"
                else:
                    cli_session = name

            # Build CLI args
            args = ["new", "-s", cli_session]
            # Pass -p when provided (CLI uses it to locate repo for worktree creation)
            if custom_path:
                args.extend(["-p", custom_path])
            # Pass template if provided
            if template_name:
                args.extend(["-t", template_name])
            # Restricted mode implies --no-bypass (needs permission hook to work)
            if restricted:
                args.append("--restricted")
            elif not bypass_permissions:
                args.append("--no-bypass")

            # Call CLI
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to create session")
                return web.json_response({"error": error_msg})

            # CLI updates rooms.json with bypass_permissions/restricted and template voice
            # We may still need to set voice/path if user selected explicitly
            session_name = result.get("session", cli_session)
            session_path = result.get("path")
            configs = self._load_room_configs()
            if session_name not in configs:
                configs[session_name] = {}
            # Only set voice if explicitly provided (not using template default)
            if voice != self.config.tts.default_voice or not template_name:
                configs[session_name]["voice"] = voice
            # Save path from CLI result
            if session_path:
                configs[session_name]["path"] = session_path
            self._save_room_configs(configs)

            return web.json_response({"success": True, "name": session_name, "template": template_name})

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
            path = session_config.get("path", str(self.config.projects.dir / project))

            # Kill the tmux session via CLI (handles local and remote)
            success, result = await self.run_agentwire_cmd(["kill", "-s", name])
            if not success:
                error_msg = result.get("error", "Failed to close session")
                return web.json_response({"error": error_msg})

            # Archive the session
            import time
            archive = self._load_archive()
            archive.insert(0, {
                "name": name,
                "path": path,
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

    async def api_list_templates(self, request: web.Request) -> web.Response:
        """List available session templates."""
        from .config import load_templates

        templates = load_templates()
        return web.json_response([t.to_dict() for t in templates])

    async def api_get_template(self, request: web.Request) -> web.Response:
        """Get details of a specific template."""
        from .config import load_template

        name = request.match_info["name"]
        template = load_template(name)

        if template is None:
            return web.json_response({"error": f"Template '{name}' not found"}, status=404)

        return web.json_response(template.to_dict())

    async def api_create_template(self, request: web.Request) -> web.Response:
        """Create or update a session template."""
        from .config import Template, save_template, load_template

        try:
            data = await request.json()
            name = data.get("name", "").strip()

            if not name:
                return web.json_response({"error": "Template name is required"})

            # Check if it already exists and overwrite not specified
            if load_template(name) and not data.get("overwrite", False):
                return web.json_response({"error": f"Template '{name}' already exists. Set overwrite=true to replace."})

            template = Template(
                name=name,
                description=data.get("description", ""),
                role=data.get("role"),
                voice=data.get("voice"),
                project=data.get("project"),
                initial_prompt=data.get("initial_prompt", ""),
                bypass_permissions=data.get("bypass_permissions", True),
                restricted=data.get("restricted", False),
            )

            if save_template(template):
                return web.json_response({"success": True, "template": template.to_dict()})
            else:
                return web.json_response({"error": "Failed to save template"})

        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            return web.json_response({"error": str(e)})

    async def api_delete_template(self, request: web.Request) -> web.Response:
        """Delete a session template."""
        from .config import delete_template

        name = request.match_info["name"]

        if delete_template(name):
            return web.json_response({"success": True})
        else:
            return web.json_response({"error": f"Template '{name}' not found or failed to delete"}, status=404)

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

        In restricted mode, only say/remote-say commands are auto-allowed,
        everything else is auto-denied silently.
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

            # Check restricted mode - auto-handle without user interaction
            if room.config.restricted:
                # Parse session name to handle local vs remote
                project, branch, machine = parse_session_name(name)
                if branch:
                    tmux_session = f"{project}/{branch}".replace(".", "_")
                else:
                    tmux_session = project.replace(".", "_")

                if _is_allowed_in_restricted_mode(tool_name, tool_input):
                    # Auto-allow
                    logger.info(f"[{name}] Restricted mode: auto-allowing {tool_name}")
                    # Only send keystroke for Bash commands (say/remote-say)
                    # AskUserQuestion doesn't need permission keystroke
                    if tool_name == "Bash":
                        try:
                            if machine:
                                await self._run_ssh_command(machine, f"tmux send-keys -t {shlex.quote(tmux_session)} 2")
                            else:
                                subprocess.run(
                                    ["tmux", "send-keys", "-t", tmux_session, "2"],
                                    check=True, capture_output=True
                                )
                        except Exception as e:
                            logger.error(f"[{name}] Failed to send allow keystroke: {e}")
                    return web.json_response({"decision": "allow_always"})
                else:
                    # Auto-deny: send "Escape" keystroke (deny silently)
                    logger.info(f"[{name}] Restricted mode: auto-denying {tool_name}")
                    try:
                        if machine:
                            await self._run_ssh_command(machine, f"tmux send-keys -t {shlex.quote(tmux_session)} Escape")
                        else:
                            subprocess.run(
                                ["tmux", "send-keys", "-t", tmux_session, "Escape"],
                                check=True, capture_output=True
                            )
                    except Exception as e:
                        logger.error(f"[{name}] Failed to send deny keystroke: {e}")
                    return web.json_response({
                        "decision": "deny",
                        "message": "Restricted mode: only say/remote-say commands are allowed"
                    })

            # Create pending permission request (normal/prompted mode)
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

            # Send keystroke to tmux session to respond to Claude's interactive prompt
            # Get session name (strip @machine suffix if present)
            session_name = name.split("@")[0]

            try:
                import subprocess
                import time as sync_time

                if decision == "custom":
                    # Custom feedback: send "3", then message, then Enter
                    custom_message = data.get("message", "")
                    if custom_message:
                        subprocess.run(
                            ["tmux", "send-keys", "-t", session_name, "3"],
                            check=True, capture_output=True
                        )
                        sync_time.sleep(0.3)
                        subprocess.run(
                            ["tmux", "send-keys", "-t", session_name, custom_message],
                            check=True, capture_output=True
                        )
                        sync_time.sleep(0.3)
                        subprocess.run(
                            ["tmux", "send-keys", "-t", session_name, "Enter"],
                            check=True, capture_output=True
                        )
                        logger.info(f"[{name}] Sent custom feedback: {custom_message[:50]}...")
                else:
                    # Map decision to keystroke: allow=1, allow_always=2, deny=Escape
                    keystroke_map = {
                        "allow": "1",
                        "allow_always": "2",
                        "deny": "Escape",
                    }
                    keystroke = keystroke_map.get(decision, "Escape")
                    subprocess.run(
                        ["tmux", "send-keys", "-t", session_name, keystroke],
                        check=True, capture_output=True
                    )
                    logger.info(f"[{name}] Sent keystroke '{keystroke}' to session")
            except Exception as e:
                logger.error(f"[{name}] Failed to send keystroke: {e}")

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
        """POST /api/room/{name}/recreate - Destroy session/worktree and create fresh one via CLI."""
        name = request.match_info["name"]
        try:
            logger.info(f"[{name}] Recreating session...")

            # Get old config for inheriting settings (before CLI deletes it)
            configs = self._load_room_configs()
            old_config = configs.get(name, {})
            bypass_permissions = old_config.get("bypass_permissions", True)
            restricted = old_config.get("restricted", False)

            # Build CLI args
            args = ["recreate", "-s", name]
            if restricted:
                args.append("--restricted")
            elif not bypass_permissions:
                args.append("--no-bypass")

            # Call CLI - handles kill, worktree removal, git pull, new worktree, new session
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to recreate session")
                return web.json_response({"error": error_msg}, status=500)

            new_session_name = result.get("session", name)
            session_path = result.get("path")

            # Clean up old room state
            if name in self.rooms:
                room = self.rooms[name]
                if room.output_task:
                    room.output_task.cancel()
                del self.rooms[name]

            # CLI updates rooms.json with bypass_permissions, add voice and path
            configs = self._load_room_configs()
            if new_session_name not in configs:
                configs[new_session_name] = {}
            configs[new_session_name]["voice"] = old_config.get("voice", self.config.tts.default_voice)
            if session_path:
                configs[new_session_name]["path"] = session_path
            self._save_room_configs(configs)

            logger.info(f"[{name}] Session recreated as '{new_session_name}'")
            return web.json_response({"success": True, "session": new_session_name})

        except Exception as e:
            logger.error(f"Recreate session API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_spawn_sibling(self, request: web.Request) -> web.Response:
        """POST /api/room/{name}/spawn-sibling - Create a new session in same project via CLI.

        Creates a parallel session in a new worktree without destroying the current one.
        Useful for working on multiple features in the same project simultaneously.
        """
        name = request.match_info["name"]
        try:
            logger.info(f"[{name}] Spawning sibling session...")

            # Parse session name to get project and machine
            project, _, machine = parse_session_name(name)

            # Get old config for inheriting settings
            configs = self._load_room_configs()
            old_config = configs.get(name, {})
            bypass_permissions = old_config.get("bypass_permissions", True)
            restricted = old_config.get("restricted", False)

            # Build new session name: project/session-<timestamp>[@machine]
            new_branch = f"session-{int(time.time())}"
            new_session_name = f"{project}/{new_branch}"
            if machine:
                new_session_name = f"{new_session_name}@{machine}"

            # Build CLI args - use `agentwire new` with the sibling session name
            args = ["new", "-s", new_session_name]
            if restricted:
                args.append("--restricted")
            elif not bypass_permissions:
                args.append("--no-bypass")

            # Call CLI - handles worktree creation and session setup
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to create sibling session")
                return web.json_response({"error": error_msg}, status=500)

            session_name = result.get("session", new_session_name)
            session_path = result.get("path")

            # CLI updates rooms.json with bypass_permissions, add voice and path
            configs = self._load_room_configs()
            if session_name not in configs:
                configs[session_name] = {}
            configs[session_name]["voice"] = old_config.get("voice", self.config.tts.default_voice)
            if session_path:
                configs[session_name]["path"] = session_path
            self._save_room_configs(configs)

            logger.info(f"[{name}] Sibling session created: '{session_name}'")
            return web.json_response({"success": True, "session": session_name})

        except Exception as e:
            logger.error(f"Spawn sibling API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_fork_session(self, request: web.Request) -> web.Response:
        """POST /api/room/{name}/fork - Fork the Claude Code session via CLI.

        Creates a new session that continues from the current conversation context.
        """
        name = request.match_info["name"]
        try:
            # Get current room config for inheriting settings
            room_config = self._get_room_config(name)

            logger.info(f"[{name}] Forking session...")

            # Parse session name to get project and machine
            project, _, machine = parse_session_name(name)

            # Find next available fork number for target name
            configs = self._load_room_configs()
            fork_num = 1
            while True:
                candidate = f"{project}-fork-{fork_num}"
                if machine:
                    candidate = f"{candidate}@{machine}"
                if candidate not in configs and not self.agent.session_exists(candidate):
                    break
                fork_num += 1

            # Build target session name: project/fork-N[@machine]
            new_branch = f"fork-{fork_num}"
            target_session = f"{project}/{new_branch}"
            if machine:
                target_session = f"{target_session}@{machine}"

            # Build CLI args
            args = ["fork", "-s", name, "-t", target_session]
            if room_config.restricted:
                args.append("--restricted")
            elif not room_config.bypass_permissions:
                args.append("--no-bypass")

            # Call CLI - handles worktree creation and session setup
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to fork session")
                return web.json_response({"error": error_msg}, status=500)

            session_name = result.get("session", target_session)
            session_path = result.get("path")

            # CLI updates rooms.json with bypass_permissions, add voice and path
            configs = self._load_room_configs()
            if session_name not in configs:
                configs[session_name] = {}
            configs[session_name]["voice"] = room_config.voice
            if session_path:
                configs[session_name]["path"] = session_path
            self._save_room_configs(configs)

            logger.info(f"[{name}] Session forked as '{session_name}'")
            return web.json_response({"success": True, "session": session_name})

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
