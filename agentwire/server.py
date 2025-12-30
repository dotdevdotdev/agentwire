"""
AgentWire WebSocket server.

Multi-room voice web interface for AI coding agents.
"""

import asyncio
import base64
import json
import logging
import re
import ssl
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import Config, load_config
from .templates import get_template
from .worktree import get_project_type, get_session_path, parse_session_name

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
        self.app.router.add_get("/room/{name}", self.handle_room)
        self.app.router.add_get("/ws/{name}", self.handle_websocket)
        self.app.router.add_get("/api/sessions", self.api_sessions)
        self.app.router.add_post("/api/create", self.api_create_session)
        self.app.router.add_post("/api/room/{name}/config", self.api_room_config)
        self.app.router.add_post("/transcribe", self.handle_transcribe)
        self.app.router.add_post("/send/{name}", self.handle_send)
        self.app.router.add_get("/api/voices", self.api_voices)
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
        return web.Response(text=html, content_type="text/html")

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
        return web.Response(text=html, content_type="text/html")

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

    async def _poll_output(self, room: Room):
        """Poll agent output and broadcast to room clients."""
        project, branch, machine = parse_session_name(room.name)

        while room.clients:
            try:
                output = await self.agent.get_output(room.name, lines=100)
                if output != room.last_output:
                    room.last_output = output
                    await self._broadcast(room, {"type": "output", "data": output})
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
            sessions = await self.agent.list_sessions()
            room_configs = self._load_room_configs()

            result = []
            for session in sessions:
                name = session.get("name", "")
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
            else:
                work_dir = self.config.projects.dir / project

            # Create session
            success = await self.agent.create_session(name, str(work_dir))
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

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_data)
                temp_path = Path(f.name)

            try:
                # Transcribe
                text = await self.stt.transcribe(temp_path)
                return web.json_response({"text": text})
            finally:
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return web.json_response({"error": str(e)})

    async def handle_send(self, request: web.Request) -> web.Response:
        """Send text to an agent session."""
        name = request.match_info["name"]
        try:
            data = await request.json()
            text = data.get("text", "").strip()

            if not text:
                return web.json_response({"error": "No text provided"})

            success = await self.agent.send_input(name, text)

            if not success:
                return web.json_response({"error": "Failed to send to session"})

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Send failed: {e}")
            return web.json_response({"error": str(e)})

    # TTS Integration

    async def speak(self, room_name: str, text: str):
        """Generate TTS audio and send to room clients."""
        if room_name not in self.rooms:
            return

        room = self.rooms[room_name]
        if not room.clients:
            return

        # Notify clients TTS is starting
        await self._broadcast(room, {"type": "tts_start"})

        try:
            # Generate audio
            audio_data = await self.tts.generate(
                text=text,
                voice=room.config.voice,
                exaggeration=room.config.exaggeration,
                cfg_weight=room.config.cfg_weight,
            )

            if audio_data:
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
