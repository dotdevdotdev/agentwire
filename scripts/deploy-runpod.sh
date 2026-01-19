#!/usr/bin/env bash
# Deploy AgentWire TTS to Docker Hub for RunPod
#
# Prerequisites:
# - Docker Hub account
# - docker login completed
# - ~/.agentwire/voices/ directory with voice clones
#
# Usage:
#   DOCKER_USERNAME=yourname ./scripts/deploy-runpod.sh
#   or set DOCKER_USERNAME in environment

set -euo pipefail

# Configuration
DOCKER_USERNAME="${DOCKER_USERNAME:-}"
IMAGE_NAME="agentwire-tts"
VERSION="${VERSION:-latest}"

if [[ -z "$DOCKER_USERNAME" ]]; then
  echo "ERROR: DOCKER_USERNAME not set"
  echo "Usage: DOCKER_USERNAME=yourname ./scripts/deploy-runpod.sh"
  exit 1
fi

FULL_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "==> Deploying AgentWire TTS to Docker Hub"
echo "    Image: ${FULL_IMAGE}"
echo ""

# Check Docker login
if ! docker info > /dev/null 2>&1; then
  echo "ERROR: Docker daemon not running"
  exit 1
fi

# Verify voices directory exists
VOICES_DIR="$HOME/.agentwire/voices"
if [[ ! -d "$VOICES_DIR" ]]; then
  echo "WARNING: Voices directory not found: ${VOICES_DIR}"
  echo "Creating empty directory..."
  mkdir -p "$VOICES_DIR"
fi

echo "==> Building Docker image..."
docker build \
  --build-context voices="$VOICES_DIR" \
  -f Dockerfile.runpod \
  -t "$FULL_IMAGE" \
  .

echo ""
echo "==> Image built successfully!"
echo "==> Image size:"
docker images "$FULL_IMAGE" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

echo ""
echo "==> Pushing to Docker Hub..."
docker push "$FULL_IMAGE"

echo ""
echo "==> Deployment complete!"
echo "    Image: ${FULL_IMAGE}"
echo ""
echo "Next steps:"
echo "  1. Create RunPod endpoint: ./scripts/runpod-endpoint.py create"
echo "  2. Test endpoint: ./scripts/test-runpod-remote.sh"
