"""Local WhisperKit STT backend using whisperkit-cli."""

import asyncio
import logging
import os
from pathlib import Path

from .base import STTBackend

logger = logging.getLogger(__name__)

# Default model path (MacWhisper's large-v3 model)
DEFAULT_MODEL_PATH = os.path.expanduser(
    "~/Library/Application Support/MacWhisper/models/whisperkit/models/"
    "argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930"
)


class WhisperKitSTT(STTBackend):
    """STT backend using local whisperkit-cli."""

    def __init__(self, model_path: str | None = None, timeout: int = 60):
        """Initialize WhisperKit STT backend.

        Args:
            model_path: Path to WhisperKit model directory. Defaults to MacWhisper's large-v3.
            timeout: Transcription timeout in seconds.
        """
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.timeout = timeout

    @property
    def name(self) -> str:
        """Return the backend name."""
        return "whisperkit"

    async def transcribe(self, audio_path: Path) -> str | None:
        """Transcribe audio file using whisperkit-cli.

        Args:
            audio_path: Path to audio file (WAV format, 16kHz mono).

        Returns:
            Transcribed text, or None if transcription failed.
        """
        if not audio_path.exists():
            logger.warning("Audio file does not exist: %s", audio_path)
            return None

        # Check model exists
        if not Path(self.model_path).exists():
            logger.error("WhisperKit model not found at: %s", self.model_path)
            logger.error("Install MacWhisper and download a model, or specify model_path in config")
            return None

        try:
            logger.info("Transcribing %s with whisperkit-cli", audio_path)

            proc = await asyncio.create_subprocess_exec(
                "whisperkit-cli", "transcribe",
                "--audio-path", str(audio_path),
                "--model-path", self.model_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                logger.error("whisperkit-cli timed out after %ds", self.timeout)
                return None

            if proc.returncode != 0:
                logger.error("whisperkit-cli failed: %s", stderr.decode())
                return None

            text = stdout.decode().strip()
            logger.info("Transcribed: %s", text)
            return text

        except FileNotFoundError:
            logger.error("whisperkit-cli not found. Install with: brew install whisperkit-cli")
            return None
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return None
