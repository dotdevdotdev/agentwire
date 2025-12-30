"""No-op STT backend."""

from pathlib import Path

from .base import STTBackend


class NoSTT(STTBackend):
    """No-op STT backend that returns None."""

    @property
    def name(self) -> str:
        return "none"

    async def transcribe(self, audio_path: Path) -> str | None:
        """No-op transcription."""
        return None
