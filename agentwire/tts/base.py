"""TTS Engine Base Classes and Abstractions"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator

from pydantic import BaseModel

if TYPE_CHECKING:
    import torch


@dataclass
class TTSCapabilities:
    """Capabilities supported by a TTS engine."""

    voice_cloning: bool = False
    voice_design: bool = False  # Generate voice from text description
    preset_voices: list[str] = field(default_factory=list)
    emotion_control: bool = False  # instruct parameter support
    paralinguistic_tags: bool = False  # [laugh], [sigh], etc.
    streaming: bool = False
    languages: list[str] = field(default_factory=lambda: ["English"])


class TTSRequest(BaseModel):
    """Request parameters for TTS generation."""

    text: str
    voice: str | None = None  # Voice reference name or preset voice

    # Chatterbox-specific
    exaggeration: float = 0.5
    cfg_weight: float = 0.5

    # Qwen-specific
    instruct: str | None = None  # Emotion/style instruction
    language: str = "English"

    # Streaming
    stream: bool = False

    # Backend selection (optional override)
    backend: str | None = None


@dataclass
class TTSResult:
    """Result of TTS generation."""

    audio: "torch.Tensor"  # Shape: (1, samples)
    sample_rate: int


class TTSEngine(ABC):
    """Abstract base class for TTS backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> TTSCapabilities:
        """Engine capabilities."""
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate in Hz."""
        pass

    @abstractmethod
    def generate(self, request: TTSRequest) -> TTSResult:
        """Generate audio from request.

        Args:
            request: TTS request parameters

        Returns:
            TTSResult with audio tensor and sample rate
        """
        pass

    def generate_stream(self, request: TTSRequest) -> Iterator[bytes]:
        """Generate audio as a stream of chunks.

        Args:
            request: TTS request parameters

        Yields:
            Audio data chunks as bytes

        Raises:
            NotImplementedError: If streaming not supported
        """
        raise NotImplementedError(f"{self.name} does not support streaming")

    def unload(self) -> None:
        """Release GPU memory and resources.

        Override in subclasses to implement proper cleanup.
        """
        pass
