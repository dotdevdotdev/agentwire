# AgentWire Build Scripts

Scripts for building and deploying AgentWire containers.

## Local Development

### Build locally for testing

```bash
# Build with defaults (CPU STT, base Whisper model)
./scripts/build-local.sh

# Build with GPU STT
STT_ARCH=gpu ./scripts/build-local.sh

# Build with larger Whisper model
WHISPER_MODEL=medium ./scripts/build-local.sh

# Run the stack
docker-compose up
```

### Test with docker-compose

```bash
# Start services in foreground
docker-compose up --build

# Start services in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment Variables

Configure via `.env` file or environment:

```bash
# STT Configuration
STT_ARCH=cpu              # cpu or gpu
WHISPER_MODEL=base        # tiny, base, small, medium, large-v2, large-v3
WHISPER_DEVICE=cpu        # cpu or cuda
WHISPER_LANGUAGE=en       # Language code or auto

# TTS Configuration
TTS_BACKEND=runpod        # runpod or chatterbox (if local TTS container enabled)
```

## Multi-Arch Builds (Production)

### Prerequisites

- Docker Hub account
- Docker buildx installed

### Build and push to registry

```bash
# Set Docker Hub username
export DOCKER_USERNAME=yourname

# Build and push all images
./scripts/build-containers.sh

# Build with specific version tag
VERSION=v1.0.0 ./scripts/build-containers.sh
```

This builds and pushes:
- `${DOCKER_USERNAME}/agentwire-portal:${VERSION}` (linux/amd64, linux/arm64)
- `${DOCKER_USERNAME}/agentwire-stt:${VERSION}-cpu` (linux/amd64, linux/arm64)
- `${DOCKER_USERNAME}/agentwire-stt:${VERSION}-gpu` (linux/amd64 only)

## RunPod Serverless

### Build and deploy TTS to RunPod

```bash
# Set Docker Hub username
export DOCKER_USERNAME=yourname

# Build and push RunPod TTS image
./scripts/deploy-runpod.sh

# Create RunPod endpoint
export RUNPOD_API_KEY=your_runpod_api_key
./scripts/runpod-endpoint.py create

# Test endpoint
./scripts/test-runpod-remote.sh
```

## Architecture

```
Portal Container (port 8765)
  ├── Session orchestration (tmux)
  ├── WebSocket server (voice UI)
  └── HTTP API

STT Container (port 8100)
  ├── faster-whisper
  ├── FastAPI server
  └── GPU or CPU variants

TTS (RunPod Serverless)
  ├── Chatterbox TurboTTS
  ├── Network volume for voices
  └── Auto-scaling GPU workers
```

## Testing Specific Components

### Test STT container

```bash
# Start STT container
docker-compose up stt

# In another terminal, test transcription
curl -X POST \
  -F "file=@test.wav" \
  http://localhost:8100/transcribe
```

### Test Portal container

```bash
# Start full stack
docker-compose up

# Access portal
open https://localhost:8765
```

## Troubleshooting

### Build fails with "buildx not found"

```bash
# Install buildx
docker buildx create --use
```

### GPU support not working

Ensure NVIDIA Docker runtime is installed:

```bash
# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Port already in use

```bash
# Find process using port
lsof -i :8765

# Kill process or change port in docker-compose.yml
```
