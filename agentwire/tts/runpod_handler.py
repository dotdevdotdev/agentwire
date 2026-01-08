#!/usr/bin/env python3
"""RunPod Traditional Serverless handler for AgentWire TTS.

This handler runs on RunPod GPU workers using the traditional serverless architecture.
It processes TTS requests via the RunPod queue system.

Traditional Serverless architecture:
- Queue-based requests via RunPod API/SDK
- Scales to zero when idle (pay-per-use)
- Job input: {"text": "...", "voice": "dotdev", ...}
- Job output: {"audio": "base64...", "sample_rate": 24000, "voice": "dotdev"}
- Custom voices are bundled into the Docker image
- Model is pre-downloaded during build for instant cold starts
"""

print("=" * 60)
print("AgentWire TTS RunPod Serverless Starting...")
print("=" * 60)

import base64
import io
from pathlib import Path
from typing import Optional

print("Importing dependencies...")
import runpod
import torch
import torchaudio

print("Dependencies imported successfully!")

# GPU optimizations
torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision('high')

# Global model reference (loaded once, reused across requests)
model = None

# Voices directory - bundled into Docker image
VOICES_DIR = Path("/voices")


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


def handler(job):
    """
    RunPod serverless handler function.

    Args:
        job: RunPod job object with job["input"] containing request data

    Expected input format:
        {
            "text": str,              # Required: text to synthesize
            "voice": str,             # Optional: voice name (e.g., "dotdev")
            "exaggeration": float,    # Optional: default 0.0
            "cfg_weight": float       # Optional: default 0.0
        }

    Returns:
        {
            "audio": str,             # base64-encoded WAV audio
            "sample_rate": int,       # audio sample rate (24000)
            "voice": str or None      # voice used (or None if default)
        }
    """
    job_input = job["input"]

    # Extract parameters
    text = job_input.get("text")
    voice = job_input.get("voice")
    exaggeration = job_input.get("exaggeration", 0.0)
    cfg_weight = job_input.get("cfg_weight", 0.0)

    print(f"Received TTS request: text='{text[:50] if text else ''}...', voice={voice}")

    # Validate input
    if not text or not text.strip():
        return {"error": "Text cannot be empty"}

    try:
        # Load model (cached after first request)
        tts_model = load_model()

        # Resolve voice file if specified
        audio_prompt_path = None
        if voice:
            voice_path = VOICES_DIR / f"{voice}.wav"
            if not voice_path.exists():
                available_voices = [p.stem for p in VOICES_DIR.glob('*.wav')]
                return {
                    "error": f"Voice '{voice}' not found. Available voices: {available_voices}"
                }
            audio_prompt_path = str(voice_path)

        # Generate TTS
        print(f"Generating TTS with model (exaggeration={exaggeration}, cfg_weight={cfg_weight})...")
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

        print(f"TTS generation complete! Audio size: {len(audio_bytes)} bytes")

        return {
            "audio": audio_b64,
            "sample_rate": tts_model.sr,
            "voice": voice,
        }

    except Exception as e:
        print(f"ERROR during TTS generation: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == "__main__":
    print("Starting RunPod serverless worker...")
    print(f"Voices directory: {VOICES_DIR}")
    if VOICES_DIR.exists():
        voices = list(VOICES_DIR.glob('*.wav'))
        print(f"Voices available: {[v.stem for v in voices] if voices else 'None'}")
    else:
        print("Voices directory does not exist!")

    # Start RunPod serverless worker
    runpod.serverless.start({"handler": handler})
