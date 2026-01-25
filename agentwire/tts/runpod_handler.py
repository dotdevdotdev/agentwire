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

Network Volume Support:
- Bundled voices: /voices/ (baked into image)
- Network voices: /runpod-volume/ (persistent storage, auto-mounted when volume attached)
- Upload voices via job: {"action": "upload_voice", "voice_name": "...", "audio_base64": "..."}
"""

print("=" * 60)
print("AgentWire TTS RunPod Serverless Starting...")
print("=" * 60)

import base64  # noqa: E402
import io  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import List, Optional  # noqa: E402

print("Importing dependencies...")
import runpod  # noqa: E402
import torch  # noqa: E402
import torchaudio  # noqa: E402

print("Dependencies imported successfully!")

# GPU optimizations
torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision('high')

# Global model reference (loaded once, reused across requests)
model = None

# Voices directories
BUNDLED_VOICES_DIR = Path("/voices")  # Bundled into Docker image
NETWORK_VOICES_DIR = Path("/runpod-volume")  # Network volume (persistent, auto-mounted by RunPod)


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


def find_voice(voice_name: str) -> Optional[Path]:
    """Find voice file in bundled or network directories.

    Checks bundled voices first (faster), then network volume.
    Returns path to voice file or None if not found.
    """
    # Check bundled voices first
    bundled_path = BUNDLED_VOICES_DIR / f"{voice_name}.wav"
    if bundled_path.exists():
        print(f"Found voice '{voice_name}' in bundled directory")
        return bundled_path

    # Check network volume
    if NETWORK_VOICES_DIR.exists():
        network_path = NETWORK_VOICES_DIR / f"{voice_name}.wav"
        if network_path.exists():
            print(f"Found voice '{voice_name}' in network volume")
            return network_path

    return None


def list_all_voices() -> List[str]:
    """List all available voices from both directories."""
    voices = set()

    # Bundled voices
    if BUNDLED_VOICES_DIR.exists():
        voices.update(p.stem for p in BUNDLED_VOICES_DIR.glob('*.wav'))

    # Network voices
    if NETWORK_VOICES_DIR.exists():
        voices.update(p.stem for p in NETWORK_VOICES_DIR.glob('*.wav'))

    return sorted(list(voices))


def upload_voice(voice_name: str, audio_base64: str) -> dict:
    """Upload a voice clone to network volume.

    Args:
        voice_name: Name for the voice (without .wav extension)
        audio_base64: Base64-encoded WAV audio (~10 seconds)

    Returns:
        {"success": bool, "message": str, "voice_name": str}
    """
    try:
        # Ensure network volume directory exists
        if not NETWORK_VOICES_DIR.exists():
            NETWORK_VOICES_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Created network voices directory: {NETWORK_VOICES_DIR}")

        # Decode audio
        audio_bytes = base64.b64decode(audio_base64)

        # Validate it's a WAV file (simple check)
        if not audio_bytes.startswith(b'RIFF'):
            return {
                "success": False,
                "error": "Invalid audio format. Must be WAV file."
            }

        # Save to network volume
        voice_path = NETWORK_VOICES_DIR / f"{voice_name}.wav"
        voice_path.write_bytes(audio_bytes)

        print(f"Voice '{voice_name}' uploaded to network volume ({len(audio_bytes)} bytes)")

        return {
            "success": True,
            "message": f"Voice '{voice_name}' uploaded successfully",
            "voice_name": voice_name,
            "size_bytes": len(audio_bytes)
        }

    except Exception as e:
        print(f"ERROR uploading voice '{voice_name}': {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def download_voice(voice_name: str) -> dict:
    """Download a voice clone as base64.

    Args:
        voice_name: Name of the voice (without .wav extension)

    Returns:
        {"success": bool, "voice_name": str, "audio_base64": str, "size_bytes": int}
    """
    try:
        voice_path = find_voice(voice_name)
        if not voice_path:
            available_voices = list_all_voices()
            return {
                "success": False,
                "error": f"Voice '{voice_name}' not found. Available voices: {available_voices}"
            }

        audio_bytes = voice_path.read_bytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        print(f"Voice '{voice_name}' downloaded ({len(audio_bytes)} bytes)")

        return {
            "success": True,
            "voice_name": voice_name,
            "audio_base64": audio_b64,
            "size_bytes": len(audio_bytes)
        }

    except Exception as e:
        print(f"ERROR downloading voice '{voice_name}': {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def handler(job):
    """
    RunPod serverless handler function.

    Args:
        job: RunPod job object with job["input"] containing request data

    Supported actions:
        1. Generate TTS (default):
            {
                "action": "generate",     # Optional, default
                "text": str,              # Required
                "voice": str,             # Optional
                "exaggeration": float,    # Optional: default 0.0
                "cfg_weight": float       # Optional: default 0.0
            }

        2. Upload voice:
            {
                "action": "upload_voice",
                "voice_name": str,        # Required
                "audio_base64": str       # Required: base64-encoded WAV
            }

        3. Download voice:
            {
                "action": "download_voice",
                "voice_name": str         # Required
            }

        4. List voices:
            {
                "action": "list_voices"
            }

    Returns:
        For generate: {"audio": str, "sample_rate": int, "voice": str}
        For upload: {"success": bool, "message": str, "voice_name": str}
        For download: {"success": bool, "voice_name": str, "audio_base64": str}
        For list: {"voices": List[str]}
    """
    job_input = job["input"]
    action = job_input.get("action", "generate")

    print(f"Received job with action: {action}")

    # Handle list_voices action
    if action == "list_voices":
        voices = list_all_voices()
        print(f"Available voices: {voices}")
        return {"voices": voices}

    # Handle upload_voice action
    if action == "upload_voice":
        voice_name = job_input.get("voice_name")
        audio_base64 = job_input.get("audio_base64")

        if not voice_name:
            return {"error": "voice_name is required"}
        if not audio_base64:
            return {"error": "audio_base64 is required"}

        return upload_voice(voice_name, audio_base64)

    # Handle download_voice action
    if action == "download_voice":
        voice_name = job_input.get("voice_name")

        if not voice_name:
            return {"error": "voice_name is required"}

        return download_voice(voice_name)

    # Handle generate action (default)
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
            voice_path = find_voice(voice)
            if not voice_path:
                available_voices = list_all_voices()
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
    print()
    print(f"Bundled voices directory: {BUNDLED_VOICES_DIR}")
    if BUNDLED_VOICES_DIR.exists():
        bundled = list(BUNDLED_VOICES_DIR.glob('*.wav'))
        print(f"  Bundled voices: {[v.stem for v in bundled] if bundled else 'None'}")
    else:
        print("  Bundled voices directory does not exist!")

    print()
    print(f"Network voices directory: {NETWORK_VOICES_DIR}")
    if NETWORK_VOICES_DIR.exists():
        network = list(NETWORK_VOICES_DIR.glob('*.wav'))
        print(f"  Network voices: {[v.stem for v in network] if network else 'None'}")
    else:
        print("  Network volume not mounted or empty")

    print()
    all_voices = list_all_voices()
    print(f"Total voices available: {all_voices if all_voices else 'None'}")
    print()

    # Start RunPod serverless worker
    runpod.serverless.start({"handler": handler})
