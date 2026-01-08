#!/bin/bash
# Build multi-arch containers for AgentWire
# Supports linux/amd64 and linux/arm64

set -e

DOCKER_USERNAME="${DOCKER_USERNAME:-agentwire}"
VERSION="${VERSION:-latest}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building AgentWire containers${NC}"
echo "Docker username: $DOCKER_USERNAME"
echo "Version tag: $VERSION"
echo ""

# Check if buildx is available
if ! docker buildx version &> /dev/null; then
    echo -e "${YELLOW}Docker buildx not found. Installing...${NC}"
    docker buildx create --use
fi

# Create builder if it doesn't exist
if ! docker buildx inspect agentwire-builder &> /dev/null; then
    echo -e "${YELLOW}Creating buildx builder...${NC}"
    docker buildx create --name agentwire-builder --use
fi

docker buildx use agentwire-builder

# Build Portal (multi-arch: amd64, arm64)
echo -e "${GREEN}Building Portal container (linux/amd64, linux/arm64)...${NC}"
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -f Dockerfile.portal \
    -t ${DOCKER_USERNAME}/agentwire-portal:${VERSION} \
    --push \
    .

# Build STT CPU (multi-arch: amd64, arm64)
echo -e "${GREEN}Building STT CPU container (linux/amd64, linux/arm64)...${NC}"
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --build-arg ARCH=cpu \
    --build-arg WHISPER_MODEL=${WHISPER_MODEL:-base} \
    -f Dockerfile.stt \
    -t ${DOCKER_USERNAME}/agentwire-stt:${VERSION}-cpu \
    --push \
    .

# Build STT GPU (amd64 only - NVIDIA CUDA)
echo -e "${GREEN}Building STT GPU container (linux/amd64)...${NC}"
docker buildx build \
    --platform linux/amd64 \
    --build-arg ARCH=gpu \
    --build-arg WHISPER_MODEL=${WHISPER_MODEL:-base} \
    -f Dockerfile.stt \
    -t ${DOCKER_USERNAME}/agentwire-stt:${VERSION}-gpu \
    --push \
    .

echo -e "${GREEN}Build complete!${NC}"
echo ""
echo "Images pushed:"
echo "  ${DOCKER_USERNAME}/agentwire-portal:${VERSION}"
echo "  ${DOCKER_USERNAME}/agentwire-stt:${VERSION}-cpu"
echo "  ${DOCKER_USERNAME}/agentwire-stt:${VERSION}-gpu"
