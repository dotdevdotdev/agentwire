"""Qwen3-TTS Base Engine (Voice Cloning)"""

from pathlib import Path
from typing import Iterator, Literal

import numpy as np
import torch

from ..base import TTSCapabilities, TTSEngine, TTSRequest, TTSResult

SUPPORTED_LANGUAGES = [
    "Chinese",
    "English",
    "Japanese",
    "Korean",
    "German",
    "French",
    "Russian",
    "Portuguese",
    "Spanish",
    "Italian",
]


class QwenBaseEngine(TTSEngine):
    """Qwen3-TTS Base model for voice cloning.

    Supports:
    - Voice cloning from 3+ second reference audio
    - 10 languages
    - Streaming output

    Does NOT support:
    - Zero-shot synthesis (requires voice reference)
    - Emotion/instruct control
    - Paralinguistic tags
    """

    def __init__(
        self,
        model_size: Literal["0.6b", "1.7b"] = "1.7b",
        device: str = "cuda:0",
        dtype: torch.dtype = torch.bfloat16,
        compile_model: bool = True,
        compile_mode: str = "reduce-overhead",
        voices_dir: Path | None = None,
    ):
        from qwen_tts import Qwen3TTSModel

        model_id = f"Qwen/Qwen3-TTS-12Hz-{model_size.upper()}-Base"
        print(f"Loading Qwen3-TTS {model_size.upper()} Base model...")

        # Check for FlashAttention
        try:
            import flash_attn  # noqa: F401

            attn_impl = "flash_attention_2"
            print("  Using FlashAttention 2")
        except ImportError:
            attn_impl = "sdpa"
            print("  Using SDPA")

        self._model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device,
            dtype=dtype,
            attn_implementation=attn_impl,
        )
        self._model_size = model_size
        self._sample_rate = 24000
        self._voices_dir = voices_dir

        # Apply torch.compile for faster inference
        if compile_model:
            try:
                if hasattr(self._model, "model"):
                    print(f"  Applying torch.compile ({compile_mode} mode)...")
                    self._model.model = torch.compile(
                        self._model.model,
                        mode=compile_mode,
                    )
                    print("  torch.compile applied!")
            except Exception as e:
                print(f"  torch.compile failed: {e}")

        print(f"Qwen3-TTS {model_size.upper()} Base loaded! Sample rate: {self._sample_rate}")

    @property
    def name(self) -> str:
        return f"Qwen3-TTS {self._model_size.upper()} Base"

    @property
    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            voice_cloning=True,
            voice_design=False,
            preset_voices=[],
            emotion_control=False,
            paralinguistic_tags=False,
            streaming=True,
            languages=SUPPORTED_LANGUAGES,
        )

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def generate(self, request: TTSRequest) -> TTSResult:
        """Generate audio using voice cloning.

        Args:
            request: TTS request with text, voice (required), language

        Returns:
            TTSResult with audio tensor

        Raises:
            ValueError: If no voice reference provided
        """
        voice_path = None
        if request.voice and self._voices_dir:
            voice_file = self._voices_dir / f"{request.voice}.wav"
            if voice_file.exists():
                voice_path = str(voice_file)

        if not voice_path:
            raise ValueError(
                "Qwen3-TTS Base model requires a voice reference. "
                "Provide a voice name that exists in the voices directory."
            )

        # Use x_vector_only_mode for speaker embedding (no transcript needed)
        wavs, sr = self._model.generate_voice_clone(
            text=request.text,
            language=request.language,
            ref_audio=voice_path,
            x_vector_only_mode=True,
        )

        # Convert to tensor
        wav = wavs[0] if isinstance(wavs, list) else wavs
        if isinstance(wav, np.ndarray):
            wav = torch.from_numpy(wav)
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)

        return TTSResult(audio=wav, sample_rate=sr)

    def generate_stream(self, request: TTSRequest) -> Iterator[bytes]:
        """Generate audio as streaming chunks.

        Note: Qwen3-TTS supports streaming natively with ~97ms first-packet latency.
        """
        import io

        import torchaudio

        voice_path = None
        if request.voice and self._voices_dir:
            voice_file = self._voices_dir / f"{request.voice}.wav"
            if voice_file.exists():
                voice_path = str(voice_file)

        if not voice_path:
            raise ValueError("Qwen3-TTS Base model requires a voice reference.")

        # Generate with streaming enabled
        wavs, sr = self._model.generate_voice_clone(
            text=request.text,
            language=request.language,
            ref_audio=voice_path,
            x_vector_only_mode=True,
            non_streaming_mode=False,  # Enable streaming
        )

        # For now, yield the full result as a single chunk
        # TODO: Implement proper chunk-by-chunk streaming
        wav = wavs[0] if isinstance(wavs, list) else wavs
        if isinstance(wav, np.ndarray):
            wav = torch.from_numpy(wav)
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)

        buffer = io.BytesIO()
        torchaudio.save(buffer, wav, sr, format="wav")
        buffer.seek(0)
        yield buffer.read()

    def unload(self) -> None:
        """Release model from GPU memory."""
        if hasattr(self, "_model"):
            del self._model
            self._model = None
