#!/bin/bash
# Build containers locally for testing (no push to registry)

set -e

WHISPER_MODEL="${WHISPER_MODEL:-base}"
STT_ARCH="${STT_ARCH:-cpu}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building AgentWire containers locally${NC}"
echo "STT Architecture: $STT_ARCH"
echo "Whisper Model: $WHISPER_MODEL"
echo ""

# Build Portal
echo -e "${GREEN}Building Portal container...${NC}"
docker build \
    -f Dockerfile.portal \
    -t agentwire-portal:local \
    .

# Build STT
echo -e "${GREEN}Building STT container ($STT_ARCH)...${NC}"
docker build \
    --build-arg ARCH=$STT_ARCH \
    --build-arg WHISPER_MODEL=$WHISPER_MODEL \
    -f Dockerfile.stt \
    -t agentwire-stt:local \
    .

echo -e "${GREEN}Build complete!${NC}"
echo ""
echo "Local images created:"
echo "  agentwire-portal:local"
echo "  agentwire-stt:local"
echo ""
echo "To run the stack:"
echo "  docker-compose up"
