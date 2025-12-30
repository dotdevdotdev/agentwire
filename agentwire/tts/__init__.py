"""TTS backend system for AgentWire."""

from .base import TTSBackend
from .chatterbox import ChatterboxTTS
from .none import NoTTS

__all__ = ["TTSBackend", "ChatterboxTTS", "NoTTS", "get_tts_backend"]


def get_tts_backend(config: dict) -> TTSBackend:
    """Get the appropriate TTS backend based on configuration.

    Args:
        config: Configuration dict. Expects tts settings under "tts" key:
            - tts.backend: "chatterbox", "none", or None
            - tts.url: API URL (for chatterbox)
            - tts.exaggeration: Voice exaggeration (optional)
            - tts.cfg_weight: CFG weight (optional)

    Returns:
        Configured TTSBackend instance.
    """
    tts_config = config.get("tts", {})
    backend = tts_config.get("backend")

    if backend == "chatterbox":
        url = tts_config.get("url", "http://localhost:8001")
        exaggeration = tts_config.get("exaggeration", 0.5)
        cfg_weight = tts_config.get("cfg_weight", 0.5)
        return ChatterboxTTS(url=url, exaggeration=exaggeration, cfg_weight=cfg_weight)

    # Default: no TTS
    return NoTTS()
