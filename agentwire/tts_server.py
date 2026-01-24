#!/usr/bin/env python3
"""AgentWire TTS Server - Multi-backend TTS with Voice Cloning + Whisper Transcription

Supported backends:
  - chatterbox: Chatterbox Turbo TTS (default)
  - qwen-0.6b: Qwen3-TTS 0.6B model
  - qwen-1.7b: Qwen3-TTS 1.7B model

Run via:
    agentwire tts start                    # Start with default backend
    agentwire tts start --backend qwen-0.6b # Start with Qwen3-TTS 0.6B
    agentwire tts stop                     # Stop the server
    agentwire tts status                   # Check status

Or run directly:
    TTS_BACKEND=qwen-1.7b uvicorn agentwire.tts_server:app --host 0.0.0.0 --port 8100
"""

import io
import os
import tempfile
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
import torchaudio
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from faster_whisper import WhisperModel
from pydantic import BaseModel

# GPU Optimizations (significant speedup on CUDA devices)
torch.backends.cudnn.benchmark = True  # Auto-tune for input sizes
torch.set_float32_matmul_precision('high')  # TensorFloat-32 on Ampere GPUs

# Backend selection via env var (set by CLI)
TTS_BACKEND = os.environ.get("TTS_BACKEND", "chatterbox")

# Global model references
tts_engine: Optional["TTSEngine"] = None
whisper_model = None

# Voice profiles directory (supports VOICES_DIR env var for Docker)
VOICES_DIR = Path(os.environ.get("VOICES_DIR", str(Path.home() / ".agentwire" / "voices")))


# === TTS Engine Abstraction ===

