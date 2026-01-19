"""No-op TTS backend (disabled TTS)."""

from .base import TTSBackend


class NoTTS(TTSBackend):
    """No-op TTS backend that returns None for all operations."""

    async def generate(self, text: str, voice: str) -> bytes | None:
        """Return None (TTS disabled)."""
        return None

    async def get_voices(self) -> list[str]:
        """Return empty list (no voices available)."""
        return []
