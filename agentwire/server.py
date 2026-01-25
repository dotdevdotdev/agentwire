"""
AgentWire WebSocket server.

Multi-session voice web interface for AI coding agents.
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
import signal
import socket
import ssl
import struct
import subprocess
import tempfile
import termios
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import aiohttp_jinja2
import jinja2
from aiohttp import web

from .config import Config, load_config
from .worktree import parse_session_name

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


def _is_allowed_in_restricted_mode(tool_name: str, tool_input: dict) -> bool:
    """Check if command is allowed in restricted mode.

    Allows:
    - AskUserQuestion tool (for interactive prompts)
    - Bash: say "message"

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

    # Match: say or agentwire say followed by quoted string (optional & for background)
    # Allows: say "hello world"
    #         say 'hello world'
    #         agentwire say "hello world"
    #         agentwire say "hello world" &
    #         agentwire say -s session "hello world"
    # Rejects: say "hi" && rm -rf /
    #          say "hi" > /tmp/log
    #          say $(cat /etc/passwd)
    pattern = r'^(?:agentwire\s+)?say\s+(?:-[sv]\s+\S+\s+)*(["\']).*\1\s*&?\s*$'

    return bool(re.match(pattern, command))


@dataclass
class SessionConfig:
    """Runtime configuration for a session."""

    voice: str = "default"
    exaggeration: float = 0.5
    cfg_weight: float = 0.5
    machine: str | None = None
    path: str | None = None
    claude_session_id: str | None = None  # Claude Code session UUID for forking
    type: str = "claude-bypass"  # Session type: bare | claude-bypass | claude-prompted | claude-restricted
    roles: list = None  # Composable roles array
    spawned_by: str | None = None  # Parent session (for worker sessions)

    def __post_init__(self):
        if self.roles is None:
            self.roles = []


@dataclass
class PendingPermission:
    """A permission request waiting for user decision."""

    request: dict  # The permission request from Claude Code
    event: asyncio.Event = field(default_factory=asyncio.Event)  # Signals when user responds
    decision: dict | None = None  # The user's decision


