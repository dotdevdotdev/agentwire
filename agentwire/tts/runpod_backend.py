"""RunPod serverless TTS backend."""

import asyncio
import base64
import logging

import aiohttp

from .base import TTSBackend

logger = logging.getLogger(__name__)


class RunPodTTS(TTSBackend):
    """TTS backend using RunPod serverless infrastructure.

    This backend calls a deployed RunPod serverless endpoint that runs
    the Chatterbox TTS model on GPU workers.

    Uses async run + polling to handle cold starts gracefully.
    """

    def __init__(
        self,
        endpoint_id: str,
        api_key: str,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        timeout: int = 120,
    ):
        """Initialize RunPod TTS backend.

        Args:
            endpoint_id: RunPod endpoint ID (e.g., "abc123xyz")
            api_key: RunPod API key for authentication
            exaggeration: Voice exaggeration parameter (0.0-1.0)
            cfg_weight: CFG weight parameter (0.0-1.0)
            timeout: Total timeout in seconds including cold start (default: 120)
        """
        self.endpoint_id = endpoint_id
        self.api_key = api_key
        self.exaggeration = exaggeration
        self.cfg_weight = cfg_weight
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

        # RunPod API endpoints
        self.run_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
        self.status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status"

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

        Uses async run + polling to handle cold starts gracefully.
        Cold starts are logged so the system can track them.

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
                "action": "generate",
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
            # Submit job (async)
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.post(
                self.run_url, json=payload, headers=headers, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    logger.error(f"RunPod run failed: {resp.status}")
                    return None

                data = await resp.json()
                job_id = data.get("id")
                if not job_id:
                    logger.error("RunPod run returned no job ID")
                    return None

            # Poll for completion
            start_time = asyncio.get_event_loop().time()
            poll_interval = 0.5
            cold_start_logged = False

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > self.timeout:
                    logger.error(f"RunPod job {job_id} timed out after {self.timeout}s")
                    return None

                # Check status
                status_timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(
                    f"{self.status_url}/{job_id}", headers=headers, timeout=status_timeout
                ) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(poll_interval)
                        continue

                    data = await resp.json()
                    status = data.get("status")

                    if status == "IN_QUEUE":
                        if not cold_start_logged:
                            logger.info(f"RunPod job {job_id}: cold start (IN_QUEUE)")
                            cold_start_logged = True
                        await asyncio.sleep(poll_interval)
                        continue

                    elif status == "IN_PROGRESS":
                        await asyncio.sleep(poll_interval)
                        continue

                    elif status == "COMPLETED":
                        output = data.get("output", {})
                        if "error" in output:
                            logger.error(f"RunPod job {job_id} error: {output.get('error')}")
                            return None

                        audio_b64 = output.get("audio", "")
                        if not audio_b64:
                            logger.error(f"RunPod job {job_id}: no audio in output")
                            return None

                        if cold_start_logged:
                            logger.info(f"RunPod job {job_id}: completed after cold start ({elapsed:.1f}s)")
                        else:
                            logger.debug(f"RunPod job {job_id}: completed ({elapsed:.1f}s)")

                        return base64.b64decode(audio_b64)

                    elif status == "FAILED":
                        error = data.get("error", "unknown error")
                        logger.error(f"RunPod job {job_id} failed: {error}")
                        return None

                    else:
                        # Unknown status, keep polling
                        await asyncio.sleep(poll_interval)

        except aiohttp.ClientError as e:
            logger.error(f"RunPod request failed: {e}")
            return None
        except base64.binascii.Error as e:
            logger.error(f"RunPod audio decode failed: {e}")
            return None

    async def get_voices(self) -> list[str]:
        """Get list of available voices from RunPod endpoint.

        Queries the RunPod endpoint's list_voices action to get all available
        voices (both bundled and network volume voices).

        Returns:
            List of voice names, or empty list if query fails.
        """
        session = await self._get_session()

        payload = {"input": {"action": "list_voices"}}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Use runsync for quick list_voices call (no cold start needed for this)
        runsync_url = f"https://api.runpod.ai/v2/{self.endpoint_id}/runsync"

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.post(
                runsync_url, json=payload, headers=headers, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()

                # Check RunPod status
                if data.get("status") == "error":
                    return []

                # Extract output
                output = data.get("output", {})
                if "error" in output:
                    return []

                # Return voices list
                voices = output.get("voices", [])
                return voices if isinstance(voices, list) else []

        except aiohttp.ClientError:
            return []

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
