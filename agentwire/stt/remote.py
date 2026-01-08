"""Remote STT backend - connects to STT server via HTTP."""

import logging
from pathlib import Path

import aiohttp

from .base import STTBackend

logger = logging.getLogger(__name__)


class RemoteSTT(STTBackend):
    """STT backend that connects to a remote STT server."""

    def __init__(self, url: str, timeout: int = 30):
        """Initialize remote STT backend.

        Args:
            url: Base URL of STT server (e.g., "http://localhost:8100")
            timeout: Request timeout in seconds
        """
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        """Return the backend name."""
        return "remote"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def transcribe(self, audio_path: Path) -> str | None:
        """Transcribe audio file via remote STT server.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcribed text, or None if transcription failed
        """
        if not audio_path.exists():
            logger.warning("Audio file does not exist: %s", audio_path)
            return None

        session = await self._get_session()

        try:
            # Read audio file
            audio_data = audio_path.read_bytes()
            logger.info("Sending %d bytes to %s/transcribe", len(audio_data), self.url)

            # Create multipart form data
            data = aiohttp.FormData()
            data.add_field(
                "file",
                audio_data,
                filename=audio_path.name,
                content_type="audio/wav"
            )

            # POST to /transcribe endpoint
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with session.post(
                f"{self.url}/transcribe",
                data=data,
                timeout=timeout
            ) as resp:
                if resp.status != 200:
                    logger.error("STT server returned status %d", resp.status)
                    return None

                result = await resp.json()
                text = result.get("text")
                logger.info("Received transcription: %s", text)
                return text

        except aiohttp.ClientError as e:
            logger.error("STT request failed: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error in transcription: %s", e)
            return None

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
