#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Test RunPod TTS response times with multiple requests.

Tests:
1. Cold start (first request after idle)
2. Warm worker (subsequent requests)
3. Different text lengths
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

def generate_tts(text, voice="dotdev", filename=None):
    """Generate TTS and return timing info."""

    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    payload = {
        "input": {
            "text": text,
            "voice": voice,
            "exaggeration": 0.0,
            "cfg_weight": 0.0
        }
    }

    print(f"Sending request: {text[:50]}...")
    start_time = time.time()

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()

        elapsed = time.time() - start_time
        result = response.json()

        if result.get("status") == "FAILED":
            print(f"  ✗ Failed: {result}")
            return None

        output = result.get("output")
        if not output or "error" in output:
            print(f"  ✗ Error: {output}")
            return None

        audio_b64 = output.get("audio")
        audio_bytes = base64.b64decode(audio_b64)

        if filename:
            Path(filename).write_bytes(audio_bytes)
            print(f"  ✓ Saved to {filename}")

        print(f"  ✓ Generated in {elapsed:.2f}s ({len(audio_bytes)} bytes)")

        return {
            "elapsed": elapsed,
            "audio_size": len(audio_bytes),
            "text_length": len(text)
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ✗ Exception after {elapsed:.2f}s: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("RunPod TTS Response Time Test")
    print("=" * 60)
    print()

    tests = [
        # Test 1: Cold start (short text)
        {
            "text": "Hello world",
            "desc": "Cold start (short)",
            "filename": "test_cold_short.wav"
        },

        # Test 2: Warm worker (short text)
        {
            "text": "This is a warm worker test",
            "desc": "Warm worker (short)",
            "filename": "test_warm_short.wav"
        },

        # Test 3: Medium length
        {
            "text": "The quick brown fox jumps over the lazy dog. This is a medium length sentence for testing TTS generation speed.",
            "desc": "Warm worker (medium)",
            "filename": "test_warm_medium.wav"
        },

        # Test 4: Long text
        {
            "text": "This is a longer test to see how the TTS system handles more complex sentences with multiple clauses and phrases. We want to measure the generation time for longer audio clips to understand the relationship between text length and processing time. The model should handle this gracefully and produce high quality speech output.",
            "desc": "Warm worker (long)",
            "filename": "test_warm_long.wav"
        },
    ]

    results = []

    for i, test in enumerate(tests, 1):
        print(f"{i}. {test['desc']}")
        result = generate_tts(test["text"], filename=test["filename"])

        if result:
            results.append({**result, "desc": test["desc"]})

        # Small delay between requests
        if i < len(tests):
            print()
            time.sleep(1)

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print()

    if results:
        print(f"{'Test':<25} {'Time':<10} {'Audio Size':<12} {'Text Len'}")
        print("-" * 60)
        for r in results:
            print(f"{r['desc']:<25} {r['elapsed']:>6.2f}s   {r['audio_size']:>8} B   {r['text_length']:>4}")

        if len(results) > 1:
            cold_start = results[0]["elapsed"]
            warm_avg = sum(r["elapsed"] for r in results[1:]) / len(results[1:])

            print()
            print(f"Cold start: {cold_start:.2f}s")
            print(f"Warm average: {warm_avg:.2f}s")
            print(f"Speedup: {cold_start / warm_avg:.1f}x faster when warm")

    print()
    print("✅ Test completed!")
