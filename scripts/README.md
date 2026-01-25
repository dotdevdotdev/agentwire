# RunPod TTS Deployment Scripts

Scripts for deploying AgentWire TTS to RunPod serverless infrastructure.

## Prerequisites

- Docker installed and running
- Docker Hub account
- RunPod account with API key

## Scripts

| Script | Purpose |
|--------|---------|
| `deploy-runpod.sh` | Build and push TTS Docker image to Docker Hub |
| `runpod-endpoint.py` | Create/manage RunPod serverless endpoints |
| `test-runpod-remote.sh` | Test deployed RunPod endpoint |

## Deployment

### 1. Build and push Docker image

```bash
export DOCKER_USERNAME=yourname
./scripts/deploy-runpod.sh
```

This builds `Dockerfile.runpod` and pushes to Docker Hub as `${DOCKER_USERNAME}/agentwire-tts:latest`.

### 2. Create RunPod endpoint

```bash
export RUNPOD_API_KEY=your_runpod_api_key
./scripts/runpod-endpoint.py create
```

### 3. Test endpoint

```bash
./scripts/test-runpod-remote.sh
```

## Endpoint Management

```bash
# List endpoints
./scripts/runpod-endpoint.py list

# Get endpoint details
./scripts/runpod-endpoint.py get <endpoint_id>

# Delete endpoint
./scripts/runpod-endpoint.py delete <endpoint_id>
```

## Configuration

The endpoint is created with:
- 1 max worker (scales to zero when idle)
- 180s execution timeout
- 180s idle timeout before scale-down

Edit `runpod-endpoint.py` to change these defaults.
