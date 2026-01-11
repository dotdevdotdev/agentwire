"""Speech-to-text backends for AgentWire."""

import logging
from typing import Any

from .base import STTBackend
from .none import NoSTT
from .remote import RemoteSTT

__all__ = [
    "STTBackend",
    "NoSTT",
    "RemoteSTT",
    "get_stt_backend",
]

logger = logging.getLogger(__name__)


def get_stt_backend(config: Any) -> STTBackend:
    """Get STT backend based on configuration.

    Args:
        config: Configuration object with stt.url attribute.

    Returns:
        Configured STT backend instance (RemoteSTT or NoSTT).
    """
    # Get STT config (handle both dict and object-style access)
    if hasattr(config, "stt"):
        stt_config = config.stt
        url = getattr(stt_config, "url", None)
        timeout = getattr(stt_config, "timeout", 30)
    elif isinstance(config, dict):
        stt_config = config.get("stt", {})
        url = stt_config.get("url")
        timeout = stt_config.get("timeout", 30)
    else:
        url = None
        timeout = 30

    # If URL is configured, use RemoteSTT
    if url:
        logger.info(f"Initializing RemoteSTT with url={url}, timeout={timeout}")
        return RemoteSTT(url=url, timeout=timeout)

    # No URL = no STT
    logger.info("No STT URL configured, STT disabled")
    return NoSTT()
