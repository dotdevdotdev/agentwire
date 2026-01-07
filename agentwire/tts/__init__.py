"""TTS backend system for AgentWire."""

from .base import TTSBackend
from .chatterbox import ChatterboxTTS
from .none import NoTTS
from .runpod_backend import RunPodTTS

__all__ = ["TTSBackend", "ChatterboxTTS", "NoTTS", "RunPodTTS", "get_tts_backend"]


def get_tts_backend(config: dict) -> TTSBackend:
    """Get the appropriate TTS backend based on configuration.

    Args:
        config: Configuration dict. Expects tts settings under "tts" key:
            - tts.backend: "chatterbox", "runpod", "none", or None
            - tts.url: API URL (for chatterbox)
            - tts.exaggeration: Voice exaggeration (optional)
            - tts.cfg_weight: CFG weight (optional)
            - tts.runpod_endpoint_id: RunPod endpoint ID (for runpod)
            - tts.runpod_api_key: RunPod API key (for runpod)
            - tts.runpod_timeout: Request timeout in seconds (for runpod)

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

    if backend == "runpod":
        endpoint_id = tts_config.get("runpod_endpoint_id", "")
        api_key = tts_config.get("runpod_api_key", "")
        exaggeration = tts_config.get("exaggeration", 0.5)
        cfg_weight = tts_config.get("cfg_weight", 0.5)
        timeout = tts_config.get("runpod_timeout", 60)

        if not endpoint_id or not api_key:
            raise ValueError("RunPod backend requires runpod_endpoint_id and runpod_api_key")

        return RunPodTTS(
            endpoint_id=endpoint_id,
            api_key=api_key,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            timeout=timeout,
        )

    # Default: no TTS
    return NoTTS()
