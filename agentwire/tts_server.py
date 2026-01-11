#!/usr/bin/env python3
"""AgentWire TTS Server - Chatterbox TTS with Voice Cloning + Whisper Transcription

This is the canonical TTS server for AgentWire. Run via:
    agentwire tts start       # Start in tmux session
    agentwire tts stop        # Stop the server
    agentwire tts status      # Check status

Or run directly:
    uvicorn agentwire.tts_server:app --host 0.0.0.0 --port 8100
"""

import io
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import torch
import torchaudio
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from faster_whisper import WhisperModel

# GPU Optimizations (significant speedup on CUDA devices)
torch.backends.cudnn.benchmark = True  # Auto-tune for input sizes
torch.set_float32_matmul_precision('high')  # TensorFloat-32 on Ampere GPUs

# Global model references
model = None
whisper_model = None

# Voice profiles directory
VOICES_DIR = Path.home() / ".agentwire" / "voices"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    global model, whisper_model
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading Chatterbox Turbo model...")
    print(f"  cuDNN benchmark: {torch.backends.cudnn.benchmark}")
    print(f"  TF32 matmul: {torch.get_float32_matmul_precision()}")
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    model = ChatterboxTurboTTS.from_pretrained(device="cuda")
    print(f"TTS model loaded! Sample rate: {model.sr}")

    print("Loading Whisper model (large-v3)...")
    whisper_model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    print("Whisper model loaded!")

    print(f"Voices directory: {VOICES_DIR}")
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

    audio_prompt_path = None
    if request.voice:
        voice_path = VOICES_DIR / f"{request.voice}.wav"
        if not voice_path.exists():
            raise HTTPException(status_code=404, detail=f"Voice '{request.voice}' not found")
        audio_prompt_path = str(voice_path)

    try:
        wav = model.generate(
            request.text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
        )

        buffer = io.BytesIO()
        torchaudio.save(buffer, wav, model.sr, format="wav")
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
        "tts_loaded": model is not None,
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
