"""Chatterbox TTS Engine"""

from pathlib import Path
from typing import Iterator

import torch

from ..base import TTSCapabilities, TTSEngine, TTSRequest, TTSResult


class ChatterboxEngine(TTSEngine):
    """Chatterbox Turbo TTS engine.

    Supports:
    - Voice cloning from reference audio
    - Paralinguistic tags: [laugh], [chuckle], [cough], [sigh], [gasp]
    - Exaggeration and CFG weight controls
    """

    def __init__(self, device: str = "cuda", voices_dir: Path | None = None):
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        print("Loading Chatterbox Turbo model...")
        self._model = ChatterboxTurboTTS.from_pretrained(device=device)
        self._device = device
        self._voices_dir = voices_dir
        print(f"Chatterbox loaded! Sample rate: {self._model.sr}")

    @property
    def name(self) -> str:
        return "Chatterbox Turbo"

    @property
    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            voice_cloning=True,
            voice_design=False,
            preset_voices=[],
            emotion_control=False,
            paralinguistic_tags=True,
            streaming=False,
            languages=["English"],
        )

    @property
    def sample_rate(self) -> int:
        return self._model.sr

    def generate(self, request: TTSRequest) -> TTSResult:
        """Generate audio using Chatterbox.

        Args:
            request: TTS request with text, voice, exaggeration, cfg_weight

        Returns:
            TTSResult with audio tensor
        """
        voice_path = None
        if request.voice and self._voices_dir:
            voice_file = self._voices_dir / f"{request.voice}.wav"
            if voice_file.exists():
                voice_path = str(voice_file)

        wav = self._model.generate(
            request.text,
            audio_prompt_path=voice_path,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
        )

        return TTSResult(audio=wav, sample_rate=self._model.sr)

    def unload(self) -> None:
        """Release model from GPU memory."""
        if hasattr(self, "_model"):
            del self._model
            self._model = None


class ChatterboxStreamingEngine(TTSEngine):
    """Chatterbox TTS with streaming support.

    Requires chatterbox-streaming package.
    """

    def __init__(self, device: str = "cuda", voices_dir: Path | None = None):
        try:
            from chatterbox_streaming import ChatterboxStreamingTTS
        except ImportError:
            raise ImportError(
                "chatterbox-streaming not installed. "
                "Install with: pip install chatterbox-streaming"
            )

        print("Loading Chatterbox Streaming model...")
        self._model = ChatterboxStreamingTTS.from_pretrained(device=device)
        self._device = device
        self._voices_dir = voices_dir
        print(f"Chatterbox Streaming loaded! Sample rate: {self._model.sr}")

    @property
    def name(self) -> str:
        return "Chatterbox Streaming"

    @property
    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            voice_cloning=True,
            voice_design=False,
            preset_voices=[],
            emotion_control=False,
            paralinguistic_tags=True,
            streaming=True,
            languages=["English"],
        )

    @property
    def sample_rate(self) -> int:
        return self._model.sr

    def generate(self, request: TTSRequest) -> TTSResult:
        """Generate full audio (non-streaming)."""
        voice_path = None
        if request.voice and self._voices_dir:
            voice_file = self._voices_dir / f"{request.voice}.wav"
            if voice_file.exists():
                voice_path = str(voice_file)

        wav = self._model.generate(
            request.text,
            audio_prompt_path=voice_path,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
        )

        return TTSResult(audio=wav, sample_rate=self._model.sr)

    def generate_stream(self, request: TTSRequest) -> Iterator[bytes]:
        """Generate audio as streaming chunks."""
        import io
        import torchaudio

        voice_path = None
        if request.voice and self._voices_dir:
            voice_file = self._voices_dir / f"{request.voice}.wav"
            if voice_file.exists():
                voice_path = str(voice_file)

        for audio_chunk, metrics in self._model.generate_stream(
            request.text,
            audio_prompt_path=voice_path,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
        ):
            # Convert chunk to WAV bytes
            buffer = io.BytesIO()
            torchaudio.save(buffer, audio_chunk, self._model.sr, format="wav")
            buffer.seek(0)
            yield buffer.read()

    def unload(self) -> None:
        """Release model from GPU memory."""
        if hasattr(self, "_model"):
            del self._model
            self._model = None
