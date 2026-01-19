#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Upload tiny-tina voice and test it."""

import os
import sys
import base64
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")

if not RUNPOD_API_KEY or not ENDPOINT_ID:
    print("Error: RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID must be set in environment")
    sys.exit(1)

def call_endpoint(payload):
    """Call RunPod endpoint with payload."""
    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    print(f"Calling endpoint: {url}")
    response = requests.post(url, json={"input": payload}, headers=headers, timeout=300)
    response.raise_for_status()

    result = response.json()

    if result.get("status") == "FAILED":
        print(f"Job failed: {result}")
        return None

    return result.get("output")

print("=" * 60)
print("Upload and Test tiny-tina Voice")
print("=" * 60)

# Upload tiny-tina voice
tiny_tina_path = Path.home() / ".agentwire/voices_backup/tiny-tina.wav"
print(f"\n📤 Uploading tiny-tina voice from: {tiny_tina_path}")

audio_bytes = tiny_tina_path.read_bytes()
audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

print(f"File size: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.1f} KB)")

output = call_endpoint({
    "action": "upload_voice",
    "voice_name": "tiny-tina",
    "audio_base64": audio_b64
})

if output and output.get("success"):
    print(f"✅ {output.get('message')}")
    print(f"   Voice: {output.get('voice_name')}")
    print(f"   Size: {output.get('size_bytes')} bytes")

    # Test the voice
    print("\n🔊 Generating test audio with tiny-tina voice...")
    output = call_endpoint({
        "action": "generate",
        "text": "Hey there! This is tiny-tina speaking from the network volume. How cool is that?",
        "voice": "tiny-tina"
    })

    if output and "error" not in output:
        audio_b64 = output.get("audio")
        audio_bytes = base64.b64decode(audio_b64)

        # Save to file
        test_file = Path("test_tiny_tina.wav")
        test_file.write_bytes(audio_bytes)

        print(f"✅ TTS generated successfully")
        print(f"   Audio size: {len(audio_bytes)} bytes")
        print(f"   Saved to: {test_file}")

        # Play it
        import subprocess
        subprocess.run(["afplay", str(test_file)])
    else:
        print(f"❌ Error: {output.get('error') if output else 'Unknown error'}")
else:
    print(f"❌ Upload failed: {output.get('error') if output else 'Unknown error'}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
