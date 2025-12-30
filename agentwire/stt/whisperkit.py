"""WhisperKit STT backend for macOS."""

import asyncio
import logging
from pathlib import Path

from .base import STTBackend

logger = logging.getLogger(__name__)


class WhisperKitSTT(STTBackend):
    """WhisperKit STT backend using whisperkit-cli (macOS only)."""

    def __init__(self, model_path: str | Path, language: str = "en"):
        """Initialize WhisperKit backend.

        Args:
            model_path: Path to the WhisperKit model directory.
            language: Language code for transcription (default: "en").
        """
        self.model_path = Path(model_path)
        self.language = language

    @property
    def name(self) -> str:
        return "whisperkit"

    async def transcribe(self, audio_path: Path) -> str | None:
        """Transcribe audio using whisperkit-cli.

        Args:
            audio_path: Path to audio file (WAV format, 16kHz mono).

        Returns:
            Transcribed text, or None if transcription failed.
        """
        cmd = [
            "whisperkit-cli",
            "transcribe",
            "--audio-path", str(audio_path),
            "--model-path", str(self.model_path),
            "--language", self.language,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(
                    "whisperkit-cli failed (code %d): %s",
                    proc.returncode,
                    stderr.decode().strip(),
                )
                return None

            text = stdout.decode().strip()
            return text if text else None

        except FileNotFoundError:
            logger.error("whisperkit-cli not found. Install WhisperKit.")
            return None
        except Exception as e:
            logger.error("WhisperKit transcription error: %s", e)
            return None
