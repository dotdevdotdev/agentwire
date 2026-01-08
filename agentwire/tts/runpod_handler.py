#!/usr/bin/env python3
"""RunPod Load Balancer handler for AgentWire TTS.

This handler runs on RunPod GPU workers as a FastAPI HTTP server.
It processes TTS requests directly via HTTP endpoints.

Load Balancer architecture:
- FastAPI server listens on port 8000
- POST /tts endpoint receives: text, voice, exaggeration, cfg_weight
- Loads Chatterbox TTS model once (cached between requests)
- Generates audio and returns base64-encoded WAV
- Custom voices are bundled into the Docker image
"""

print("=" * 60)
print("AgentWire TTS RunPod Load Balancer Starting...")
print("=" * 60)

import base64
import io
import os
from pathlib import Path
from typing import Optional

print("Importing dependencies...")
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import torchaudio
import uvicorn

print("Dependencies imported successfully!")

# GPU optimizations
torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision('high')

# Global model reference (loaded once, reused across requests)
model = None

# Voices directory - bundled into Docker image
VOICES_DIR = Path("/voices")

# FastAPI app
app = FastAPI(title="AgentWire TTS", version="1.0.0")


class TTSRequest(BaseModel):
    """TTS generation request."""
    text: str
    voice: Optional[str] = None
    exaggeration: float = 0.0
    cfg_weight: float = 0.0


class TTSResponse(BaseModel):
    """TTS generation response."""
    audio: str  # base64-encoded WAV
    sample_rate: int
    voice: Optional[str] = None


def load_model():
    """Load Chatterbox TTS model (runs once on first request)."""
    global model
    if model is None:
        try:
            print("Loading Chatterbox Turbo model...")
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            print("Chatterbox module imported, creating model...")
            model = ChatterboxTurboTTS.from_pretrained(device="cuda")
            print(f"TTS model loaded! Sample rate: {model.sr}")
        except Exception as e:
            print(f"ERROR loading model: {e}")
            import traceback
            traceback.print_exc()
            raise
    return model


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "AgentWire TTS",
        "status": "ready",
        "model_loaded": model is not None
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """Generate TTS audio from text.

    Args:
        request: TTSRequest with text, optional voice, exaggeration, cfg_weight

    Returns:
        TTSResponse with base64-encoded WAV audio
    """
    print(f"Received TTS request: text='{request.text[:50]}...', voice={request.voice}")

    # Validate input
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Load model (cached after first request)
    tts_model = load_model()

    # Resolve voice file if specified
    audio_prompt_path = None
    if request.voice:
        voice_path = VOICES_DIR / f"{request.voice}.wav"
        if not voice_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Voice '{request.voice}' not found. Available voices: {[p.stem for p in VOICES_DIR.glob('*.wav')]}"
            )
        audio_prompt_path = str(voice_path)

    try:
        # Generate TTS
        print(f"Generating TTS with model (exaggeration={request.exaggeration}, cfg_weight={request.cfg_weight})...")
        wav = tts_model.generate(
            request.text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
        )

        # Convert to WAV bytes
        buffer = io.BytesIO()
        torchaudio.save(buffer, wav, tts_model.sr, format="wav")
        buffer.seek(0)
        audio_bytes = buffer.read()

        # Encode to base64
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        print(f"TTS generation complete! Audio size: {len(audio_bytes)} bytes")

        return TTSResponse(
            audio=audio_b64,
            sample_rate=tts_model.sr,
            voice=request.voice,
        )

    except Exception as e:
        print(f"ERROR during TTS generation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("Starting FastAPI server on port 8000...")
    print(f"Voices directory: {VOICES_DIR}")
    if VOICES_DIR.exists():
        voices = list(VOICES_DIR.glob('*.wav'))
        print(f"Voices available: {[v.stem for v in voices] if voices else 'None'}")
    else:
        print("Voices directory does not exist!")

    # Start FastAPI server with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
