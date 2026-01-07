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
    method: Literal["portal", "chatterbox", "none"]
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
        """Send TTS request to portal API.

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

        async with aiohttp.ClientSession() as session:
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
    """Route TTS requests to available backends with fallback.

    Routing logic (from Wave 1 decisions):
    1. If session detected AND portal running → use portal (broadcasts to browser)
    2. Otherwise, use configured backend from config.yaml
    3. Respect user's backend choice (don't override with fallbacks)
    """

    def __init__(self, config: Config):
        self.config = config
        self.portal_client = PortalClient(config)
        self.chatterbox_client = ChatterboxClient(config)

    async def speak(
        self, text: str, voice: Optional[str], session: Optional[str]
    ) -> TTSResult:
        """Speak text via appropriate TTS backend.

        Args:
            text: Text to speak
            voice: TTS voice name (optional)
            session: Detected session name/room (optional)

        Returns:
            TTSResult with success status and method used
        """
        # Try portal first if we have a session/room (for browser broadcasting)
        if session:
            try:
                await self.portal_client.speak(text=text, voice=voice, room=session)
                return TTSResult(success=True, method="portal")
            except Exception:
                # Portal down or room doesn't exist, fall through to configured backend
                pass

        # Use configured TTS backend
        backend = self.config.tts.backend

        if backend == "chatterbox":
            try:
                await self.chatterbox_client.speak(text=text, voice=voice)
                return TTSResult(success=True, method="chatterbox")
            except Exception as e:
                return TTSResult(
                    success=False, method="none", error=f"Chatterbox failed: {e}"
                )

        elif backend == "none":
            # TTS disabled in config
            return TTSResult(success=True, method="none")

        else:
            # Unknown or unsupported backend
            return TTSResult(
                success=False, method="none", error=f"Unknown TTS backend: {backend}"
            )
