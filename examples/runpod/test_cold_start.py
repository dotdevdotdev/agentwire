#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Test cold start time after worker has scaled to zero."""

import os
import sys
import time
import base64
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID", "dw0aqos9tvt95h")

if not RUNPOD_API_KEY:
    print("Error: RUNPOD_API_KEY not found in environment")
    sys.exit(1)

def test_cold_start():
    """Test cold start from idle state."""

    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    payload = {
        "input": {
            "text": "Testing cold start performance after worker has scaled to zero.",
            "voice": "dotdev"
        }
    }

    print("=" * 60)
    print("Cold Start Performance Test")
    print("=" * 60)
    print()
    print("Worker should be idle (scaled to zero)")
    print("This test measures:")
    print("  - Worker initialization time")
    print("  - Model loading time")
    print("  - TTS generation time")
    print()
    print("Starting cold start test...")
    print()

    start_time = time.time()

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()

        elapsed = time.time() - start_time
        result = response.json()

        if result.get("status") == "FAILED":
            print(f"✗ Failed: {result}")
            return False

        output = result.get("output")
        if not output or "error" in output:
            print(f"✗ Error: {output}")
            return False

        # Extract audio
        audio_b64 = output.get("audio")
        sample_rate = output.get("sample_rate")
        voice_used = output.get("voice")

        audio_bytes = base64.b64decode(audio_b64)

        # Save to file
        output_file = Path("test_cold_start.wav")
        output_file.write_bytes(audio_bytes)

        print("=" * 60)
        print("✅ Cold Start Complete!")
        print("=" * 60)
        print()
        print(f"Total time: {elapsed:.2f}s")
        print()
        print("Breakdown estimate:")
        print(f"  Worker initialization: ~{max(0, elapsed - 5):.1f}s")
        print(f"  TTS generation: ~5.0s")
        print()
        print(f"Sample rate: {sample_rate}")
        print(f"Voice: {voice_used}")
        print(f"Audio size: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.1f} KB)")
        print(f"Saved to: {output_file}")
        print()

        # Play audio
        import subprocess
        print("Playing audio...")
        subprocess.run(["afplay", str(output_file)])

        return True

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"✗ Request timed out after {elapsed:.2f}s")
        return False
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ Exception after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_cold_start()
    sys.exit(0 if success else 1)
