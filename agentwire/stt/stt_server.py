#!/usr/bin/env python3
"""STT server using faster-whisper.

Provides HTTP endpoint for speech-to-text transcription.
Supports both GPU (CUDA) and CPU execution.
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from faster_whisper import WhisperModel

app = FastAPI(title="AgentWire STT Server")

# Global model instance (loaded once)
whisper_model = None


def load_model():
    """Load Whisper model on startup."""
    global whisper_model

    if whisper_model is not None:
        return whisper_model

    model_size = os.getenv("WHISPER_MODEL", "base")
    device = os.getenv("WHISPER_DEVICE", "cpu")

    print(f"Loading Whisper model: {model_size} on {device}")

    # Load model with appropriate device
    whisper_model = WhisperModel(
        model_size,
        device=device,
        compute_type="float16" if device == "cuda" else "int8"
    )

    print(f"Whisper model loaded: {model_size} ({device})")
    return whisper_model


@app.on_event("startup")
async def startup_event():
    """Load model on startup."""
    load_model()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model_loaded": whisper_model is not None,
        "model": os.getenv("WHISPER_MODEL", "base"),
        "device": os.getenv("WHISPER_DEVICE", "cpu")
    }


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio file to text.

    Args:
        file: Audio file (WAV, MP3, M4A, etc.)

    Returns:
        {
            "text": str,
            "language": str,
            "duration": float
        }
    """
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    # Save uploaded audio to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Transcribe with Whisper
        language = os.getenv("WHISPER_LANGUAGE", "en")

        segments, info = whisper_model.transcribe(
            tmp_path,
            beam_size=5,
            language=language if language != "auto" else None,
            vad_filter=True,  # Voice activity detection to filter silence
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
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("STT_PORT", "8100"))
    host = os.getenv("STT_HOST", "0.0.0.0")

    print(f"Starting AgentWire STT server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