class TTSEngine(ABC):
    """Abstract base class for TTS backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name."""
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate in Hz."""
        pass

    @abstractmethod
    def generate(
        self,
        text: str,
        voice_path: Optional[str] = None,
        exaggeration: float = 0.0,
        cfg_weight: float = 0.0,
    ) -> torch.Tensor:
        """Generate audio from text.

        Args:
            text: Text to synthesize
            voice_path: Path to voice reference audio for cloning
            exaggeration: Expression exaggeration (backend-specific)
            cfg_weight: CFG weight (backend-specific)

        Returns:
            Audio tensor of shape (1, samples)
        """
        pass


class ChatterboxEngine(TTSEngine):
    """Chatterbox Turbo TTS backend."""

    def __init__(self):
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        print("Loading Chatterbox Turbo model...")
        self._model = ChatterboxTurboTTS.from_pretrained(device="cuda")
        print(f"Chatterbox loaded! Sample rate: {self._model.sr}")

    @property
    def name(self) -> str:
        return "Chatterbox Turbo"

    @property
    def sample_rate(self) -> int:
        return self._model.sr

    def generate(
        self,
        text: str,
        voice_path: Optional[str] = None,
        exaggeration: float = 0.0,
        cfg_weight: float = 0.0,
    ) -> torch.Tensor:
        return self._model.generate(
            text,
            audio_prompt_path=voice_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
        )


class QwenTTSEngine(TTSEngine):
    """Qwen3-TTS backend (0.6B or 1.7B)."""

    def __init__(self, model_size: str = "0.6b"):
        from qwen_tts import Qwen3TTSModel

        model_id = f"Qwen/Qwen3-TTS-12Hz-{model_size.upper()}-Base"
        print(f"Loading Qwen3-TTS {model_size.upper()} model...")

        # Check for FlashAttention support
        try:
            import flash_attn  # noqa: F401
            attn_impl = "flash_attention_2"
            print("  Using FlashAttention 2")
        except ImportError:
            attn_impl = "sdpa"
            print("  Using SDPA (install flash-attn for better performance)")

        self._model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map="cuda:0",
            dtype=torch.bfloat16,
            attn_implementation=attn_impl,
        )
        self._model_size = model_size
        # Qwen3-TTS outputs at 24kHz
        self._sample_rate = 24000

        # Try to compile the underlying model for faster inference
        try:
            if hasattr(self._model, 'model'):
                print("  Applying torch.compile (max-autotune mode)...")
                self._model.model = torch.compile(
                    self._model.model,
                    mode="max-autotune",
                )
                print("  torch.compile applied!")
        except Exception as e:
            print(f"  torch.compile failed: {e}")

        print(f"Qwen3-TTS {model_size.upper()} loaded! Sample rate: {self._sample_rate}")

    @property
    def name(self) -> str:
        return f"Qwen3-TTS {self._model_size.upper()}"

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def generate(
        self,
        text: str,
        voice_path: Optional[str] = None,
        exaggeration: float = 0.0,
        cfg_weight: float = 0.0,
    ) -> torch.Tensor:
        import numpy as np

        if not voice_path:
            raise ValueError("Qwen3-TTS Base model requires a voice reference. Provide a voice name.")

        # Use x_vector_only_mode=True for speaker embedding only (no transcript needed)
        wavs, sr = self._model.generate_voice_clone(
            text=text,
            language="English",
            ref_audio=voice_path,
            x_vector_only_mode=True,
        )

        # Convert to tensor - wavs is List[np.ndarray]
        if isinstance(wavs, list):
            wav = wavs[0]
        else:
            wav = wavs

        if isinstance(wav, np.ndarray):
            wav = torch.from_numpy(wav)

        if wav.dim() == 1:
            wav = wav.unsqueeze(0)

        return wav


def create_tts_engine(backend: str) -> TTSEngine:
    """Factory function to create TTS engine by name."""
    if backend == "chatterbox":
        return ChatterboxEngine()
    elif backend == "qwen-0.6b":
        return QwenTTSEngine("0.6b")
    elif backend == "qwen-1.7b":
        return QwenTTSEngine("1.7b")
    else:
        raise ValueError(f"Unknown TTS backend: {backend}. Options: chatterbox, qwen-0.6b, qwen-1.7b")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    global tts_engine, whisper_model
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"TTS Backend: {TTS_BACKEND}")
    print(f"  cuDNN benchmark: {torch.backends.cudnn.benchmark}")
    print(f"  TF32 matmul: {torch.get_float32_matmul_precision()}")

    tts_engine = create_tts_engine(TTS_BACKEND)
    print(f"TTS engine: {tts_engine.name}")

    print("Loading Whisper model (large-v3)...")
    whisper_model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    print("Whisper model loaded!")

    print(f"Voices directory: {VOICES_DIR}")
    if TTS_BACKEND == "chatterbox":
        print("Paralinguistic tags supported: [laugh], [chuckle], [cough], [sigh], [gasp]")
    yield
    print("Shutting down...")


app = FastAPI(title="AgentWire TTS Server", lifespan=lifespan)


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    exaggeration: float = 0.0  # Turbo default
    cfg_weight: float = 0.0    # Turbo default


@app.post("/tts")
async def generate_tts(request: TTSRequest):
    """Generate TTS audio from text, optionally with a cloned voice."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    voice_path = None
    if request.voice:
        voice_file = VOICES_DIR / f"{request.voice}.wav"
        if not voice_file.exists():
            raise HTTPException(status_code=404, detail=f"Voice '{request.voice}' not found")
        voice_path = str(voice_file)

    try:
        wav = tts_engine.generate(
            request.text,
            voice_path=voice_path,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
        )

        buffer = io.BytesIO()
        torchaudio.save(buffer, wav, tts_engine.sample_rate, format="wav")
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=speech.wav"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voices/{name}")
async def upload_voice(name: str, file: UploadFile = File(...)):
    """Upload a voice reference audio (~10s WAV recommended)."""
    if not name.isalnum() and "_" not in name and "-" not in name:
        raise HTTPException(status_code=400, detail="Voice name must be alphanumeric")

    voice_path = VOICES_DIR / f"{name}.wav"

    # Save uploaded file
    content = await file.read()

    # Convert to proper format if needed (24kHz mono)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        waveform, sr = torchaudio.load(tmp_path)

        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Resample to 24kHz if needed
        if sr != 24000:
            resampler = torchaudio.transforms.Resample(sr, 24000)
            waveform = resampler(waveform)

        # Save processed audio
        torchaudio.save(str(voice_path), waveform, 24000)

        duration = waveform.shape[1] / 24000
        return {
            "name": name,
            "duration": round(duration, 2),
            "message": f"Voice '{name}' saved ({duration:.1f}s)"
        }
    finally:
        os.unlink(tmp_path)


@app.get("/voices")
async def list_voices():
    """List all available voice profiles."""
    voices = []
    for f in VOICES_DIR.glob("*.wav"):
        waveform, sr = torchaudio.load(str(f))
        duration = waveform.shape[1] / sr
        voices.append({"name": f.stem, "duration": round(duration, 2)})
    return {"voices": voices}


@app.delete("/voices/{name}")
async def delete_voice(name: str):
    """Delete a voice profile."""
    voice_path = VOICES_DIR / f"{name}.wav"
    if not voice_path.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{name}' not found")
    voice_path.unlink()
    return {"message": f"Voice '{name}' deleted"}


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "backend": TTS_BACKEND,
        "tts_loaded": tts_engine is not None,
        "tts_engine": tts_engine.name if tts_engine else None,
        "whisper_loaded": whisper_model is not None
    }


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio using Whisper."""
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    # Save uploaded audio to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Transcribe with Whisper
        segments, info = whisper_model.transcribe(
            tmp_path,
            beam_size=5,
            language="en",
            vad_filter=True,  # Filter out silence
        )

        # Combine all segments
        text = " ".join(segment.text.strip() for segment in segments)

        return {
            "text": text,
            "language": info.language,
            "duration": info.duration
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
