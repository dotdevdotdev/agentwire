#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Upload bashbunni voice to network volume."""

import os
import sys
import base64
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID", "dw0aqos9tvt95h")

if not RUNPOD_API_KEY:
    print("Error: RUNPOD_API_KEY not found")
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
print("Upload bashbunni Voice")
print("=" * 60)

# Upload bashbunni voice
bashbunni_path = Path.home() / ".agentwire/voices_backup/bashbunni.wav"
print(f"\n📤 Uploading bashbunni voice from: {bashbunni_path}")

audio_bytes = bashbunni_path.read_bytes()
audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

print(f"File size: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.1f} KB)")

output = call_endpoint({
    "action": "upload_voice",
    "voice_name": "bashbunni",
    "audio_base64": audio_b64
})

if output and output.get("success"):
    print(f"✅ {output.get('message')}")
    print(f"   Voice: {output.get('voice_name')}")
    print(f"   Size: {output.get('size_bytes')} bytes")

    # Test the voice
    print("\n🔊 Generating test audio with bashbunni voice...")
    output = call_endpoint({
        "action": "generate",
        "text": "What's up everyone! This is bashbunni coming to you from the network volume. Pretty awesome, right?",
        "voice": "bashbunni"
    })

    if output and "error" not in output:
        audio_b64 = output.get("audio")
        audio_bytes = base64.b64decode(audio_b64)

        # Save to file
        test_file = Path("test_bashbunni.wav")
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
