"""
TTS routing with fallback logic for AgentWire MCP server.

Routes TTS requests to appropriate backends based on session detection and config.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import aiohttp

from agentwire.config import Config


@dataclass
class TTSResult:
    """Result of a TTS routing attempt."""

    success: bool
    method: Literal["portal", "local", "chatterbox", "none"]
    error: Optional[str] = None


class PortalClient:
    """Client for portal /api/say endpoint.

    Sends TTS requests to the portal for browser broadcasting.
    """

    def __init__(self, config: Config):
        self.config = config
        self.base_url = self._get_portal_url()

    def _get_portal_url(self) -> str:
        """Get portal URL from config or portal_url file.

        Priority:
        1. ~/.agentwire/portal_url file (for remote machines)
        2. config.server.host:port (for local)
        """
        # Check ~/.agentwire/portal_url first
        portal_url_file = Path.home() / ".agentwire" / "portal_url"
        if portal_url_file.exists():
            return portal_url_file.read_text().strip()

        # Fallback to config
        host = self.config.server.host or "localhost"
        port = self.config.server.port or 8765
        return f"https://{host}:{port}"

    async def speak(self, text: str, voice: Optional[str], room: str) -> dict:
        """Send TTS request to portal API for browser broadcasting.

        Args:
            text: Text to speak
            voice: TTS voice name (optional)
            room: Room name for broadcasting

        Returns:
            API response JSON

        Raises:
            aiohttp.ClientError: If request fails
        """
        url = f"{self.base_url}/api/say/{room}"

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                json={"text": text, "voice": voice},
                ssl=False,  # Self-signed certs
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def speak_local(self, text: str, voice: Optional[str], room: str) -> dict:
        """Send TTS request to portal API for local speaker playback.

        Args:
            text: Text to speak
            voice: TTS voice name (optional)
            room: Room name for context

        Returns:
            API response JSON

        Raises:
            aiohttp.ClientError: If request fails
        """
        url = f"{self.base_url}/api/local-tts/{room}"

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                json={"text": text, "voice": voice},
                ssl=False,  # Self-signed certs
            ) as response:
                response.raise_for_status()
                return await response.json()


class ChatterboxClient:
    """Client for Chatterbox TTS server.

    Direct connection to Chatterbox for local/remote TTS.
    """

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.tts.url
        self.default_voice = config.tts.default_voice

    async def speak(self, text: str, voice: Optional[str]) -> dict:
        """Send TTS request to Chatterbox server.

        Args:
            text: Text to speak
            voice: TTS voice name (optional, falls back to default_voice)

        Returns:
            API response JSON

        Raises:
            aiohttp.ClientError: If request fails
        """
        url = f"{self.base_url}/tts"
        voice_to_use = voice or self.default_voice

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"text": text, "voice": voice_to_use},
                ssl=False,  # Chatterbox uses HTTP
            ) as response:
                response.raise_for_status()
                return await response.json()


class TTSRouter:
    """Route TTS requests to available backends with connection-aware logic.

    Routing logic (connection-aware):
    1. If session detected AND portal has connections → portal (browser playback)
    2. If session detected AND portal has no connections → local (speaker playback)
    3. If no session → chatterbox (direct TTS backend)
    """

    def __init__(self, config: Config):
        self.config = config
        self.portal_client = PortalClient(config)
        self.chatterbox_client = ChatterboxClient(config)

    async def _check_portal_connections(self, session: str) -> bool:
        """Check if portal has active browser connections for a session.

        Args:
            session: Room/session name

        Returns:
            True if portal has connections, False otherwise
        """
        url = f"{self.portal_client.base_url}/api/rooms/{session}/connections"

        try:
            timeout = aiohttp.ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout) as http_session:
                async with http_session.get(url, ssl=False) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("has_connections", False)
        except Exception:
            # On any error (timeout, connection refused, etc.), assume no connections
            return False

    async def speak(
        self, text: str, voice: Optional[str], session: Optional[str]
    ) -> TTSResult:
        """Speak text via appropriate TTS backend with connection-aware routing.

        Args:
            text: Text to speak
            voice: TTS voice name (optional)
            session: Detected session name/room (optional)

        Returns:
            TTSResult with success status and method used
        """
        # Connection-aware routing
        if session and await self._check_portal_connections(session):
            # Route to portal browser playback
            try:
                await self.portal_client.speak(text=text, voice=voice, room=session)
                return TTSResult(success=True, method="portal")
            except Exception as e:
                return TTSResult(
                    success=False, method="none", error=f"Portal speak failed: {e}"
                )

        elif session:
            # Session exists but no connections - route to local speaker playback
            try:
                await self.portal_client.speak_local(text=text, voice=voice, room=session)
                return TTSResult(success=True, method="local")
            except Exception as e:
                return TTSResult(
                    success=False, method="none", error=f"Local TTS failed: {e}"
                )

        else:
            # No session - use chatterbox directly
            try:
                await self.chatterbox_client.speak(text=text, voice=voice)
                return TTSResult(success=True, method="chatterbox")
            except Exception as e:
                return TTSResult(
                    success=False, method="none", error=f"Chatterbox failed: {e}"
                )
