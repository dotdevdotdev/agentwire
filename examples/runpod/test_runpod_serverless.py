#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Test RunPod Traditional Serverless TTS endpoint.

This tests the queue-based serverless architecture (not Load Balancer).
"""

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

def test_tts_generation():
    """Test TTS generation with traditional serverless (synchronous)."""

    # Use runsync endpoint for synchronous execution
    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    # Job input for our handler
    payload = {
        "input": {
            "text": "Hello from RunPod traditional serverless! This is a test of the queue-based architecture.",
            "voice": "dotdev",
            "exaggeration": 0.0,
            "cfg_weight": 0.0
        }
    }

    print("Submitting synchronous job to RunPod...")
    print(f"Endpoint: {ENDPOINT_ID}")
    print(f"Text: {payload['input']['text']}")
    print(f"Voice: {payload['input']['voice']}")
    print()
    print("Waiting for response (may take 1-2 minutes on cold start)...")

    start_time = time.time()

    # Submit synchronous job (blocks until complete)
    response = requests.post(url, json=payload, headers=headers, timeout=300)
    response.raise_for_status()

    elapsed = time.time() - start_time

    result = response.json()
    print(f"\nResponse received after {elapsed:.1f}s")

    # Check for errors
    if result.get("status") == "FAILED":
        print("\nJob failed!")
        print(result)
        sys.exit(1)

    # Extract output
    output = result.get("output")
    if not output:
        print("Error: No output in response")
        print(result)
        sys.exit(1)

    if "error" in output:
        print(f"Error from handler: {output['error']}")
        sys.exit(1)

    # Get audio data
    audio_b64 = output.get("audio")
    sample_rate = output.get("sample_rate")
    voice_used = output.get("voice")

    print(f"Sample rate: {sample_rate}")
    print(f"Voice: {voice_used}")
    print(f"Audio size (base64): {len(audio_b64)} bytes")

    # Decode and save
    audio_bytes = base64.b64decode(audio_b64)
    output_path = Path("test_output_serverless.wav")
    output_path.write_bytes(audio_bytes)

    print(f"\nAudio saved to: {output_path}")
    print(f"Audio size (WAV): {len(audio_bytes)} bytes")
    print(f"\nTotal time: {elapsed:.1f}s")

if __name__ == "__main__":
    print("=" * 60)
    print("RunPod Traditional Serverless TTS Test")
    print("=" * 60)
    print()

    test_tts_generation()

    print("\n✅ Test completed successfully!")
