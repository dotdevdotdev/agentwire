"""Abstract base class for TTS backends."""

from abc import ABC, abstractmethod


class TTSBackend(ABC):
    """Abstract base class for text-to-speech backends."""

    @abstractmethod
    async def generate(self, text: str, voice: str) -> bytes | None:
        """Generate audio from text.

        Args:
            text: The text to synthesize.
            voice: The voice ID to use.

        Returns:
            WAV audio bytes, or None if generation failed.
        """
        ...

    @abstractmethod
    async def get_voices(self) -> list[str]:
        """Get list of available voice IDs.

        Returns:
            List of voice identifiers.
        """
        ...

    async def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
