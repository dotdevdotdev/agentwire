#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Test network volume voice management."""

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

    response = requests.post(url, json={"input": payload}, headers=headers, timeout=300)
    response.raise_for_status()

    result = response.json()

    if result.get("status") == "FAILED":
        print(f"Job failed: {result}")
        return None

    return result.get("output")

def list_voices():
    """List all available voices."""
    print("\n" + "=" * 60)
    print("Listing all voices")
    print("=" * 60)

    output = call_endpoint({"action": "list_voices"})

    if output:
        voices = output.get("voices", [])
        print(f"Available voices: {voices}")
        print(f"Total: {len(voices)}")
        return voices
    else:
        print("Failed to list voices")
        return []

def upload_voice(voice_name, wav_file_path):
    """Upload a voice to the network volume."""
    print("\n" + "=" * 60)
    print(f"Uploading voice: {voice_name}")
    print("=" * 60)

    # Read WAV file
    wav_path = Path(wav_file_path)
    if not wav_path.exists():
        print(f"Error: File not found: {wav_file_path}")
        return False

    audio_bytes = wav_path.read_bytes()
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

    print(f"File: {wav_file_path}")
    print(f"Size: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.1f} KB)")
    print()

    # Upload to endpoint
    output = call_endpoint({
        "action": "upload_voice",
        "voice_name": voice_name,
        "audio_base64": audio_b64
    })

    if output:
        if output.get("success"):
            print(f"✅ {output.get('message')}")
            print(f"   Voice: {output.get('voice_name')}")
            print(f"   Size: {output.get('size_bytes')} bytes")
            return True
        else:
            print(f"❌ Upload failed: {output.get('error')}")
            return False
    else:
        print("❌ Upload failed")
        return False

def test_voice(voice_name):
    """Generate TTS with a voice to test it."""
    print("\n" + "=" * 60)
    print(f"Testing voice: {voice_name}")
    print("=" * 60)

    output = call_endpoint({
        "action": "generate",
        "text": f"This is a test of the {voice_name} voice from the network volume.",
        "voice": voice_name
    })

    if output:
        if "error" in output:
            print(f"❌ Error: {output['error']}")
            return False
        else:
            audio_b64 = output.get("audio")
            audio_bytes = base64.b64decode(audio_b64)

            # Save to file
            test_file = Path(f"test_network_voice_{voice_name}.wav")
            test_file.write_bytes(audio_bytes)

            print(f"✅ TTS generated successfully")
            print(f"   Audio size: {len(audio_bytes)} bytes")
            print(f"   Saved to: {test_file}")

            # Play it
            import subprocess
            subprocess.run(["afplay", str(test_file)])

            return True
    else:
        print("❌ TTS generation failed")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Network Volume Voice Management Test")
    print("=" * 60)

    # Test 1: List voices (should show dotdev from bundled)
    print("\n📋 Test 1: List voices")
    voices = list_voices()

    # Test 2: Upload bashbunni voice (if it exists locally)
    bashbunni_path = Path.home() / ".agentwire/voices/bashbunni.wav"
    if bashbunni_path.exists():
        print("\n📤 Test 2: Upload bashbunni voice")
        upload_voice("bashbunni", bashbunni_path)

        # Test 3: List voices again (should now show bashbunni + dotdev)
        print("\n📋 Test 3: List voices (after upload)")
        voices = list_voices()

        # Test 4: Generate TTS with bashbunni
        if "bashbunni" in voices:
            print("\n🔊 Test 4: Test bashbunni voice")
            test_voice("bashbunni")
    else:
        print(f"\n⚠️  Skipping upload test (bashbunni.wav not found at {bashbunni_path})")

    # Test 5: Test dotdev voice (bundled)
    print("\n🔊 Test 5: Test dotdev voice (bundled)")
    test_voice("dotdev")

    print("\n" + "=" * 60)
    print("✅ Tests complete!")
    print("=" * 60)
