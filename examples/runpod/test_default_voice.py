#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Test RunPod TTS with default Chatterbox voice (no voice cloning)."""

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
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")

if not RUNPOD_API_KEY or not ENDPOINT_ID:
    print("Error: RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID must be set in environment")
    sys.exit(1)

def test_default_voice(text):
    """Test TTS with no voice parameter (default Chatterbox)."""

    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    # NO voice parameter - should use default Chatterbox
    payload = {
        "input": {
            "text": text,
            "exaggeration": 0.0,
            "cfg_weight": 0.0
        }
    }

    print(f"Testing default Chatterbox voice...")
    print(f"Text: {text}")
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
        if not output:
            print(f"✗ No output: {result}")
            return False

        if "error" in output:
            print(f"✗ Error: {output['error']}")
            return False

        # Extract audio
        audio_b64 = output.get("audio")
        sample_rate = output.get("sample_rate")
        voice_used = output.get("voice")

        audio_bytes = base64.b64decode(audio_b64)

        # Save to file
        output_file = Path("test_default_voice.wav")
        output_file.write_bytes(audio_bytes)

        print(f"✓ Success!")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Sample rate: {sample_rate}")
        print(f"  Voice returned: {voice_used}")
        print(f"  Audio size: {len(audio_bytes)} bytes")
        print(f"  Saved to: {output_file}")

        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ Exception after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Default Chatterbox Voice Test (No Voice Cloning)")
    print("=" * 60)
    print()

    success = test_default_voice(
        "Hello, this is a test of the default Chatterbox voice without any voice cloning applied."
    )

    print()
    if success:
        print("✅ Test passed! Playing audio...")
        import subprocess
        subprocess.run(["afplay", "test_default_voice.wav"])
    else:
        print("❌ Test failed")
        sys.exit(1)
