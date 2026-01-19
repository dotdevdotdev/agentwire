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

    async def generate(
        self,
        text: str,
        voice: str,
        exaggeration: float | None = None,
        cfg_weight: float | None = None,
    ) -> bytes | None:
        """Generate audio from text using Chatterbox API.

        Args:
            text: The text to synthesize.
            voice: The voice ID to use.
            exaggeration: Override voice exaggeration (0.0-1.0).
            cfg_weight: Override CFG weight (0.0-1.0).

        Returns:
            WAV audio bytes, or None if generation failed.
        """
        session = await self._get_session()
        payload = {
            "text": text,
            "voice": voice,
            "exaggeration": exaggeration if exaggeration is not None else self.exaggeration,
            "cfg_weight": cfg_weight if cfg_weight is not None else self.cfg_weight,
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
                    voices = data
                    if isinstance(data, dict) and "voices" in data:
                        voices = data["voices"]
                    # Extract name if voices are objects
                    if voices and isinstance(voices[0], dict):
                        return [v.get("name", str(v)) for v in voices]
                    return voices if isinstance(voices, list) else []
                return []
        except aiohttp.ClientError:
            return []

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
