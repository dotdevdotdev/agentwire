"""OpenAI Whisper API STT backend."""

import logging
import os
from pathlib import Path

from .base import STTBackend

logger = logging.getLogger(__name__)

# API endpoint
WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"


class OpenAISTT(STTBackend):
    """OpenAI Whisper API STT backend."""

    def __init__(self, language: str = "en"):
        """Initialize OpenAI Whisper backend.

        Args:
            language: Language code for transcription (default: "en").

        Raises:
            ValueError: If OPENAI_API_KEY environment variable is not set.
        """
        self.language = language
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

    @property
    def name(self) -> str:
        return "openai"

    async def transcribe(self, audio_path: Path) -> str | None:
        """Transcribe audio using OpenAI Whisper API.

        Args:
            audio_path: Path to audio file (WAV format, 16kHz mono).

        Returns:
            Transcribed text, or None if transcription failed.
        """
        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp is required for OpenAI STT backend")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                with open(audio_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field(
                        "file",
                        f,
                        filename=audio_path.name,
                        content_type="audio/wav",
                    )
                    data.add_field("model", "whisper-1")
                    data.add_field("language", self.language)
                    data.add_field("response_format", "text")

                    async with session.post(
                        WHISPER_API_URL,
                        headers=headers,
                        data=data,
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(
                                "OpenAI API error (%d): %s",
                                response.status,
                                error_text,
                            )
                            return None

                        text = await response.text()
                        return text.strip() if text.strip() else None

        except aiohttp.ClientError as e:
            logger.error("OpenAI API request failed: %s", e)
            return None
        except Exception as e:
            logger.error("OpenAI transcription error: %s", e)
            return None
