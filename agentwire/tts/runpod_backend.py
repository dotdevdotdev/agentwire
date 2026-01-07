"""RunPod serverless TTS backend."""

import base64

import aiohttp

from .base import TTSBackend


class RunPodTTS(TTSBackend):
    """TTS backend using RunPod serverless infrastructure.

    This backend calls a deployed RunPod serverless endpoint that runs
    the Chatterbox TTS model on GPU workers.
    """

    def __init__(
        self,
        endpoint_id: str,
        api_key: str,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        timeout: int = 60,
    ):
        """Initialize RunPod TTS backend.

        Args:
            endpoint_id: RunPod endpoint ID (e.g., "abc123xyz")
            api_key: RunPod API key for authentication
            exaggeration: Voice exaggeration parameter (0.0-1.0)
            cfg_weight: CFG weight parameter (0.0-1.0)
            timeout: Request timeout in seconds (default: 60)
        """
        self.endpoint_id = endpoint_id
        self.api_key = api_key
        self.exaggeration = exaggeration
        self.cfg_weight = cfg_weight
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

        # RunPod API endpoint
        self.endpoint_url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def generate(
        self,
        text: str,
        voice: str,
        exaggeration: float | None = None,
        cfg_weight: float | None = None,
    ) -> bytes | None:
        """Generate audio from text using RunPod serverless endpoint.

        Args:
            text: The text to synthesize.
            voice: The voice ID to use.
            exaggeration: Override voice exaggeration (0.0-1.0).
            cfg_weight: Override CFG weight (0.0-1.0).

        Returns:
            WAV audio bytes, or None if generation failed.
        """
        session = await self._get_session()

        # Build request payload
        payload = {
            "input": {
                "text": text,
                "voice": voice,
                "exaggeration": exaggeration if exaggeration is not None else self.exaggeration,
                "cfg_weight": cfg_weight if cfg_weight is not None else self.cfg_weight,
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with session.post(
                self.endpoint_url, json=payload, headers=headers, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()

                # Check RunPod status
                if data.get("status") == "error":
                    return None

                # Extract output
                output = data.get("output", {})
                if "error" in output:
                    return None

                # Decode base64 audio
                audio_b64 = output.get("audio", "")
                if not audio_b64:
                    return None

                audio_bytes = base64.b64decode(audio_b64)
                return audio_bytes

        except (aiohttp.ClientError, base64.binascii.Error):
            return None

    async def get_voices(self) -> list[str]:
        """Get list of available voices.

        Note: RunPod serverless endpoint doesn't expose a voices endpoint.
        Voices are bundled into the Docker image and must be configured
        in AgentWire config.

        Returns:
            Empty list (voices must be configured separately).
        """
        # RunPod endpoint doesn't expose voices API
        # Voices are bundled into the Docker image
        return []

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
