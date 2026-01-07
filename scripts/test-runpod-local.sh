#!/usr/bin/env bash
# Test RunPod TTS container locally
#
# Prerequisites:
# - Docker with NVIDIA GPU support
# - ~/.agentwire/voices/ directory with voice clones
#
# Usage:
#   ./scripts/test-runpod-local.sh

set -euo pipefail

echo "==> Building RunPod TTS Docker image..."

# Build with voices directory as build context
docker build \
  --build-context voices="$HOME/.agentwire/voices" \
  -f Dockerfile.runpod \
  -t agentwire-tts:local \
  .

echo "==> Image built successfully!"
echo "==> Image size:"
docker images agentwire-tts:local --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

echo ""
echo "==> Testing handler locally with RunPod Python API..."
echo "Note: This requires a GPU. Use 'docker run --gpus all' to enable GPU access."

# Test by importing the handler directly
docker run --rm --gpus all \
  -v "$(pwd)/test_runpod_input.json:/test_input.json" \
  agentwire-tts:local \
  python3 -c "
import json
import sys
sys.path.insert(0, '/app')
from agentwire.tts.runpod_handler import handler

# Load test input
with open('/test_input.json') as f:
    test_job = json.load(f)

# Simulate RunPod job format
job = {'input': test_job['input']}

# Run handler
result = handler(job)

# Check result
if 'error' in result:
    print(f'ERROR: {result[\"error\"]}')
    sys.exit(1)
else:
    print(f'SUCCESS!')
    print(f'  Voice: {result.get(\"voice\")}')
    print(f'  Sample Rate: {result.get(\"sample_rate\")}')
    print(f'  Audio Length: {len(result.get(\"audio\", \"\"))} bytes (base64)')
    sys.exit(0)
"

echo ""
echo "==> Local test complete!"
echo "To push to Docker Hub: ./scripts/deploy-runpod.sh"
