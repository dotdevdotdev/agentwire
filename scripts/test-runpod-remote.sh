#!/usr/bin/env bash
# Test deployed RunPod TTS endpoint
#
# Prerequisites:
# - RunPod endpoint created (via runpod-endpoint.py create)
# - RUNPOD_ENDPOINT_ID or ~/.agentwire/runpod_endpoint.txt
#
# Usage:
#   RUNPOD_ENDPOINT_ID=your_endpoint_id ./scripts/test-runpod-remote.sh
#   or use saved endpoint from runpod-endpoint.py

set -euo pipefail

# Get endpoint ID from env or saved file
ENDPOINT_ID="${RUNPOD_ENDPOINT_ID:-}"
ENDPOINT_FILE="$HOME/.agentwire/runpod_endpoint.txt"

if [[ -z "$ENDPOINT_ID" ]] && [[ -f "$ENDPOINT_FILE" ]]; then
  ENDPOINT_ID=$(cat "$ENDPOINT_FILE")
fi

if [[ -z "$ENDPOINT_ID" ]]; then
  echo "ERROR: RUNPOD_ENDPOINT_ID not set and no saved endpoint found"
  echo "Usage: RUNPOD_ENDPOINT_ID=your_endpoint_id ./scripts/test-runpod-remote.sh"
  echo "   or: ./scripts/runpod-endpoint.py create"
  exit 1
fi

RUNPOD_API_KEY="${RUNPOD_API_KEY:-}"
if [[ -z "$RUNPOD_API_KEY" ]]; then
  echo "ERROR: RUNPOD_API_KEY environment variable not set"
  exit 1
fi

echo "==> Testing RunPod endpoint: ${ENDPOINT_ID}"
echo ""

# Test with sample input
INPUT_JSON=$(cat test_runpod_input.json)

# Call RunPod endpoint
# RunPod API URL format: https://api.runpod.ai/v2/{endpoint_id}/runsync
ENDPOINT_URL="https://api.runpod.ai/v2/${ENDPOINT_ID}/runsync"

echo "==> Sending TTS request..."
RESPONSE=$(curl -s -X POST "$ENDPOINT_URL" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$INPUT_JSON")

# Parse response
echo "$RESPONSE" | python3 -c "
import sys
import json
import base64

response = json.load(sys.stdin)

# Check for errors
if response.get('status') == 'error':
    print('ERROR:', response.get('error', 'Unknown error'))
    sys.exit(1)

# Get output
output = response.get('output', {})

if 'error' in output:
    print('HANDLER ERROR:', output['error'])
    sys.exit(1)

# Decode audio
audio_b64 = output.get('audio', '')
if not audio_b64:
    print('ERROR: No audio in response')
    sys.exit(1)

audio_bytes = base64.b64decode(audio_b64)

print('==> SUCCESS!')
print(f'  Voice: {output.get(\"voice\")}')
print(f'  Sample Rate: {output.get(\"sample_rate\")}')
print(f'  Audio Size: {len(audio_bytes)} bytes')
print(f'  Duration: ~{len(audio_bytes) / output.get(\"sample_rate\", 24000) / 2:.2f}s')

# Save to file
with open('test_output.wav', 'wb') as f:
    f.write(audio_bytes)

print()
print('==> Audio saved to: test_output.wav')
print('    Play with: aplay test_output.wav (Linux) or afplay test_output.wav (macOS)')
"

echo ""
echo "==> Test complete!"