@dataclass
class Session:
    """Active session with connected clients."""

    name: str
    config: SessionConfig
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
    """Main server managing sessions, WebSockets, and agent backends."""

    def __init__(self, config: Config):
        self.config = config
        self.active_sessions: dict[str, Session] = {}  # Active sessions with connected clients
        self.session_activity: dict[str, dict] = {}  # Global activity tracking for all sessions
        self.dashboard_clients: set = set()  # WebSocket clients for dashboard updates
        self.session_client_counts: dict[str, int] = {}  # Attached tmux client counts per session
        self.stt = None
        self.agent = None
        self._http_session: aiohttp.ClientSession | None = None  # For TTS HTTP calls
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
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/ws", self.handle_dashboard_ws)
        self.app.router.add_get("/ws/{name:.+}", self.handle_websocket)
        self.app.router.add_get("/ws/terminal/{name:.+}", self.handle_terminal_ws)
        self.app.router.add_get("/api/sessions", self.api_sessions)
        self.app.router.add_get("/api/sessions/local", self.api_sessions_local)
        self.app.router.add_get("/api/sessions/remote", self.api_sessions_remote)
        self.app.router.add_get("/api/projects", self.api_projects)
        self.app.router.add_get("/api/machine/{machine_id}/status", self.api_machine_status)
        self.app.router.add_get("/api/check-path", self.api_check_path)
        self.app.router.add_get("/api/check-branches", self.api_check_branches)
        self.app.router.add_post("/api/create", self.api_create_session)
        self.app.router.add_post("/api/session/{name:.+}/config", self.api_session_config)
        self.app.router.add_post("/transcribe", self.handle_transcribe)
        self.app.router.add_post("/upload", self.handle_upload)
        self.app.router.add_post("/send/{name:.+}", self.handle_send)
        self.app.router.add_post("/api/say/{name:.+}", self.api_say)
        self.app.router.add_get("/api/sessions/{name:.+}/connections", self.api_session_connections)
        self.app.router.add_post("/api/local-tts/{name:.+}", self.api_local_tts)
        self.app.router.add_post("/api/answer/{name:.+}", self.api_answer)
        self.app.router.add_post("/api/session/{name:.+}/recreate", self.api_recreate_session)
        self.app.router.add_post("/api/session/{name:.+}/spawn-sibling", self.api_spawn_sibling)
        self.app.router.add_post("/api/session/{name:.+}/fork", self.api_fork_session)
        self.app.router.add_post("/api/session/{name:.+}/restart-service", self.api_restart_service)
        self.app.router.add_get("/api/voices", self.api_voices)
        self.app.router.add_delete("/api/sessions/{name:.+}", self.api_close_session)
        self.app.router.add_get("/api/machines", self.api_machines)
        self.app.router.add_post("/api/machines", self.api_add_machine)
        self.app.router.add_delete("/api/machines/{machine_id}", self.api_remove_machine)
        self.app.router.add_get("/api/config", self.api_get_config)
        self.app.router.add_post("/api/config", self.api_save_config)
        self.app.router.add_post("/api/config/reload", self.api_reload_config)
        self.app.router.add_post("/api/sessions/refresh", self.api_refresh_sessions)
        # Permission request handling (from Claude Code hook)
        # Note: respond route must come first as aiohttp matches in order
        self.app.router.add_post("/api/permission/{name:.+}/respond", self.api_permission_respond)
        self.app.router.add_post("/api/permission/{name:.+}", self.api_permission_request)
        # History endpoints
        self.app.router.add_get("/api/history", self.api_history_list)
        self.app.router.add_get("/api/history/{session_id}", self.api_history_detail)
        self.app.router.add_post("/api/history/{session_id}/resume", self.api_history_resume)
        # Tmux hook notifications
        self.app.router.add_post("/api/notify", self.api_notify)
        self.app.router.add_static("/static", Path(__file__).parent / "static")

    async def init_backends(self):
        """Initialize TTS, STT, and agent backends."""
        # Convert config to dict for backend factories
        config_dict = {
            "tts": {
                "backend": self.config.tts.backend,
                "url": self.config.tts.url,
                "exaggeration": self.config.tts.exaggeration,
                "cfg_weight": self.config.tts.cfg_weight,
                "runpod_endpoint_id": self.config.tts.runpod_endpoint_id,
                "runpod_api_key": self.config.tts.runpod_api_key,
                "runpod_timeout": self.config.tts.runpod_timeout,
            },
            "stt": {
                "url": self.config.stt.url,
                "timeout": self.config.stt.timeout,
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

        try:
            self.stt = get_stt_backend(self.config)
        except ValueError as e:
            logger.warning(f"STT backend not available: {e}")
            from .stt import NoSTT

            self.stt = NoSTT()
        self.agent = get_agent_backend(config_dict)

        # Create HTTP session for TTS server calls
        self._http_session = aiohttp.ClientSession()

        logger.info(f"TTS URL: {self.config.tts.url}")
        logger.info(f"STT backend: {type(self.stt).__name__}")

    async def close_backends(self):
        """Clean up backend resources."""
        if self._http_session:
            await self._http_session.close()

    async def _tts_generate(
        self,
        text: str,
        voice: str,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> bytes | None:
        """Generate TTS audio via HTTP call to TTS server."""
        if not self._http_session:
            return None

        try:
            async with self._http_session.post(
                f"{self.config.tts.url}/tts",
                json={
                    "text": text,
                    "voice": voice,
                    "exaggeration": exaggeration,
                    "cfg_weight": cfg_weight,
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logger.warning(f"TTS request failed: {resp.status}")
                    return None
        except Exception as e:
            logger.warning(f"TTS request error: {e}")
            return None

    async def _tts_get_voices(self) -> list[str]:
        """Get available TTS voices via HTTP call to TTS server."""
        if not self._http_session:
            return [self.config.tts.default_voice]

        try:
            async with self._http_session.get(
                f"{self.config.tts.url}/voices",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("voices", [self.config.tts.default_voice])
                else:
                    return [self.config.tts.default_voice]
        except Exception as e:
            logger.warning(f"TTS voices request error: {e}")
            return [self.config.tts.default_voice]

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

    def _get_session_config(self, name: str) -> SessionConfig:
        """Get session config dynamically from .agentwire.yml in session's working directory.

        Uses cached config from active_sessions if available, otherwise looks up
        the session's working directory from tmux and reads .agentwire.yml.
        """
        # Check active_sessions first for cached config
        if name in self.active_sessions:
            return self.active_sessions[name].config

        # Parse name for machine
        machine_id = None
        base_name = name
        if "@" in name:
            base_name, machine_id = name.rsplit("@", 1)

        # Get working directory from tmux
        cwd = self._get_session_cwd(base_name, machine_id)
        if not cwd:
            return SessionConfig(voice=self.config.tts.default_voice)

        # Read .agentwire.yml from that path
        yaml_config = self._read_agentwire_yaml(cwd, machine_id)
        if not yaml_config:
            return SessionConfig(voice=self.config.tts.default_voice)

        return SessionConfig(
            type=yaml_config.get("type", "claude-bypass"),
            roles=yaml_config.get("roles", []),
            voice=yaml_config.get("voice", self.config.tts.default_voice),
        )

    def _get_session_cwd(self, session_name: str, machine_id: str | None = None) -> str | None:
        """Get working directory of a tmux session.

        Args:
            session_name: Base session name (without @machine suffix)
            machine_id: Machine ID if remote, None for local

        Returns:
            Working directory path, or None if session not found
        """
        import socket
        local_hostname = socket.gethostname().split('.')[0]

        # Check if this is a local session
        is_local = machine_id is None or machine_id == "local" or machine_id == local_hostname

        if is_local:
            # Local tmux lookup
            result = subprocess.run(
                ["tmux", "display-message", "-t", session_name, "-p", "#{pane_current_path}"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        else:
            # Remote tmux lookup via SSH
            machine = self._get_machine_config(machine_id)
            if not machine:
                return None

            host = machine.get("host", "")
            user = machine.get("user", "")
            ssh_target = f"{user}@{host}" if user else host

            try:
                cmd = f"tmux display-message -t {shlex.quote(session_name)} -p '#{{pane_current_path}}'"
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", ssh_target, cmd],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, Exception):
                pass
            return None

    def _get_machine_config(self, machine_id: str) -> dict | None:
        """Get machine config by ID from machines.json."""
        if hasattr(self.agent, 'machines'):
            for m in self.agent.machines:
                if m.get('id') == machine_id:
                    return m
        return None

    def _read_agentwire_yaml(self, cwd: str, machine_id: str | None = None) -> dict | None:
        """Read .agentwire.yml from a directory.

        Args:
            cwd: Working directory path
            machine_id: Machine ID if remote, None for local

        Returns:
            Parsed YAML dict, or None if not found/invalid
        """
        import socket

        import yaml
        local_hostname = socket.gethostname().split('.')[0]

        is_local = machine_id is None or machine_id == "local" or machine_id == local_hostname

        if is_local:
            yaml_path = Path(cwd) / ".agentwire.yml"
            if yaml_path.exists():
                try:
                    with open(yaml_path) as f:
                        return yaml.safe_load(f) or {}
                except Exception:
                    pass
            return None
        else:
            # Remote read via SSH
            machine = self._get_machine_config(machine_id)
            if not machine:
                return None

            host = machine.get("host", "")
            user = machine.get("user", "")
            ssh_target = f"{user}@{host}" if user else host

            try:
                yaml_path = f"{cwd}/.agentwire.yml"
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", ssh_target, f"cat {shlex.quote(yaml_path)}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return yaml.safe_load(result.stdout) or {}
            except (subprocess.TimeoutExpired, Exception):
                pass
            return None

    def _write_agentwire_yaml(self, cwd: str, data: dict, machine_id: str | None = None) -> bool:
        """Write .agentwire.yml to a directory.

        Args:
            cwd: Working directory path
            data: YAML data to write
            machine_id: Machine ID if remote, None for local

        Returns:
            True if written successfully, False otherwise
        """
        import socket

        import yaml
        local_hostname = socket.gethostname().split('.')[0]

        is_local = machine_id is None or machine_id == "local" or machine_id == local_hostname

        if is_local:
            yaml_path = Path(cwd) / ".agentwire.yml"
            try:
                with open(yaml_path, "w") as f:
                    yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
                return True
            except Exception as e:
                logger.warning(f"Failed to write {yaml_path}: {e}")
                return False
        else:
            # Remote write via SSH
            machine = self._get_machine_config(machine_id)
            if not machine:
                return False

            host = machine.get("host", "")
            user = machine.get("user", "")
            ssh_target = f"{user}@{host}" if user else host

            try:
                yaml_content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
                yaml_path = f"{cwd}/.agentwire.yml"
                # Use base64 encoding for safe content transmission (avoids heredoc injection)
                encoded = base64.b64encode(yaml_content.encode()).decode()
                cmd = f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(yaml_path)}"
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", ssh_target, cmd],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.returncode == 0
            except (subprocess.TimeoutExpired, Exception) as e:
                logger.warning(f"Failed to write remote yaml: {e}")
                return False

    async def _get_voices(self) -> list[str]:
        """Get available TTS voices."""
        return await self._tts_get_voices()

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

    async def handle_index(self, request: web.Request) -> web.Response:
        """Serve the desktop UI."""
        voices = await self._get_voices()
        context = {
            "version": __version__,
            "voices": voices,
            "default_voice": self.config.tts.default_voice,
        }
        response = aiohttp_jinja2.render_template("desktop.html", request, context)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    async def handle_dashboard_ws(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket endpoint for dashboard updates (sessions, machines, config)."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.dashboard_clients.add(ws)
        logger.info(f"Dashboard client connected (total: {len(self.dashboard_clients)})")

        # Send initial state
        try:
            sessions_data = await self._get_sessions_data()
            await ws.send_json({"type": "sessions_update", "sessions": sessions_data})

            machines_data = await self._get_machines_data()
            await ws.send_json({"type": "machines_update", "machines": machines_data})
        except Exception as e:
            logger.error(f"Failed to send initial dashboard state: {e}")

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_dashboard_message(ws, data)
                    except json.JSONDecodeError:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"Dashboard WebSocket error: {ws.exception()}")
        finally:
            self.dashboard_clients.discard(ws)
            logger.info(f"Dashboard client disconnected (total: {len(self.dashboard_clients)})")

        return ws

    async def _handle_dashboard_message(self, ws: web.WebSocketResponse, data: dict):
        """Handle messages from dashboard clients."""
        msg_type = data.get("type")

        if msg_type == "refresh_sessions":
            sessions_data = await self._get_sessions_data()
            await ws.send_json({"type": "sessions_update", "sessions": sessions_data})

        elif msg_type == "refresh_machines":
            machines_data = await self._get_machines_data()
            await ws.send_json({"type": "machines_update", "machines": machines_data})

    async def _get_sessions_data(self) -> list:
        """Get local sessions list for dashboard (fast, no SSH)."""
        try:
            success, result = await self.run_agentwire_cmd(["list", "--local", "--sessions"])
            if not success:
                return []

            sessions = result.get("sessions", [])
            session_names = set()
            for s in sessions:
                name = s.get("name", "")
                session_names.add(name)
                s["activity"] = self._get_global_session_activity(name)
                # Include attached client count for presence indicator
                s["client_count"] = self.session_client_counts.get(name, 0)

            # Clean up stale state for sessions that no longer exist
            stale = [k for k in self.session_client_counts if k not in session_names]
            for k in stale:
                del self.session_client_counts[k]

            return sessions
        except Exception as e:
            logger.error(f"Failed to get sessions data: {e}")
            return []

    async def _get_machines_data(self) -> list:
        """Get machines list (without slow SSH status checks)."""
        try:
            machines = []
            if hasattr(self.agent, 'machines'):
                for m in self.agent.machines:
                    machines.append({
                        "id": m.get("id"),
                        "host": m.get("host"),
                        "status": "unknown",  # Don't check SSH on initial load
                    })
            return machines
        except Exception as e:
            logger.error(f"Failed to get machines data: {e}")
            return []

    async def broadcast_dashboard(self, msg_type: str, data: dict):
        """Broadcast a message to all connected dashboard clients."""
        if not self.dashboard_clients:
            return

        message = {"type": msg_type, **data}
        closed = []

        for ws in self.dashboard_clients:
            try:
                await ws.send_json(message)
            except Exception:
                closed.append(ws)

        for ws in closed:
            self.dashboard_clients.discard(ws)

    def _get_system_session_names(self) -> dict[str, str]:
        """Get system session names from config."""
        services = self.config.raw.get("services", {})
        return {
            "portal": services.get("portal", {}).get("session_name", "agentwire-portal"),
            "tts": services.get("tts", {}).get("session_name", "agentwire-tts"),
            "stt": services.get("stt", {}).get("session_name", "agentwire-stt"),
            "main": "agentwire",  # Main session name is always "agentwire"
        }

    def _is_system_session(self, name: str) -> bool:
        """Check if this is a system session (agentwire services)."""
        # Extract base session name (without @machine suffix)
        base_name = name.split("@")[0]
        session_names = self._get_system_session_names()
        return base_name in session_names.values()

    def _get_session_activity_status(self, session: Session) -> str:
        """Calculate activity status based on last output timestamp.

        Returns:
            "active" if output changed within threshold, "idle" otherwise
        """
        if session.last_output_timestamp == 0.0:
            return "idle"

        time_since_last_output = time.time() - session.last_output_timestamp
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

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for a session."""
        name = request.match_info["name"]
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Get or create session
        if name not in self.active_sessions:
            self.active_sessions[name] = Session(name=name, config=self._get_session_config(name))

        session = self.active_sessions[name]
        client_id = str(id(ws))
        session.clients.add(ws)
        logger.info(f"[{name}] Client connected (total: {len(session.clients)})")

        # Skip tmux polling for special sessions that aren't real tmux sessions
        is_real_session = name != "dashboard"

        # Send current output immediately on connect (if this is a real session)
        if is_real_session:
            try:
                output = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.agent.get_output(name, lines=100)
                )
                if output:
                    session.last_output = output
                    await ws.send_json({"type": "output", "data": output})
            except Exception as e:
                logger.debug(f"Initial output fetch failed for {name}: {e}")

            # Start output polling if not running
            if session.output_task is None or session.output_task.done():
                session.output_task = asyncio.create_task(self._poll_output(session))

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_ws_message(session, ws, client_id, data)
                    except json.JSONDecodeError:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            session.clients.discard(ws)
            if session.locked_by == client_id:
                session.locked_by = None
                await self._broadcast(session, {"type": "session_unlocked"})

        return ws

    async def handle_terminal_ws(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket endpoint for interactive terminal via tmux attach.

        Provides bidirectional communication between browser terminal (xterm.js)
        and tmux session. Handles terminal input, output, and resize commands.
        """
        session_name = request.match_info["name"]
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        proc = None
        master_fd = None
        tmux_to_ws_task = None
        ws_to_tmux_task = None

        # Track this connection for TTS routing (so audio goes to browser, not local speakers)
        if session_name not in self.active_sessions:
            self.active_sessions[session_name] = Session(name=session_name, config=self._get_session_config(session_name))
        session = self.active_sessions[session_name]
        session.clients.add(ws)
        logger.info(f"[Terminal] Client connected to {session_name} (total: {len(session.clients)})")

        try:
            # Parse session name for local vs remote
            project, branch, machine_id = parse_session_name(session_name)
            session_name = f"{project}/{branch}" if branch else project

            # Build tmux attach command
            # Check if this is a remote machine (needs SSH)
            is_remote = False
            if machine_id:
                machine_config = self._get_machine_config(machine_id)
                if not machine_config:
                    logger.error(f"[Terminal] Machine not found: {machine_id}")
                    await ws.close()
                    return ws
                # Only use SSH if machine is not marked as local
                is_remote = not machine_config.get("local", False)

            if is_remote:
                ssh_host = machine_config.get("host", machine_id)
                ssh_user = machine_config.get("user")
                ssh_target = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host

                # Remote session via SSH with PTY allocation
                # Use accept-new to accept new host keys but reject changed ones (MITM protection)
                cmd = ["ssh", "-t", "-o", "StrictHostKeyChecking=accept-new", ssh_target, "tmux", "attach", "-t", session_name]
                logger.info(f"[Terminal] Attaching to {session_name}: {' '.join(cmd)}")

                # Create PTY for SSH too (ssh -t needs local PTY)
                master_fd, slave_fd = pty.openpty()

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    preexec_fn=os.setsid,
                )

                os.close(slave_fd)
                os.set_blocking(master_fd, False)

                # Send initial window size to trigger tmux redraw
                winsize = struct.pack("HHHH", 24, 80, 0, 0)
                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                logger.info(f"[Terminal] Set initial PTY size for SSH to 80x24 (fd={master_fd})")
            else:
                # Local session - use PTY
                cmd = ["tmux", "attach", "-t", session_name]
                logger.info(f"[Terminal] Attaching to {session_name}: {' '.join(cmd)}")

                # Create PTY for local tmux attach
                master_fd, slave_fd = pty.openpty()

                # Setup function to make PTY the controlling terminal
                def setup_pty_session():
                    os.setsid()  # Create new session (required first)
                    # Make the PTY the controlling terminal
                    fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

                # Spawn process with slave PTY as stdin/stdout/stderr
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    preexec_fn=setup_pty_session,
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
                        logger.debug(f"[Terminal] on_readable callback: read {len(data) if data else 0} bytes")
                        if data:
                            # Schedule putting data in queue from event loop
                            asyncio.create_task(data_queue.put(data))
                        else:
                            # Empty read = EOF (process exited)
                            logger.info(f"[Terminal] PTY EOF (empty read) for {session_name}")
                            asyncio.create_task(data_queue.put(None))
                    except OSError as e:
                        logger.info(f"[Terminal] PTY read error: {e}")
                        # Signal EOF
                        asyncio.create_task(data_queue.put(None))

                try:
                    if master_fd is not None:
                        # Local: register reader once for PTY master
                        loop.add_reader(master_fd, on_readable)
                        reader_registered = True
                        logger.info(f"[Terminal] Registered PTY reader for {session_name} (fd={master_fd})")

                    while True:
                        if master_fd is not None:
                            # Local: read from queue populated by on_readable
                            data = await data_queue.get()
                            if data is None:  # EOF signal
                                logger.info(f"[Terminal] Received EOF from PTY for {session_name}")
                                # For remote sessions, check exit code to determine message type
                                if is_remote and not ws.closed:
                                    try:
                                        # Wait for SSH process to exit and get return code
                                        exit_code = await proc.wait() if proc else None
                                        logger.info(f"[Terminal] SSH exit code for {session_name}: {exit_code}")

                                        if exit_code == 0:
                                            # Clean exit - tmux session ended normally, close window
                                            await ws.send_json({"type": "remote_session_ended", "session": session_name})
                                            logger.info(f"[Terminal] Sent remote_session_ended to browser for {session_name}")
                                        else:
                                            # Non-zero exit - connection issue, show reconnect overlay
                                            await ws.send_json({"type": "remote_disconnected", "session": session_name})
                                            logger.info(f"[Terminal] Sent remote_disconnected to browser for {session_name}")
                                    except Exception as e:
                                        logger.warning(f"[Terminal] Failed to send disconnect message: {e}")
                                break
                            logger.debug(f"[Terminal] Read {len(data)} bytes from PTY for {session_name}")
                            if not ws.closed:
                                await ws.send_bytes(data)
                                logger.debug(f"[Terminal] Sent {len(data)} bytes to WebSocket for {session_name}")
                        else:
                            # Remote: read from subprocess stdout
                            data = await proc.stdout.read(8192)
                            if not data:
                                break
                            if not ws.closed:
                                await ws.send_bytes(data)
                except asyncio.CancelledError:
                    logger.debug(f"[Terminal] tmux→ws task cancelled for {session_name}")
                except Exception as e:
                    logger.error(f"[Terminal] Error forwarding tmux→ws for {session_name}: {e}")
                finally:
                    if master_fd is not None and reader_registered:
                        try:
                            loop.remove_reader(master_fd)
                            logger.info(f"[Terminal] Unregistered PTY reader for {session_name}")
                        except Exception:
                            pass

            # Task: Forward WebSocket → tmux stdin
            async def forward_ws_to_tmux():
                """Read from WebSocket and write to tmux stdin."""
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
                                    logger.info(f"[Terminal] Resize {session_name} to {cols}x{rows}")

                                    if master_fd is not None:
                                        # Local: use TIOCSWINSZ ioctl to resize PTY
                                        winsize = struct.pack("HHHH", rows, cols, 0, 0)
                                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                                        # Send SIGWINCH to notify tmux of size change
                                        if proc and proc.pid:
                                            try:
                                                os.kill(proc.pid, signal.SIGWINCH)
                                            except (OSError, ProcessLookupError):
                                                pass  # Process may have exited
                                        # Force tmux to resize window to fit largest client
                                        resize_proc = await asyncio.create_subprocess_exec(
                                            "tmux", "resize-window", "-a", "-t", session_name,
                                            stdout=asyncio.subprocess.DEVNULL,
                                            stderr=asyncio.subprocess.DEVNULL,
                                        )
                                        await resize_proc.wait()
                                    else:
                                        # Remote: send tmux resize-window command
                                        resize_cmd = f"tmux resize-window -t {session_name} -x {cols} -y {rows}\n"
                                        resize_proc = await asyncio.create_subprocess_exec(
                                            "ssh", ssh_target, "sh", "-c", resize_cmd,
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
                    logger.debug(f"[Terminal] ws→tmux task cancelled for {session_name}")
                except Exception as e:
                    logger.error(f"[Terminal] Error forwarding ws→tmux for {session_name}: {e}")

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

            logger.info(f"[Terminal] Disconnected from {session_name}")

        except FileNotFoundError:
            logger.error("[Terminal] tmux command not found")
            if not ws.closed:
                await ws.send_json({
                    "type": "error",
                    "message": "tmux not found on system"
                })

        except Exception as e:
            logger.error(f"[Terminal] Error attaching to {session_name}: {e}")
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

            # Remove client from session tracking
            session.clients.discard(ws)
            logger.info(f"[Terminal] Client disconnected from {session.name} (remaining: {len(session.clients)})")

        return ws

    async def _handle_ws_message(
        self, session: Session, ws: web.WebSocketResponse, client_id: str, data: dict
    ):
        """Handle incoming WebSocket messages."""
        msg_type = data.get("type")

        if msg_type == "recording_started":
            # Try to lock the session
            if session.locked_by is None:
                session.locked_by = client_id
                # Notify others
                for client in session.clients:
                    if client != ws:
                        try:
                            await client.send_json({"type": "session_locked"})
                        except Exception:
                            pass

        elif msg_type == "recording_stopped":
            # Unlock will happen after TTS completes or on disconnect
            pass

        elif msg_type == "resize":
            # Resize tmux pane for monitor mode (so captured output fits the viewer)
            cols = data.get("cols", 80)
            rows = data.get("rows", 24)
            logger.info(f"[{session.name}] Resize request: {cols}x{rows}")
            # Note: Resizing won't reformat existing scrollback content.
            # For proper display, use terminal mode (Connect) instead of monitor mode.

    # Patterns for say command detection
    # Matches: say "text", agentwire say "text", agentwire say -s session "text"
    SAY_PATTERN = re.compile(r'(?:agentwire\s+)?say\s+(?:-s\s+\S+\s+)?(?:"([^"]+)"|\'([^\']+)\')', re.IGNORECASE)
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

    async def _poll_output(self, session: Session):
        """Poll agent output and broadcast to session clients."""
        while session.clients:
            try:
                # Run sync get_output in thread pool to avoid blocking
                output = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.agent.get_output(session.name, lines=100)
                )
                if output != session.last_output:
                    old_output = session.last_output
                    session.last_output = output
                    timestamp = time.time()
                    session.last_output_timestamp = timestamp  # Update activity timestamp

                    # Also update global activity tracking (persists across session create/destroy)
                    self.session_activity[session.name] = {
                        "last_output_timestamp": timestamp,
                        "last_output": output,
                    }

                    await self._broadcast(session, {"type": "output", "data": output})

                    # Notify clients that agent is actively working
                    if old_output:  # Skip first poll
                        await self._broadcast(session, {"type": "activity"})
                        # Also notify dashboard clients
                        await self.broadcast_dashboard("session_activity", {
                            "session": session.name,
                            "active": True
                        })

                    # Note: TTS detection removed - agentwire say CLI calls /api/say directly

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

                    if question_key != session.last_question and options:
                        session.last_question = question_key
                        logger.info(f"[{session.name}] Question: {question[:50]}...")

                        await self._broadcast(session, {
                            "type": "question",
                            "header": header,
                            "question": question,
                            "options": options,
                        })

                elif session.last_question and not ask_match:
                    # Question was answered (UI disappeared)
                    session.last_question = None
                    await self._broadcast(session, {"type": "question_answered"})

                # Check for activity status transitions
                current_status = self._get_session_activity_status(session)
                new_is_active = current_status == "active"

                # Broadcast transition event if state changed
                if new_is_active != session.is_active:
                    session.is_active = new_is_active
                    await self._broadcast(session, {
                        "type": "session_activity",
                        "session": session.name,
                        "active": new_is_active
                    })
                    logger.info(f"[{session.name}] Activity transition: {'active' if new_is_active else 'idle'}")

            except Exception as e:
                logger.debug(f"Output poll error for {session.name}: {e}")

            await asyncio.sleep(0.5)

    async def _broadcast(self, session: Session, message: dict):
        """Broadcast message to all session clients."""
        dead_clients = set()
        for client in session.clients:
            try:
                await client.send_json(message)
            except Exception:
                dead_clients.add(client)
        session.clients -= dead_clients

    # API Handlers

    async def api_sessions(self, request: web.Request) -> web.Response:
        """List all active sessions grouped by machine via CLI."""
        try:
            # Get local sessions via CLI
            local_success, local_result = await self.run_agentwire_cmd(["list", "--local", "--sessions"])
            local_sessions = local_result.get("sessions", []) if local_success else []

            # Get remote sessions via CLI (includes SSH checks)
            remote_success, remote_result = await self.run_agentwire_cmd(["list", "--remote", "--sessions"])
            remote_sessions = remote_result.get("sessions", []) if remote_success else []

            # Combine and add activity status
            all_sessions = local_sessions + remote_sessions
            for s in all_sessions:
                s["activity"] = self._get_global_session_activity(s.get("name", ""))

            # Group sessions by machine
            machine_sessions = {}
            for s in all_sessions:
                machine_id = s.get("machine") or "local"  # Handle null/None
                if machine_id not in machine_sessions:
                    machine_sessions[machine_id] = []
                machine_sessions[machine_id].append(s)

            # Build machine list
            machines = []
            for machine_id, sessions_list in machine_sessions.items():
                machines.append({
                    "id": machine_id,
                    "host": machine_id,
                    "status": "online",  # If we got sessions, machine is online
                    "session_count": len(sessions_list),
                    "sessions": sessions_list,
                })

            # Sort machines: local first, then others alphabetically
            machines.sort(key=lambda m: (m["id"] != "local" and not m["id"].endswith(socket.gethostname().split('.')[0]), m["id"]))

            return web.json_response({"machines": machines})
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return web.json_response({"machines": []})

    async def api_sessions_local(self, request: web.Request) -> web.Response:
        """Fast endpoint for local sessions only (no SSH checks)."""
        try:
            success, result = await self.run_agentwire_cmd(["list", "--local", "--sessions"])
            if not success:
                return web.json_response({"sessions": []})

            sessions = result.get("sessions", [])
            # Add activity status
            for s in sessions:
                s["activity"] = self._get_global_session_activity(s.get("name", ""))

            return web.json_response({"sessions": sessions})
        except Exception as e:
            logger.error(f"Failed to list local sessions: {e}")
            return web.json_response({"sessions": []})

    async def api_sessions_remote(self, request: web.Request) -> web.Response:
        """Endpoint for remote sessions grouped by machine (includes SSH checks)."""
        try:
            success, result = await self.run_agentwire_cmd(["list", "--remote", "--sessions"])
            if not success:
                return web.json_response({"machines": []})

            sessions = result.get("sessions", [])

            # Group by machine and add activity status
            machines_dict = {}
            for s in sessions:
                machine_id = s.get("machine", "unknown")
                if machine_id not in machines_dict:
                    machines_dict[machine_id] = []
                s["activity"] = self._get_global_session_activity(s.get("name", ""))
                machines_dict[machine_id].append(s)

            machines = [
                {"id": mid, "sessions": sess}
                for mid, sess in machines_dict.items()
            ]

            return web.json_response({"machines": machines})
        except Exception as e:
            logger.error(f"Failed to list remote sessions: {e}")
            return web.json_response({"machines": []})

    async def api_projects(self, request: web.Request) -> web.Response:
        """List discovered projects.

        Query params:
            machine: Optional machine ID to filter by (e.g., 'local', 'mac-studio')

        Response:
            {"projects": [{name, path, type, roles, machine}, ...]}
        """
        try:
            args = ["projects", "list", "--json"]

            # Add machine filter if provided
            machine = request.query.get("machine")
            if machine:
                args.extend(["--machine", machine])

            success, result = await self.run_agentwire_cmd(args)
            if not success:
                return web.json_response({"projects": []})

            return web.json_response({"projects": result.get("projects", [])})
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return web.json_response({"projects": []})

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
            voice: TTS voice for this session
            type: Session type (claude-bypass | claude-prompted | claude-restricted | opencode-bypass | opencode-prompted | opencode-restricted | bare)
            roles: Comma-separated list of roles (e.g., "agentwire,worker")
            machine: Machine ID ('local' or remote machine ID)
            worktree: Whether to create a worktree session
            branch: Branch name for worktree sessions

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
            session_type = data.get("type", "claude-bypass")
            roles = data.get("roles")
            machine = data.get("machine", "local")
            worktree = data.get("worktree", False)
            branch = data.get("branch", "").strip()

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
            # Set session type via --type flag
            args.extend(["--type", session_type])
            # Set roles if provided
            if roles:
                args.extend(["--roles", roles])

            # Call CLI
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to create session")
                return web.json_response({"error": error_msg})

            session_name = result.get("session", cli_session)
            session_path = result.get("path")

            # CLI writes .agentwire.yml with type
            # If user explicitly selected a voice, update it
            if session_path and voice != self.config.tts.default_voice:
                # Parse session name for machine
                machine_id = None
                if "@" in session_name:
                    _, machine_id = session_name.rsplit("@", 1)

                # Read and update .agentwire.yml
                yaml_config = self._read_agentwire_yaml(session_path, machine_id) or {}
                yaml_config["voice"] = voice
                self._write_agentwire_yaml(session_path, yaml_config, machine_id)

            # Broadcast session created to dashboard clients
            await self.broadcast_dashboard("session_created", {"session": session_name})
            sessions_data = await self._get_sessions_data()
            await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            return web.json_response({"success": True, "name": session_name})

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return web.json_response({"error": str(e)})

    async def api_close_session(self, request: web.Request) -> web.Response:
        """Close/kill a session."""
        name = request.match_info["name"]
        try:
            # Kill the tmux session via CLI (handles local and remote)
            success, result = await self.run_agentwire_cmd(["kill", "-s", name])
            if not success:
                error_msg = result.get("error", "Failed to close session")
                return web.json_response({"error": error_msg})

            # Clean up session if exists
            if name in self.active_sessions:
                session = self.active_sessions[name]
                if session.output_task:
                    session.output_task.cancel()
                del self.active_sessions[name]

            # Broadcast session closed to dashboard clients
            await self.broadcast_dashboard("session_closed", {"session": name})
            sessions_data = await self._get_sessions_data()
            await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Failed to close session: {e}")
            return web.json_response({"error": str(e)})

    async def api_session_config(self, request: web.Request) -> web.Response:
        """Update session configuration (voice only).

        Edits the project's .agentwire.yml directly.
        """
        name = request.match_info["name"]
        try:
            data = await request.json()

            # Only voice is configurable via UI now
            if "voice" not in data:
                return web.json_response({"error": "No voice specified"}, status=400)

            voice = data["voice"]

            # Parse session name for machine
            machine_id = None
            base_name = name
            if "@" in name:
                base_name, machine_id = name.rsplit("@", 1)

            # Get session's working directory
            cwd = self._get_session_cwd(base_name, machine_id)
            if not cwd:
                return web.json_response({"error": "Session working directory not found"}, status=404)

            # Read existing .agentwire.yml (or create new)
            yaml_config = self._read_agentwire_yaml(cwd, machine_id) or {}

            # Update voice
            yaml_config["voice"] = voice

            # Write back
            if not self._write_agentwire_yaml(cwd, yaml_config, machine_id):
                return web.json_response({"error": "Failed to write .agentwire.yml"}, status=500)

            # Update live session if exists
            if name in self.active_sessions:
                self.active_sessions[name].config.voice = voice

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

            # No sessions.json to clean up - config is now in .agentwire.yml per project

            # Reload agent backend to pick up changes
            if self.agent and hasattr(self.agent, '_load_machines'):
                self.agent._load_machines()

            return web.json_response({
                "success": True,
                "machine_id": machine_id,
            })

        except Exception as e:
            logger.error(f"Failed to remove machine: {e}")
            return web.json_response({"error": str(e)})

    async def api_get_config(self, request: web.Request) -> web.Response:
        """Get config file contents or display format.

        Query params:
            format=display - Return key/value pairs for UI display
        """
        # Check if display format requested
        if request.query.get("format") == "display":
            # Return flattened key/value pairs from current config
            items = [
                {"key": "TTS Backend", "value": self.config.tts.backend},
                {"key": "TTS URL", "value": self.config.tts.url},
                {"key": "TTS Default Voice", "value": self.config.tts.default_voice},
                {"key": "STT URL", "value": self.config.stt.url},
                {"key": "Server Host", "value": self.config.server.host},
                {"key": "Server Port", "value": self.config.server.port},
                {"key": "SSL Enabled", "value": self.config.server.ssl.enabled},
                {"key": "Projects Directory", "value": str(self.config.projects.dir)},
                {"key": "Worktrees Enabled", "value": self.config.projects.worktrees.enabled},
                {"key": "Worktrees Suffix", "value": self.config.projects.worktrees.suffix},
                {"key": "Agent Command", "value": self.config.agent.command},
                {"key": "Machines File", "value": str(self.config.machines.file)},
            ]
            return web.json_response({"items": items})

        # Default: return raw config file contents
        config_path = Path.home() / ".agentwire" / "config.yaml"
        content = ""
        if config_path.exists():
            try:
                content = config_path.read_text()
                # SECURITY: Redact sensitive fields before returning
                # Matches patterns like: runpod_api_key: "secret" or runpod_api_key: secret
                content = re.sub(
                    r'(runpod_api_key\s*:\s*)["\']?[^"\'\n]+["\']?',
                    r'\1"[REDACTED]"',
                    content
                )
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
  default_voice: "dotdev"

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

    async def api_refresh_sessions(self, request: web.Request) -> web.Response:
        """Refresh sessions and broadcast update to all dashboard clients.

        Called by CLI commands (like `agentwire kill`) to notify portal of changes.
        """
        try:
            sessions_data = await self._get_sessions_data()
            await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})
            return web.json_response({
                "success": True,
                "sessions": len(sessions_data),
            })
        except Exception as e:
            logger.error(f"Failed to refresh sessions: {e}")
            return web.json_response({"error": str(e)}, status=500)

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
                logger.info("Converting webm to wav: %s -> %s", webm_path, wav_path)
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
                logger.info("Transcribing %s via %s backend", wav_path, type(self.stt).__name__)
                text = await self.stt.transcribe(Path(wav_path))
                logger.info("Transcription result: %s", text)
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
        """Send text to an agent session via CLI."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            text = data.get("text", "").strip()

            if not text:
                return web.json_response({"error": "No text provided"})

            # Use CLI: agentwire send -s <session> <text>
            success, result = await self.run_agentwire_cmd(["send", "-s", name, text])

            if not success:
                error_msg = result.get("error", "Failed to send to session")
                return web.json_response({"error": error_msg})

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

    async def _say_to_room(self, session_name: str, text: str):
        """Generate TTS audio and send to session clients (internal)."""
        await self.speak(session_name, text)

    async def api_say(self, request: web.Request) -> web.Response:
        """POST /api/say/{session} - Generate TTS and broadcast to session."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            text = data.get("text", "").strip()

            if not text:
                return web.json_response({"error": "No text provided"}, status=400)

            # Ensure session exists (create if not)
            if name not in self.active_sessions:
                self.active_sessions[name] = Session(name=name, config=self._get_session_config(name))

            session = self.active_sessions[name]

            # Track this text to avoid duplicate TTS from output polling
            session.played_says.add(text)
            if len(session.played_says) > 50:
                session.played_says = set(list(session.played_says)[-25:])

            logger.info(f"[{name}] API say: {text[:50]}...")

            # Generate and broadcast TTS in background (don't block the API response)
            asyncio.create_task(self.speak(name, text))

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Say API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_session_connections(self, request: web.Request) -> web.Response:
        """GET /api/sessions/{session}/connections - Check if session has active browser connections."""
        name = request.match_info["name"]
        try:
            has_connections = False
            connection_count = 0

            if name in self.active_sessions:
                session = self.active_sessions[name]
                connection_count = len(session.clients)
                has_connections = connection_count > 0

            return web.json_response({
                "has_connections": has_connections,
                "connection_count": connection_count
            })

        except Exception as e:
            logger.error(f"Session connections check failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_local_tts(self, request: web.Request) -> web.Response:
        """POST /api/local-tts/{session} - Generate TTS and return audio for local playback."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            text = data.get("text", "").strip()
            voice = data.get("voice")

            if not text:
                return web.json_response({"error": "No text provided"}, status=400)

            # Get session config for defaults
            session_config = self._get_session_config(name)
            if voice is None:
                voice = session_config.voice
            exaggeration = session_config.exaggeration
            cfg_weight = session_config.cfg_weight

            logger.info(f"[{name}] Local TTS: {text[:50]}... (voice={voice})")

            # Generate audio via TTS server HTTP call
            audio_data = await self._tts_generate(
                text=text,
                voice=voice,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
            )

            if not audio_data:
                return web.json_response(
                    {"success": False, "error": "TTS generation returned no audio"},
                    status=500
                )

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            try:
                temp_file.write(audio_data)
                temp_path = temp_file.name
                temp_file.close()

                # Play audio (platform-specific)
                import sys
                if sys.platform == "darwin":
                    # macOS: use afplay
                    proc = await asyncio.create_subprocess_exec(
                        "afplay", temp_path,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    await proc.wait()
                elif sys.platform == "linux":
                    # Linux: try aplay, paplay, play in order
                    players = ["aplay", "paplay", "play"]
                    played = False
                    for player in players:
                        try:
                            proc = await asyncio.create_subprocess_exec(
                                player, temp_path,
                                stdout=asyncio.subprocess.DEVNULL,
                                stderr=asyncio.subprocess.DEVNULL
                            )
                            await proc.wait()
                            played = True
                            break
                        except FileNotFoundError:
                            continue

                    if not played:
                        logger.warning("No audio player found (tried aplay, paplay, play)")
                        return web.json_response(
                            {"success": False, "error": "No audio player available"},
                            status=500
                        )
                else:
                    logger.warning(f"Local TTS playback not supported on platform: {sys.platform}")
                    return web.json_response(
                        {"success": False, "error": f"Platform not supported: {sys.platform}"},
                        status=500
                    )

                return web.json_response({"success": True})

            finally:
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)

        except asyncio.TimeoutError:
            logger.error(f"TTS generation timeout for: {text[:50]}...")
            return web.json_response(
                {"success": False, "error": "TTS generation timeout"},
                status=500
            )
        except Exception as e:
            logger.error(f"Local TTS API failed: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_answer(self, request: web.Request) -> web.Response:
        """POST /api/answer/{session} - Answer an AskUserQuestion prompt."""
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
            # 3. Direct custom: just send text + Enter (free-form input without numbered option)
            if option_number:
                # "Type something" flow: select option first (no Enter), then type
                self.agent.send_keys(name, str(option_number))
                await asyncio.sleep(0.5)  # Wait for Claude to show text input
                success = self.agent.send_input(name, answer)  # text + Enter
            elif is_custom:
                # Direct custom answer: type the text and press Enter
                success = self.agent.send_input(name, answer)
            else:
                # Just send the number key - AskUserQuestion responds to single keypress
                success = self.agent.send_keys(name, str(answer))

            if not success:
                return web.json_response({"error": "Failed to send answer"}, status=500)

            # Notify clients the question was answered
            if name in self.active_sessions:
                session = self.active_sessions[name]
                session.last_question = None
                await self._broadcast(session, {"type": "question_answered"})

            logger.info(f"[{name}] Answered: {answer}")
            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Answer API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_permission_request(self, request: web.Request) -> web.Response:
        """POST /api/permission/{session} - Handle permission request from Claude Code hook.

        This endpoint is called by the permission hook script when Claude Code
        needs permission for an action. It broadcasts the request to connected
        clients and waits for a response.

        In restricted mode, only say commands are auto-allowed,
        everything else is auto-denied silently.
        """
        name = request.match_info["name"]
        try:
            data = await request.json()
            tool_name = data.get("tool_name", "unknown")
            tool_input = data.get("tool_input", {})
            message = data.get("message", "")

            logger.info(f"[{name}] Permission request: {tool_name}")

            # Ensure session exists
            if name not in self.active_sessions:
                self.active_sessions[name] = Session(name=name, config=self._get_session_config(name))

            session = self.active_sessions[name]

            # Check restricted mode - auto-handle without user interaction
            if session.config.type == "claude-restricted":
                # Parse session name to handle local vs remote
                project, branch, machine = parse_session_name(name)
                if branch:
                    tmux_session = f"{project}/{branch}".replace(".", "_")
                else:
                    tmux_session = project.replace(".", "_")

                if _is_allowed_in_restricted_mode(tool_name, tool_input):
                    # Auto-allow
                    logger.info(f"[{name}] Restricted mode: auto-allowing {tool_name}")
                    # Only send keystroke for Bash commands (say)
                    # AskUserQuestion doesn't need permission keystroke
                    if tool_name == "Bash":
                        try:
                            # Use CLI for consistent behavior (handles local and remote)
                            # Send "1" to select "Yes" option in permission prompt
                            session_target = f"{tmux_session}@{machine}" if machine else tmux_session
                            subprocess.run(
                                ["agentwire", "send-keys", "-s", session_target, "1"],
                                check=True, capture_output=True
                            )
                        except Exception as e:
                            logger.error(f"[{name}] Failed to send allow keystroke: {e}")
                    return web.json_response({"decision": "allow_always"})
                else:
                    # Auto-deny: send "Escape" keystroke (deny silently)
                    logger.info(f"[{name}] Restricted mode: auto-denying {tool_name}")
                    try:
                        # Use CLI for consistent behavior (handles local and remote)
                        session_target = f"{tmux_session}@{machine}" if machine else tmux_session
                        subprocess.run(
                            ["agentwire", "send-keys", "-s", session_target, "Escape"],
                            check=True, capture_output=True
                        )
                    except Exception as e:
                        logger.error(f"[{name}] Failed to send deny keystroke: {e}")
                    return web.json_response({
                        "decision": "deny",
                        "message": "Restricted mode: only say commands are allowed"
                    })

            # Create pending permission request (normal/prompted mode)
            session.pending_permission = PendingPermission(request=data)

            # Broadcast permission request to all clients (Task 3.1)
            await self._broadcast(session, {
                "type": "permission_request",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "message": message,
            })

            # Generate TTS announcement (Task 3.6)
            await self._announce_permission_request(name, tool_name, tool_input)

            # Wait for user decision with 5 minute timeout
            try:
                await asyncio.wait_for(session.pending_permission.event.wait(), timeout=300)
            except asyncio.TimeoutError:
                logger.warning(f"[{name}] Permission request timed out")
                session.pending_permission = None
                await self._broadcast(session, {"type": "permission_timeout"})
                return web.json_response({
                    "decision": "deny",
                    "message": "Permission request timed out (5 minutes)"
                })

            # Return the decision to the hook script
            decision = session.pending_permission.decision
            session.pending_permission = None

            logger.info(f"[{name}] Permission decision: {decision}")
            return web.json_response(decision)

        except Exception as e:
            logger.error(f"Permission request failed: {e}")
            return web.json_response(
                {"decision": "deny", "message": str(e)},
                status=500
            )

    async def api_permission_respond(self, request: web.Request) -> web.Response:
        """POST /api/permission/{session}/respond - User responds to permission request.

        Called by the portal UI when user clicks Allow or Deny.
        """
        name = request.match_info["name"]
        try:
            data = await request.json()
            decision = data.get("decision", "deny")

            logger.info(f"[{name}] Permission response: {decision}")

            if name not in self.active_sessions:
                return web.json_response({"error": "Session not found"}, status=404)

            session = self.active_sessions[name]

            if not session.pending_permission:
                return web.json_response({"error": "No pending permission request"}, status=400)

            # Store decision and signal the waiting request
            session.pending_permission.decision = {"decision": decision}
            if decision == "deny":
                session.pending_permission.decision["message"] = data.get("message", "User denied permission")
            session.pending_permission.event.set()

            # Send keystroke to session to respond to Claude's interactive prompt
            # Use CLI for consistent behavior (handles local and remote via session@machine format)
            try:
                import subprocess

                if decision == "custom":
                    # Custom feedback: send "3", then message, then Enter
                    custom_message = data.get("message", "")
                    if custom_message:
                        # send-keys handles pauses between key groups
                        subprocess.run(
                            ["agentwire", "send-keys", "-s", name, "3", custom_message, "Enter"],
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
                        ["agentwire", "send-keys", "-s", name, keystroke],
                        check=True, capture_output=True
                    )
                    logger.info(f"[{name}] Sent keystroke '{keystroke}' to session")
            except Exception as e:
                logger.error(f"[{name}] Failed to send keystroke: {e}")

            # Broadcast permission_resolved to all clients (Task 3.7)
            await self._broadcast(session, {
                "type": "permission_resolved",
                "decision": decision,
            })

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Permission respond failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _announce_permission_request(self, session_name: str, tool_name: str, tool_input: dict):
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

        await self._say_to_room(session_name, text)

    async def api_recreate_session(self, request: web.Request) -> web.Response:
        """POST /api/session/{name}/recreate - Destroy session/worktree and create fresh one via CLI.

        Inherits session type from existing session config.
        Supported types: claude-bypass | claude-prompted | claude-restricted | opencode-bypass | opencode-prompted | opencode-restricted | bare
        """
        name = request.match_info["name"]
        try:
            logger.info(f"[{name}] Recreating session...")

            # Get old config for inheriting settings (before CLI deletes it)
            old_config = self._get_session_config(name)

            # Build CLI args
            args = ["recreate", "-s", name]
            # Set session type via --type flag
            args.extend(["--type", old_config.type])

            # Call CLI - handles kill, worktree removal, git pull, new worktree, new session
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to recreate session")
                return web.json_response({"error": error_msg}, status=500)

            new_session_name = result.get("session", name)
            session_path = result.get("path")

            # Clean up old session state
            if name in self.active_sessions:
                session = self.active_sessions[name]
                if session.output_task:
                    session.output_task.cancel()
                del self.active_sessions[name]

            # CLI writes .agentwire.yml with type; update voice if the old session had one
            if session_path and old_config.voice != self.config.tts.default_voice:
                machine_id = None
                if "@" in new_session_name:
                    _, machine_id = new_session_name.rsplit("@", 1)
                yaml_config = self._read_agentwire_yaml(session_path, machine_id) or {}
                yaml_config["voice"] = old_config.voice
                self._write_agentwire_yaml(session_path, yaml_config, machine_id)

            logger.info(f"[{name}] Session recreated as '{new_session_name}'")
            return web.json_response({"success": True, "session": new_session_name})

        except Exception as e:
            logger.error(f"Recreate session API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_spawn_sibling(self, request: web.Request) -> web.Response:
        """POST /api/session/{name}/spawn-sibling - Create a new session in same project via CLI.

        Creates a parallel session in a new worktree without destroying the current one.
        Useful for working on multiple features in the same project simultaneously.

        Inherits session type from existing session config.
        Supported types: claude-bypass | claude-prompted | claude-restricted | opencode-bypass | opencode-prompted | opencode-restricted | bare
        """
        name = request.match_info["name"]
        try:
            logger.info(f"[{name}] Spawning sibling session...")

            # Parse session name to get project and machine
            project, _, machine = parse_session_name(name)

            # Get old config for inheriting settings
            old_config = self._get_session_config(name)

            # Build new session name: project/session-<timestamp>[@machine]
            new_branch = f"session-{int(time.time())}"
            new_session_name = f"{project}/{new_branch}"
            if machine:
                new_session_name = f"{new_session_name}@{machine}"

            # Build CLI args - use `agentwire new` with the sibling session name
            args = ["new", "-s", new_session_name]
            # Set session type via --type flag
            args.extend(["--type", old_config.type])

            # Call CLI - handles worktree creation and session setup
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to create sibling session")
                return web.json_response({"error": error_msg}, status=500)

            session_name = result.get("session", new_session_name)
            session_path = result.get("path")

            # CLI writes .agentwire.yml with type; update voice if the old session had one
            if session_path and old_config.voice != self.config.tts.default_voice:
                machine_id = machine
                yaml_config = self._read_agentwire_yaml(session_path, machine_id) or {}
                yaml_config["voice"] = old_config.voice
                self._write_agentwire_yaml(session_path, yaml_config, machine_id)

            logger.info(f"[{name}] Sibling session created: '{session_name}'")
            return web.json_response({"success": True, "session": session_name})

        except Exception as e:
            logger.error(f"Spawn sibling API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_fork_session(self, request: web.Request) -> web.Response:
        """POST /api/session/{name}/fork - Fork the Claude Code session via CLI.

        Creates a new session that continues from the current conversation context.

        Inherits session type from existing session config.
        Supported types: claude-bypass | claude-prompted | claude-restricted | opencode-bypass | opencode-prompted | opencode-restricted | bare
        """
        name = request.match_info["name"]
        try:
            # Get current session config for inheriting settings
            session_config = self._get_session_config(name)

            logger.info(f"[{name}] Forking session...")

            # Parse session name to get project and machine
            project, _, machine = parse_session_name(name)

            # Find next available fork number for target name
            # Just check if tmux session exists (no cache to check)
            fork_num = 1
            while True:
                candidate = f"{project}-fork-{fork_num}"
                if machine:
                    candidate = f"{candidate}@{machine}"
                if not self.agent.session_exists(candidate):
                    break
                fork_num += 1

            # Build target session name: project/fork-N[@machine]
            new_branch = f"fork-{fork_num}"
            target_session = f"{project}/{new_branch}"
            if machine:
                target_session = f"{target_session}@{machine}"

            # Build CLI args
            args = ["fork", "-s", name, "-t", target_session]
            # Set session type via --type flag
            args.extend(["--type", session_config.type])

            # Call CLI - handles worktree creation and session setup
            success, result = await self.run_agentwire_cmd(args)

            if not success:
                error_msg = result.get("error", "Failed to fork session")
                return web.json_response({"error": error_msg}, status=500)

            session_name = result.get("session", target_session)
            session_path = result.get("path")

            # CLI writes .agentwire.yml with type; update voice if the old session had one
            if session_path and session_config.voice != self.config.tts.default_voice:
                machine_id = machine
                yaml_config = self._read_agentwire_yaml(session_path, machine_id) or {}
                yaml_config["voice"] = session_config.voice
                self._write_agentwire_yaml(session_path, yaml_config, machine_id)

            logger.info(f"[{name}] Session forked as '{session_name}'")
            return web.json_response({"success": True, "session": session_name})

        except Exception as e:
            logger.error(f"Fork session API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_restart_service(self, request: web.Request) -> web.Response:
        """POST /api/session/{name}/restart-service - Restart a system service.

        For system sessions (portal, tts, main), this properly restarts the service.
        Session names are configurable via services.*.session_name in config.
        """
        import subprocess

        name = request.match_info["name"]
        base_name = name.split("@")[0]
        session_names = self._get_system_session_names()

        if not self._is_system_session(name):
            return web.json_response(
                {"error": f"'{name}' is not a system session"},
                status=400
            )

        try:
            logger.info(f"[{name}] Restarting service...")
            portal_session = session_names["portal"]
            tts_session = session_names["tts"]
            main_session = session_names["main"]

            if base_name == portal_session:
                # Special case: we are the portal, need to restart ourselves
                # Schedule restart after responding
                # Can't use `agentwire portal start` as it tries to attach to terminal
                async def delayed_restart():
                    await asyncio.sleep(1)
                    logger.info("Portal restarting...")
                    # Kill the tmux session (which kills us)
                    subprocess.run(
                        ["tmux", "kill-session", "-t", portal_session],
                        capture_output=True
                    )
                    await asyncio.sleep(0.5)
                    # Create new tmux session with portal serve command
                    subprocess.run(
                        ["tmux", "new-session", "-d", "-s", portal_session],
                        capture_output=True
                    )
                    subprocess.run(
                        ["tmux", "send-keys", "-t", portal_session,
                         "agentwire portal serve", "Enter"],
                        capture_output=True
                    )

                asyncio.create_task(delayed_restart())
                return web.json_response({
                    "success": True,
                    "message": "Portal restarting in 1 second..."
                })

            elif base_name == tts_session:
                # Restart TTS server
                subprocess.run(
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

            elif base_name == main_session:
                # Restart the agentwire session - kill Claude and restart it
                self.agent.send_keys(name, "/exit")
                await asyncio.sleep(1)

                # Send the agent command to restart Claude
                agent_cmd = self.agent.agent_command
                self.agent.send_input(name, agent_cmd)

                return web.json_response({
                    "success": True,
                    "message": "Agentwire session restarted"
                })

            return web.json_response({"error": "Unknown system session"}, status=400)

        except Exception as e:
            logger.error(f"Restart service API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_history_list(self, request: web.Request) -> web.Response:
        """GET /api/history - List session history.

        Query params:
            project: Project path (required)
            machine: Machine ID (default "local")
            limit: Max number of entries (default 20)

        Response:
            {history: [{sessionId, firstMessage, lastSummary, timestamp, messageCount}, ...]}
        """
        try:
            project = request.query.get("project")
            if not project:
                return web.json_response(
                    {"error": "project parameter is required"},
                    status=400
                )

            machine = request.query.get("machine", "local")
            limit = request.query.get("limit", "20")

            args = [
                "history", "list",
                "--project", project,
                "--machine", machine,
                "--limit", str(limit)
            ]

            success, result = await self.run_agentwire_cmd(args)
            if not success:
                error_msg = result.get("error", "Failed to list history") if isinstance(result, dict) else "Failed to list history"
                return web.json_response({"error": error_msg}, status=500)

            # CLI returns list directly, wrap it
            history = result if isinstance(result, list) else result.get("history", [])
            return web.json_response({"history": history})

        except Exception as e:
            logger.error(f"History list API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_history_detail(self, request: web.Request) -> web.Response:
        """GET /api/history/{session_id} - Get session history details.

        URL params:
            session_id: The session ID to get details for

        Query params:
            machine: Machine ID (default "local")

        Response:
            {sessionId, summaries: [], firstMessage, timestamps: {start, end}, gitBranch, messageCount}
        """
        try:
            session_id = request.match_info["session_id"]
            machine = request.query.get("machine", "local")

            args = [
                "history", "show",
                session_id,
                "--machine", machine
            ]

            success, result = await self.run_agentwire_cmd(args)
            if not success:
                error_msg = result.get("error", "Failed to get history detail") if isinstance(result, dict) else "Failed to get history detail"
                return web.json_response({"error": error_msg}, status=500)

            return web.json_response(result)

        except Exception as e:
            logger.error(f"History detail API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_history_resume(self, request: web.Request) -> web.Response:
        """POST /api/history/{session_id}/resume - Resume a session from history.

        URL params:
            session_id: The session ID to resume

        Request body:
            name: Optional custom session name
            projectPath: Project path (required)
            machine: Machine ID (required)

        Response:
            {session: "<new-tmux-session-name>"}
        """
        try:
            session_id = request.match_info["session_id"]
            data = await request.json()

            project_path = data.get("projectPath")
            if not project_path:
                return web.json_response(
                    {"error": "projectPath is required"},
                    status=400
                )

            machine = data.get("machine", "local")
            name = data.get("name")

            args = [
                "history", "resume",
                session_id,
                "--project", project_path,
                "--machine", machine
            ]
            if name:
                args.extend(["--name", name])

            success, result = await self.run_agentwire_cmd(args)
            if not success:
                error_msg = result.get("error", "Failed to resume session") if isinstance(result, dict) else "Failed to resume session"
                return web.json_response({"error": error_msg}, status=500)

            session_name = result.get("session") if isinstance(result, dict) else None
            return web.json_response({"session": session_name})

        except Exception as e:
            logger.error(f"History resume API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_notify(self, request: web.Request) -> web.Response:
        """POST /api/notify - Receive tmux hook notifications.

        Called by tmux hooks (via agentwire notify) when sessions/panes change.
        Broadcasts the event to all connected dashboard clients.

        Request body:
            event: Event type:
                - session_closed, session_created: Session lifecycle
                - pane_died, pane_created: Pane lifecycle
                - client_attached, client_detached: Presence tracking
                - session_renamed: Session name changes (old_name, new_name)
                - pane_focused: Active pane tracking (pane_id)
                - window_activity: Activity in monitored window
            session: Session name
            pane: Pane index (optional, for pane events)
            pane_id: Pane ID (optional, for pane events)
            old_name: Previous session name (for session_renamed)
            new_name: New session name (for session_renamed)

        Response:
            {success: true}
        """
        try:
            data = await request.json()
            event = data.get("event")
            session = data.get("session")

            if not event:
                return web.json_response(
                    {"error": "event is required"},
                    status=400
                )

            logger.info(f"Received notify: event={event}, session={session}")

            # Broadcast to dashboard clients based on event type
            if event == "session_closed":
                await self.broadcast_dashboard("session_closed", {"session": session})
                # Clean up stale state for this session
                self.session_client_counts.pop(session, None)
                # Also send sessions_update with refreshed list
                sessions_data = await self._get_sessions_data()
                await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            elif event == "session_created":
                await self.broadcast_dashboard("session_created", {"session": session})
                sessions_data = await self._get_sessions_data()
                await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            elif event == "pane_died":
                pane = data.get("pane")
                pane_id = data.get("pane_id")
                await self.broadcast_dashboard("pane_died", {"session": session, "pane": pane, "pane_id": pane_id})
                # Also send sessions_update to refresh pane counts
                sessions_data = await self._get_sessions_data()
                await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            elif event == "pane_created":
                pane = data.get("pane")
                pane_id = data.get("pane_id")
                await self.broadcast_dashboard("pane_created", {"session": session, "pane": pane, "pane_id": pane_id})
                # Also send sessions_update to refresh pane counts
                sessions_data = await self._get_sessions_data()
                await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            elif event == "client_attached":
                # Increment attached client count for this session
                self.session_client_counts[session] = self.session_client_counts.get(session, 0) + 1
                await self.broadcast_dashboard("client_attached", {
                    "session": session,
                    "client_count": self.session_client_counts[session]
                })
                # Also send sessions_update to refresh client counts
                sessions_data = await self._get_sessions_data()
                await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            elif event == "client_detached":
                # Decrement attached client count for this session
                count = self.session_client_counts.get(session, 1)
                self.session_client_counts[session] = max(0, count - 1)
                await self.broadcast_dashboard("client_detached", {
                    "session": session,
                    "client_count": self.session_client_counts[session]
                })
                # Also send sessions_update to refresh client counts
                sessions_data = await self._get_sessions_data()
                await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            elif event == "session_renamed":
                # Handle session rename - old_name and new_name in data
                old_name = data.get("old_name")
                new_name = data.get("new_name") or session
                # Transfer client count to new name
                if old_name and old_name in self.session_client_counts:
                    self.session_client_counts[new_name] = self.session_client_counts.pop(old_name)
                await self.broadcast_dashboard("session_renamed", {
                    "old_name": old_name,
                    "new_name": new_name
                })
                sessions_data = await self._get_sessions_data()
                await self.broadcast_dashboard("sessions_update", {"sessions": sessions_data})

            elif event == "pane_focused":
                # Track which pane is focused in a session
                pane_id = data.get("pane_id")
                await self.broadcast_dashboard("pane_focused", {
                    "session": session,
                    "pane_id": pane_id
                })

            elif event == "window_activity":
                # Activity detected in a monitored window
                await self.broadcast_dashboard("window_activity", {"session": session})

            else:
                # Generic event - just broadcast it
                await self.broadcast_dashboard(event, data)

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Notify API failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def speak(self, session_name: str, text: str) -> bool:
        """Generate TTS audio and send to session clients.

        Audio is broadcast only to clients connected to this specific session
        (terminal, monitor, or chat windows viewing that session).

        Returns:
            True if audio was sent to clients, False if no clients connected.
        """
        # Get or create session
        if session_name not in self.active_sessions:
            self.active_sessions[session_name] = Session(
                name=session_name, config=self._get_session_config(session_name)
            )

        session = self.active_sessions[session_name]

        # Check if any clients are connected to this session
        if not session.clients:
            logger.warning(f"[{session_name}] speak: no session clients connected")
            return False

        logger.info(f"[{session_name}] speak: {len(session.clients)} session client(s)")

        # Get voice settings
        voice = session.config.voice or self.config.tts.default_voice
        exaggeration = session.config.exaggeration
        cfg_weight = session.config.cfg_weight

        # Notify clients TTS is starting
        await self._broadcast(session, {"type": "tts_start", "text": text})

        try:
            # Generate audio via TTS server HTTP call
            logger.info(f"[{session_name}] TTS voice: {voice}")
            audio_data = await self._tts_generate(
                text=text,
                voice=voice,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
            )

            if audio_data:
                # Prepend silence to prevent first syllable cutoff
                audio_data = self._prepend_silence(audio_data, ms=300)
                # Send base64 encoded audio to session clients only
                audio_b64 = base64.b64encode(audio_data).decode()
                logger.info(f"[{session_name}] Broadcasting audio to session ({len(audio_b64)} bytes b64)")
                await self._broadcast(session, {"type": "audio", "data": audio_b64})
                return True
            else:
                logger.warning(f"[{session_name}] TTS returned no audio data")
                return False

        except Exception as e:
            logger.error(f"TTS failed for {session_name}: {e}")
            return False


async def run_server(config: Config):
    """Run the AgentWire server."""
    server = AgentWireServer(config)
    await server.init_backends()

    # Cleanup old uploads on startup
    await server.cleanup_old_uploads()

    # Sessions are now fetched dynamically from tmux + .agentwire.yml
    # No cache to rebuild or periodically refresh

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


def main(config_path: str | None = None, **overrides) -> None:
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
        config.stt.url = None

    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
