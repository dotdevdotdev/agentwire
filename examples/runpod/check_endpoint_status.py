#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Check RunPod endpoint worker status."""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")

if not RUNPOD_API_KEY or not ENDPOINT_ID:
    print("Error: RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID must be set in environment")
    sys.exit(1)

# Check endpoint health
url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/health"
headers = {
    "Authorization": f"Bearer {RUNPOD_API_KEY}"
}

print("=" * 60)
print("RunPod Endpoint Status")
print("=" * 60)
print()
print(f"Endpoint ID: {ENDPOINT_ID}")
print()

try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()
    print("Health check response:")

    import json
    print(json.dumps(data, indent=2))

    # Try to extract worker info
    if "workers" in data:
        workers = data["workers"]
        print()
        print(f"Total workers: {workers.get('total', 0)}")
        print(f"Idle workers: {workers.get('idle', 0)}")
        print(f"Running workers: {workers.get('running', 0)}")

        if workers.get('total', 0) == 0:
            print()
            print("Status: ✅ Scaled to zero (no workers)")
        elif workers.get('running', 0) > 0:
            print()
            print("Status: 🟢 Active (workers running)")
        else:
            print()
            print("Status: 🟡 Idle (workers ready but not processing)")

except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
    print(f"Response: {e.response.text if e.response else 'No response'}")
except Exception as e:
    print(f"Error: {e}")
