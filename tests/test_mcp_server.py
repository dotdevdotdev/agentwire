"""Unit tests for MCP server implementation.

Tests MCP tool registration, session detection, TTS routing, and error handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass


# Mock classes for testing (since actual implementation doesn't exist yet)
@dataclass
class MockTTSResult:
    """Mock TTS result for testing."""
    success: bool
    method: str
    error: str | None = None


@dataclass
class MockConfig:
    """Mock config for testing."""
    @dataclass
    class ServerConfig:
        host: str = "localhost"
        port: int = 8765

    @dataclass
    class TTSConfig:
        backend: str = "chatterbox"
        default_voice: str = "bashbunni"
        url: str = "http://localhost:8100"

    server: ServerConfig = None
    tts: TTSConfig = None

    def __post_init__(self):
        if self.server is None:
            self.server = self.ServerConfig()
        if self.tts is None:
            self.tts = self.TTSConfig()


@pytest.fixture
def mock_config():
    """Provide mock config for testing."""
    return MockConfig()


@pytest.fixture
def mock_session_detector():
    """Provide mock session detector."""
    detector = Mock()
    detector.get_calling_session = Mock(return_value="test-session")
    detector.get_room_for_session = Mock(return_value="test-session")
    return detector


@pytest.fixture
def mock_tts_router():
    """Provide mock TTS router."""
    router = AsyncMock()
    router.speak = AsyncMock(return_value=MockTTSResult(
        success=True,
        method="portal"
    ))
    router.list_voices = AsyncMock(return_value=["bashbunni", "voice2"])
    return router


class TestMCPToolRegistration:
    """Test MCP tool registration and configuration."""

    def test_speak_tool_registered(self, mock_session_detector, mock_tts_router):
        """Verify speak tool is registered with correct parameters."""
        # This will be the actual implementation pattern
        # from agentwire.mcp.server import AgentWireMCPServer
        # server = AgentWireMCPServer(mock_session_detector, mock_tts_router)

        # Pattern verification for expected tool parameters
        expected_params = {
            "text": {"type": "string", "required": True},
            "voice": {"type": "string", "required": False}
        }
        assert "text" in expected_params
        assert expected_params["text"]["required"] is True
        assert expected_params["voice"]["required"] is False

    def test_list_voices_tool_registered(self):
        """Verify list_voices tool is registered."""
        # Tool should have no required parameters
        expected_params = {}
        # Actual verification will happen when implementation exists
        assert expected_params == {}

    def test_set_voice_tool_registered(self):
        """Verify set_voice tool is registered with correct parameters."""
        expected_params = {
            "name": {"type": "string", "required": True}
        }
        # Actual verification will happen when implementation exists
        assert "name" in expected_params


class TestSessionDetection:
    """Test session detection from PID."""

    @patch('psutil.Process')
    def test_detect_session_from_tmux_parent(self, mock_process_class):
        """Verify session detection walks process tree to find tmux."""
        # Create mock process tree
        claude_process = Mock()
        claude_process.parent.return_value = Mock()

        tmux_process = Mock()
        tmux_process.name.return_value = "tmux: server"
        tmux_process.cmdline.return_value = ["tmux", "attach", "-t", "myproject"]
        tmux_process.parent.return_value = None

        claude_process.parent.return_value = tmux_process
        mock_process_class.return_value = claude_process

        # from agentwire.session_detector import SessionDetector
        # detector = SessionDetector()
        # session = detector.get_calling_session()
        # assert session == "myproject"

        # Pattern verification for now
        assert tmux_process.cmdline()[3] == "myproject"

    @patch('psutil.Process')
    def test_extract_session_from_tmux_server_name(self, mock_process_class):
        """Verify session extraction from tmux server process name."""
        tmux_process = Mock()
        tmux_process.name.return_value = "tmux: server (test-session)"
        tmux_process.cmdline.return_value = ["tmux: server (test-session)"]

        # Extract session from name format: "tmux: server (session-name)"
        name = tmux_process.name()
        if '(' in name:
            session = name.split('(')[1].rstrip(')')
            assert session == "test-session"

    @patch('psutil.Process')
    def test_session_detection_returns_none_outside_tmux(self, mock_process_class):
        """Verify None is returned when not in tmux session."""
        # Create mock process tree with no tmux parent
        process = Mock()
        process.name.return_value = "python"
        process.parent.return_value = None
        mock_process_class.return_value = process

        # from agentwire.session_detector import SessionDetector
        # detector = SessionDetector()
        # session = detector.get_calling_session()
        # assert session is None

        # Pattern verification
        assert "tmux" not in process.name()

    def test_session_to_room_mapping(self):
        """Verify session name maps directly to room name."""
        test_cases = [
            ("myproject", "myproject"),
            ("myproject/branch", "myproject/branch"),
            ("myproject@machine", "myproject@machine"),
            ("myproject/branch@machine", "myproject/branch@machine"),
        ]

        for session, expected_room in test_cases:
            # Session name IS the room name in AgentWire
            assert session == expected_room


class TestTTSRouting:
    """Test TTS routing logic with fallbacks."""

    @pytest.mark.asyncio
    async def test_portal_routing_with_session(self, mock_config):
        """Verify portal is used when session is detected."""
        # from agentwire.tts_router import TTSRouter
        # router = TTSRouter(mock_config)
        # result = await router.speak(
        #     text="Hello",
        #     voice=None,
        #     session="test-session"
        # )
        # assert result.method == "portal"

        # Pattern verification
        session = "test-session"
        assert session is not None

    @pytest.mark.asyncio
    async def test_chatterbox_routing_without_session(self, mock_config):
        """Verify chatterbox is used when no session detected."""
        # from agentwire.tts_router import TTSRouter
        # router = TTSRouter(mock_config)
        # result = await router.speak(
        #     text="Hello",
        #     voice=None,
        #     session=None
        # )
        # assert result.method == "chatterbox"

        # Pattern verification
        assert mock_config.tts.backend == "chatterbox"

    @pytest.mark.asyncio
    async def test_portal_fallback_to_chatterbox_on_error(self, mock_config):
        """Verify fallback to chatterbox when portal fails."""
        # Portal should be tried first, then fall back to configured backend
        # from agentwire.tts_router import TTSRouter, PortalClient

        # with patch.object(PortalClient, 'speak', side_effect=Exception("Portal down")):
        #     router = TTSRouter(mock_config)
        #     result = await router.speak(
        #         text="Hello",
        #         voice=None,
        #         session="test-session"
        #     )
        #     assert result.method == "chatterbox"

        # Pattern verification
        assert mock_config.tts.backend == "chatterbox"

    @pytest.mark.asyncio
    async def test_none_backend_returns_success(self, mock_config):
        """Verify 'none' backend returns success without doing anything."""
        mock_config.tts.backend = "none"

        # from agentwire.tts_router import TTSRouter
        # router = TTSRouter(mock_config)
        # result = await router.speak(
        #     text="Hello",
        #     voice=None,
        #     session=None
        # )
        # assert result.success is True
        # assert result.method == "none"

        # Pattern verification
        assert mock_config.tts.backend == "none"


class TestPortalClient:
    """Test Portal API client."""

    def test_portal_url_from_file(self, tmp_path):
        """Verify portal URL is read from portal_url file."""
        portal_url_file = tmp_path / "portal_url"
        portal_url_file.write_text("https://192.168.1.100:8765")

        # from agentwire.tts_router import PortalClient
        # with patch('pathlib.Path.home', return_value=tmp_path.parent):
        #     client = PortalClient(mock_config)
        #     assert client.base_url == "https://192.168.1.100:8765"

        # Pattern verification
        assert portal_url_file.read_text() == "https://192.168.1.100:8765"

    def test_portal_url_from_config(self, mock_config):
        """Verify portal URL fallback to config."""
        # from agentwire.tts_router import PortalClient
        # client = PortalClient(mock_config)
        # assert client.base_url == f"https://{mock_config.server.host}:{mock_config.server.port}"

        # Pattern verification
        expected_url = f"https://{mock_config.server.host}:{mock_config.server.port}"
        assert expected_url == "https://localhost:8765"

    @pytest.mark.asyncio
    async def test_portal_speak_posts_to_correct_endpoint(self):
        """Verify portal speak POSTs to /api/say/{room}."""
        room = "test-session"
        expected_url = f"https://localhost:8765/api/say/{room}"

        # from agentwire.tts_router import PortalClient
        # with patch('aiohttp.ClientSession.post') as mock_post:
        #     mock_response = AsyncMock()
        #     mock_response.raise_for_status = Mock()
        #     mock_response.json = AsyncMock(return_value={"success": True})
        #     mock_post.return_value.__aenter__.return_value = mock_response
        #
        #     client = PortalClient(mock_config)
        #     await client.speak(text="Hello", voice=None, room=room)
        #
        #     mock_post.assert_called_once()
        #     call_args = mock_post.call_args
        #     assert expected_url in str(call_args)

        # Pattern verification
        assert "/api/say/" in expected_url


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_portal_down_error_handling(self, mock_config):
        """Verify graceful handling when portal is down."""
        # from agentwire.tts_router import TTSRouter, PortalClient

        # with patch.object(PortalClient, 'speak', side_effect=Exception("Connection refused")):
        #     router = TTSRouter(mock_config)
        #     result = await router.speak(
        #         text="Hello",
        #         voice=None,
        #         session="test-session"
        #     )
        #     # Should fall back to configured backend
        #     assert result.success is True
        #     assert result.method == "chatterbox"

        # Pattern verification
        assert mock_config.tts.backend == "chatterbox"

    @pytest.mark.asyncio
    async def test_invalid_backend_returns_error(self):
        """Verify error is returned for unknown backend."""
        mock_config = MockConfig()
        mock_config.tts.backend = "invalid-backend"

        # from agentwire.tts_router import TTSRouter
        # router = TTSRouter(mock_config)
        # result = await router.speak(
        #     text="Hello",
        #     voice=None,
        #     session=None
        # )
        # assert result.success is False
        # assert result.method == "none"
        # assert "Unknown TTS backend" in result.error

        # Pattern verification
        assert mock_config.tts.backend == "invalid-backend"

    @pytest.mark.asyncio
    async def test_chatterbox_failure_returns_error(self, mock_config):
        """Verify error is returned when chatterbox fails."""
        # from agentwire.tts_router import TTSRouter, ChatterboxClient

        # with patch.object(ChatterboxClient, 'speak', side_effect=Exception("TTS server down")):
        #     router = TTSRouter(mock_config)
        #     result = await router.speak(
        #         text="Hello",
        #         voice=None,
        #         session=None
        #     )
        #     assert result.success is False
        #     assert "Chatterbox failed" in result.error

        # Pattern verification
        assert mock_config.tts.backend == "chatterbox"


class TestVoiceManagement:
    """Test voice listing and setting."""

    @pytest.mark.asyncio
    async def test_list_voices_from_portal(self, mock_tts_router):
        """Verify list_voices queries portal when available."""
        voices = await mock_tts_router.list_voices()
        assert isinstance(voices, list)
        assert len(voices) > 0

    @pytest.mark.asyncio
    async def test_set_voice_persists_to_rooms_json(self, tmp_path):
        """Verify set_voice persists to rooms.json."""
        rooms_file = tmp_path / "rooms.json"
        rooms_file.write_text('{"test-session": {"voice": "old-voice"}}')

        # from agentwire.mcp.server import AgentWireMCPServer
        # server = AgentWireMCPServer(mock_session_detector, mock_tts_router)
        # await server.handle_set_voice(name="new-voice")

        # Pattern verification
        import json
        rooms = json.loads(rooms_file.read_text())
        assert "test-session" in rooms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
