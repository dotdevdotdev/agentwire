"""AgentWire TTS Module - Multi-backend TTS with hot-swapping support"""

from .base import TTSCapabilities, TTSEngine, TTSRequest, TTSResult
from .registry import EngineRegistry, registry

__all__ = [
    "TTSCapabilities",
    "TTSEngine",
    "TTSRequest",
    "TTSResult",
    "EngineRegistry",
    "registry",
]
