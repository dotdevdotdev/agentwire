"""Chatterbox TTS backend."""

import aiohttp

from .base import TTSBackend


class ChatterboxTTS(TTSBackend):
    """TTS backend using the Chatterbox HTTP API."""

    def __init__(
        self,
        url: str,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ):
        """Initialize Chatterbox TTS backend.

        Args:
            url: Base URL of the Chatterbox API (e.g., "http://localhost:8001").
            exaggeration: Voice exaggeration parameter (0.0-1.0).
            cfg_weight: CFG weight parameter (0.0-1.0).
        """
        self.url = url.rstrip("/")
        self.exaggeration = exaggeration
        self.cfg_weight = cfg_weight
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def generate(self, text: str, voice: str) -> bytes | None:
        """Generate audio from text using Chatterbox API.

        Args:
            text: The text to synthesize.
            voice: The voice ID to use.

        Returns:
            WAV audio bytes, or None if generation failed.
        """
        session = await self._get_session()
        payload = {
            "text": text,
            "voice": voice,
            "exaggeration": self.exaggeration,
            "cfg_weight": self.cfg_weight,
        }

        try:
            async with session.post(f"{self.url}/tts", json=payload) as resp:
                if resp.status == 200:
                    return await resp.read()
                return None
        except aiohttp.ClientError:
            return None

    async def get_voices(self) -> list[str]:
        """Get list of available voices from Chatterbox API.

        Returns:
            List of voice identifiers.
        """
        session = await self._get_session()

        try:
            async with session.get(f"{self.url}/voices") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict) and "voices" in data:
                        return data["voices"]
                return []
        except aiohttp.ClientError:
            return []

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
