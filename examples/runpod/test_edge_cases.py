#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Comprehensive edge case testing for RunPod TTS endpoint."""

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

def test_endpoint(name, payload, expect_error=False, save_audio=None):
    """Test endpoint with given payload."""

    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"{'='*60}")
    print(f"Payload: {payload}")
    print()

    start_time = time.time()

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        elapsed = time.time() - start_time

        print(f"Status code: {response.status_code}")
        print(f"Response time: {elapsed:.2f}s")

        result = response.json()

        # Check if we expected an error
        if expect_error:
            if result.get("status") == "FAILED" or "error" in result.get("output", {}):
                error_msg = result.get("output", {}).get("error", result.get("error", "Unknown error"))
                print(f"✓ Got expected error: {error_msg}")
                return True
            else:
                print(f"✗ Expected error but got success")
                print(f"Response: {result}")
                return False

        # Check for success
        if result.get("status") == "FAILED":
            print(f"✗ Job failed: {result}")
            return False

        output = result.get("output")
        if not output:
            print(f"✗ No output in response")
            return False

        if "error" in output:
            print(f"✗ Error in output: {output['error']}")
            return False

        # Extract audio
        audio_b64 = output.get("audio")
        sample_rate = output.get("sample_rate")
        voice_used = output.get("voice")

        audio_bytes = base64.b64decode(audio_b64)

        print(f"✓ Success!")
        print(f"  Sample rate: {sample_rate}")
        print(f"  Voice: {voice_used}")
        print(f"  Audio size: {len(audio_bytes)} bytes")

        if save_audio:
            Path(save_audio).write_bytes(audio_bytes)
            print(f"  Saved to: {save_audio}")

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
    print("=" * 60)
    print("RunPod TTS Endpoint - Comprehensive Edge Case Tests")
    print("=" * 60)

    tests = []

    # Test 1: Empty text (should error)
    tests.append({
        "name": "Empty text",
        "payload": {"input": {"text": ""}},
        "expect_error": True,
        "save_audio": None
    })

    # Test 2: Whitespace only (should error)
    tests.append({
        "name": "Whitespace only",
        "payload": {"input": {"text": "   "}},
        "expect_error": True,
        "save_audio": None
    })

    # Test 3: Missing text field (should error)
    tests.append({
        "name": "Missing text field",
        "payload": {"input": {"voice": "dotdev"}},
        "expect_error": True,
        "save_audio": None
    })

    # Test 4: Invalid voice name (should error)
    tests.append({
        "name": "Invalid voice name",
        "payload": {"input": {"text": "Test", "voice": "nonexistent_voice"}},
        "expect_error": True,
        "save_audio": None
    })

    # Test 5: Very long text
    long_text = "This is a test sentence. " * 100  # ~2500 chars
    tests.append({
        "name": "Very long text (2500 chars)",
        "payload": {"input": {"text": long_text}},
        "expect_error": False,
        "save_audio": "test_long_text.wav"
    })

    # Test 6: Special characters and punctuation
    tests.append({
        "name": "Special characters",
        "payload": {"input": {"text": "Hello! How are you? I'm fine, thanks. What's up? $100 @ 50% off!"}},
        "expect_error": False,
        "save_audio": "test_special_chars.wav"
    })

    # Test 7: Numbers
    tests.append({
        "name": "Numbers",
        "payload": {"input": {"text": "The year is 2025. I have 42 apples and 3.14159 pies."}},
        "expect_error": False,
        "save_audio": "test_numbers.wav"
    })

    # Test 8: Unicode characters
    tests.append({
        "name": "Unicode characters",
        "payload": {"input": {"text": "Hello world in different languages: Héllo, Привет, 你好, مرحبا"}},
        "expect_error": False,
        "save_audio": "test_unicode.wav"
    })

    # Test 9: Emoji (might not speak well but shouldn't error)
    tests.append({
        "name": "Emoji",
        "payload": {"input": {"text": "Hello 😊 This is a test 🎉 with emoji 🚀"}},
        "expect_error": False,
        "save_audio": "test_emoji.wav"
    })

    # Test 10: bashbunni voice
    tests.append({
        "name": "bashbunni voice clone",
        "payload": {"input": {"text": "This is the bashbunni voice clone.", "voice": "bashbunni"}},
        "expect_error": False,
        "save_audio": "test_bashbunni.wav"
    })

    # Test 11: dotdev voice
    tests.append({
        "name": "dotdev voice clone",
        "payload": {"input": {"text": "This is the dotdev voice clone.", "voice": "dotdev"}},
        "expect_error": False,
        "save_audio": "test_dotdev.wav"
    })

    # Test 12: High exaggeration
    tests.append({
        "name": "High exaggeration (1.0)",
        "payload": {"input": {"text": "This is with high exaggeration!", "exaggeration": 1.0}},
        "expect_error": False,
        "save_audio": "test_exaggeration_high.wav"
    })

    # Test 13: Low exaggeration
    tests.append({
        "name": "Low exaggeration (0.0)",
        "payload": {"input": {"text": "This is with no exaggeration.", "exaggeration": 0.0}},
        "expect_error": False,
        "save_audio": "test_exaggeration_low.wav"
    })

    # Test 14: High cfg_weight
    tests.append({
        "name": "High cfg_weight (1.0)",
        "payload": {"input": {"text": "This is with high cfg weight.", "cfg_weight": 1.0}},
        "expect_error": False,
        "save_audio": "test_cfg_high.wav"
    })

    # Test 15: Low cfg_weight
    tests.append({
        "name": "Low cfg_weight (0.0)",
        "payload": {"input": {"text": "This is with no cfg weight.", "cfg_weight": 0.0}},
        "expect_error": False,
        "save_audio": "test_cfg_low.wav"
    })

    # Run all tests
    results = []
    for test in tests:
        result = test_endpoint(
            test["name"],
            test["payload"],
            test.get("expect_error", False),
            test.get("save_audio")
        )
        results.append({"name": test["name"], "passed": result})
        time.sleep(0.5)  # Small delay between tests

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print()

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    for r in results:
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        print(f"{status}: {r['name']}")

    print()
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)
