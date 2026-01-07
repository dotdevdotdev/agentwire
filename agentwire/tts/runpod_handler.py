#!/usr/bin/env python3
"""RunPod serverless handler for AgentWire TTS.

This handler runs on RunPod GPU workers and processes TTS requests.
It uses the same Chatterbox TTS backend as the local TTS server.

RunPod serverless architecture:
- Handler receives input dict with: text, voice, exaggeration, cfg_weight
- Loads Chatterbox TTS model once (cached between invocations)
- Generates audio and returns base64-encoded WAV
- Custom voices are bundled into the Docker image
"""

import base64
import io
import os
from pathlib import Path

import runpod
import torch
import torchaudio

# GPU optimizations
torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision('high')

# Global model reference (loaded once, reused across invocations)
model = None

# Voices directory - bundled into Docker image
VOICES_DIR = Path("/voices")


def load_model():
    """Load Chatterbox TTS model (runs once on worker startup)."""
    global model
    if model is None:
        print("Loading Chatterbox Turbo model...")
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        model = ChatterboxTurboTTS.from_pretrained(device="cuda")
        print(f"TTS model loaded! Sample rate: {model.sr}")
    return model


def handler(job):
    """RunPod serverless handler for TTS generation.

    Input:
        {
            "text": "Hello world",
            "voice": "bashbunni",  # Optional
            "exaggeration": 0.5,   # Optional (0.0-1.0)
            "cfg_weight": 0.5      # Optional (0.0-1.0)
        }

    Output:
        {
            "audio": "<base64-encoded WAV>",
            "sample_rate": 24000,
            "voice": "bashbunni"
        }
    """
    job_input = job["input"]

    # Validate input
    text = job_input.get("text", "").strip()
    if not text:
        return {"error": "Text cannot be empty"}

    voice = job_input.get("voice")
    exaggeration = job_input.get("exaggeration", 0.0)
    cfg_weight = job_input.get("cfg_weight", 0.0)

    # Load model (cached after first invocation)
    tts_model = load_model()

    # Resolve voice file if specified
    audio_prompt_path = None
    if voice:
        voice_path = VOICES_DIR / f"{voice}.wav"
        if not voice_path.exists():
            return {"error": f"Voice '{voice}' not found"}
        audio_prompt_path = str(voice_path)

    try:
        # Generate TTS
        wav = tts_model.generate(
            text,
            audio_prompt_path=audio_prompt_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
        )

        # Convert to WAV bytes
        buffer = io.BytesIO()
        torchaudio.save(buffer, wav, tts_model.sr, format="wav")
        buffer.seek(0)
        audio_bytes = buffer.read()

        # Encode to base64
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {
            "audio": audio_b64,
            "sample_rate": tts_model.sr,
            "voice": voice,
        }

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Start RunPod serverless worker
    runpod.serverless.start({"handler": handler})
