"""Speech-to-text backends for AgentWire."""

import sys
from typing import Any

from .base import STTBackend
from .none import NoSTT
from .openai import OpenAISTT
from .remote import RemoteSTT
from .whispercpp import WhisperCppSTT
from .whisperkit import WhisperKitSTT

__all__ = [
    "STTBackend",
    "NoSTT",
    "OpenAISTT",
    "RemoteSTT",
    "WhisperCppSTT",
    "WhisperKitSTT",
    "get_stt_backend",
]


def get_stt_backend(config: Any) -> STTBackend:
    """Get STT backend based on configuration.

    Args:
        config: Configuration object with stt.backend, stt.model_path,
                and stt.language attributes.

    Returns:
        Configured STT backend instance.

    Raises:
        ValueError: If backend is invalid or platform requirements not met.
    """
    # Get STT config (handle both dict and object-style access)
    if hasattr(config, "stt"):
        stt_config = config.stt
        backend = getattr(stt_config, "backend", None)
        model_path = getattr(stt_config, "model_path", None)
        language = getattr(stt_config, "language", "en")
        url = getattr(stt_config, "url", None)
        timeout = getattr(stt_config, "timeout", 30)
    elif isinstance(config, dict):
        stt_config = config.get("stt", {})
        backend = stt_config.get("backend")
        model_path = stt_config.get("model_path")
        language = stt_config.get("language", "en")
        url = stt_config.get("url")
        timeout = stt_config.get("timeout", 30)
    else:
        backend = None
        model_path = None
        language = "en"
        url = None
        timeout = 30

    # Handle None or "none" backend
    if backend is None or backend == "none":
        return NoSTT()

    if backend == "whisperkit":
        if sys.platform != "darwin":
            raise ValueError("WhisperKit is only available on macOS")
        if not model_path:
            raise ValueError("stt.model_path is required for WhisperKit")
        return WhisperKitSTT(model_path=model_path, language=language)

    if backend == "whispercpp":
        if not model_path:
            raise ValueError("stt.model_path is required for Whisper.cpp")
        return WhisperCppSTT(model_path=model_path, language=language)

    if backend == "openai":
        return OpenAISTT(language=language)

    if backend == "remote":
        if not url:
            raise ValueError("stt.url is required for remote STT backend")
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Initializing RemoteSTT with url={url}, timeout={timeout}")
        return RemoteSTT(url=url, timeout=timeout)

    raise ValueError(f"Unknown STT backend: {backend}")
