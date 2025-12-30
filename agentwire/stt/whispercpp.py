"""Whisper.cpp STT backend (cross-platform)."""

import asyncio
import logging
import shutil
from pathlib import Path

from .base import STTBackend

logger = logging.getLogger(__name__)


class WhisperCppSTT(STTBackend):
    """Whisper.cpp STT backend (Linux, macOS, WSL2)."""

    def __init__(self, model_path: str | Path, language: str = "en"):
        """Initialize Whisper.cpp backend.

        Args:
            model_path: Path to the GGML model file.
            language: Language code for transcription (default: "en").
        """
        self.model_path = Path(model_path)
        self.language = language
        self._executable: str | None = None

    def _find_executable(self) -> str | None:
        """Find the whisper.cpp executable."""
        if self._executable:
            return self._executable

        # Try common executable names
        for name in ["whisper-cpp", "whisper", "main"]:
            if shutil.which(name):
                self._executable = name
                return name

        return None

    @property
    def name(self) -> str:
        return "whispercpp"

    async def transcribe(self, audio_path: Path) -> str | None:
        """Transcribe audio using whisper.cpp.

        Args:
            audio_path: Path to audio file (WAV format, 16kHz mono).

        Returns:
            Transcribed text, or None if transcription failed.
        """
        executable = self._find_executable()
        if not executable:
            logger.error(
                "whisper.cpp executable not found. "
                "Install whisper.cpp and ensure 'whisper-cpp' or 'whisper' is in PATH."
            )
            return None

        cmd = [
            executable,
            "-m", str(self.model_path),
            "-l", self.language,
            "-f", str(audio_path),
            "--no-timestamps",
            "--output-txt",
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
                    "whisper.cpp failed (code %d): %s",
                    proc.returncode,
                    stderr.decode().strip(),
                )
                return None

            # whisper.cpp outputs text to stdout with --output-txt
            text = stdout.decode().strip()
            
            # Clean up any [BLANK_AUDIO] or similar markers
            if text.startswith("[") and text.endswith("]"):
                return None
            
            return text if text else None

        except FileNotFoundError:
            logger.error("whisper.cpp executable not found: %s", executable)
            return None
        except Exception as e:
            logger.error("Whisper.cpp transcription error: %s", e)
            return None
