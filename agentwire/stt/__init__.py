"""Speech-to-text backend for AgentWire."""

import logging
from typing import Any

from .base import STTBackend
from .whisperkit import WhisperKitSTT

__all__ = [
    "STTBackend",
    "WhisperKitSTT",
    "get_stt_backend",
]

logger = logging.getLogger(__name__)


def get_stt_backend(config: Any) -> STTBackend:
    """Get STT backend (WhisperKit).

    Args:
        config: Configuration object with optional stt.model_path.

    Returns:
        WhisperKitSTT instance.
    """
    # Get optional model_path from config
    model_path = None
    timeout = 60

    if hasattr(config, "stt"):
        stt_config = config.stt
        model_path = getattr(stt_config, "model_path", None)
        timeout = getattr(stt_config, "timeout", 60)
    elif isinstance(config, dict):
        stt_config = config.get("stt", {})
        model_path = stt_config.get("model_path")
        timeout = stt_config.get("timeout", 60)

    logger.info("Using local WhisperKitSTT")
    return WhisperKitSTT(model_path=model_path, timeout=timeout)
