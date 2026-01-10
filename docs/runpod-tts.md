# RunPod Serverless TTS

AgentWire TTS can run on RunPod serverless infrastructure instead of a local GPU machine. This provides pay-per-use GPU access without maintaining dedicated hardware.

## Why RunPod Serverless?

| Benefit | Description |
|---------|-------------|
| **No GPU required** | Run TTS on cloud GPUs (RTX 3090, A100, etc.) |
| **Pay per use** | Only charged when generating audio (~$0.0004/sec on RTX 3090) |
| **Auto-scaling** | Scales to zero when idle, spins up on demand |
| **Custom voices** | Bundle voices in Docker image OR upload dynamically via network volumes |
| **Network volumes** | Persistent storage for voice clones without rebuilding Docker image |

## Prerequisites

- Docker Hub account for hosting the image
- RunPod account with API key
- Custom voice files in `~/.agentwire/voices/` (optional)

## Setup Steps

### 1. Build and Deploy Docker Image

```bash
# Set your Docker Hub username
export DOCKER_USERNAME=yourname

# Build and push image to Docker Hub
./scripts/deploy-runpod.sh
```

This creates a Docker image with:
- Chatterbox TurboTTS model
- Your custom voice clones from `~/.agentwire/voices/`
- CUDA 12.1 + cuDNN 8 for GPU acceleration

### 2. Create RunPod Endpoint

```bash
# Set RunPod API key
export RUNPOD_API_KEY=your_runpod_api_key_here

# Create serverless endpoint
./scripts/runpod-endpoint.py create
```

This creates a serverless endpoint and saves the endpoint ID to `~/.agentwire/runpod_endpoint.txt`.

### 3. Configure AgentWire

Edit `~/.agentwire/config.yaml`:

```yaml
tts:
  backend: runpod  # Change from "chatterbox" to "runpod"
  default_voice: bashbunni
  runpod_endpoint_id: your_endpoint_id  # From runpod-endpoint.py create
  runpod_api_key: your_runpod_api_key   # RunPod API key
  runpod_timeout: 60  # Request timeout in seconds
```

**Security note:** API keys in config files are less secure than environment variables. For production, use:

```bash
export AGENTWIRE_TTS__RUNPOD_API_KEY=your_key
# Config will be overridden by env var
```

### 4. Test Endpoint

```bash
# Test deployed endpoint
./scripts/test-runpod-remote.sh
```

This sends a TTS request and saves the audio to `test_output.wav`.

## RunPod Management Commands

```bash
# List all endpoints
./scripts/runpod-endpoint.py list

# Get endpoint details
./scripts/runpod-endpoint.py get <endpoint_id>

# Delete endpoint
./scripts/runpod-endpoint.py delete <endpoint_id>
```

## Cost Estimation

RunPod serverless pricing (as of 2024):

| GPU | Price per second | TTS generation (~5s) |
|-----|------------------|---------------------|
| RTX 3090 | $0.00039/sec | ~$0.002 |
| RTX 4090 | $0.00069/sec | ~$0.003 |
| A100 SXM | $0.00139/sec | ~$0.007 |

**Idle cost:** $0 (scales to zero when not in use)

## Workflow Comparison

| Aspect | Local GPU | RunPod Serverless |
|--------|-----------|-------------------|
| **Setup** | One-time GPU setup | Docker + endpoint creation |
| **Cost** | GPU hardware + electricity | Pay per use |
| **Latency** | ~1-2s | ~3-5s (includes cold start) |
| **Maintenance** | Manual updates | Automatic via Docker rebuild |
| **Scaling** | Fixed capacity | Auto-scales to demand |

## Voice Management

AgentWire supports two methods for managing voices on RunPod:

### Option 1: Network Volume (Recommended)

Upload voices dynamically without rebuilding the Docker image using RunPod's network volumes:

**Setup:**
1. Create a network volume in RunPod dashboard
2. Attach it to your serverless endpoint (auto-mounts at `/runpod-volume/`)
3. Upload voices via the API:

```python
import base64
import requests
from pathlib import Path

# Read voice file
voice_path = Path("~/.agentwire/voices/bashbunni.wav").expanduser()
audio_bytes = voice_path.read_bytes()
audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

# Upload to network volume
response = requests.post(
    f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
    json={
        "input": {
            "action": "upload_voice",
            "voice_name": "bashbunni",
            "audio_base64": audio_b64
        }
    },
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=300
)
```

**Voice lookup hierarchy:**
1. Bundled voices in `/voices/` (baked into Docker image)
2. Network voices in `/runpod-volume/` (persistent, uploadable)

See `upload_bashbunni.py` and `test_tiny_tina.py` for complete examples.

### Option 2: Bundled Voices (Docker Image)

Bundle voices into the Docker image (requires rebuild for updates):

1. Add voices to `~/.agentwire/voices/`
2. Rebuild and push Docker image:
   ```bash
   ./scripts/deploy-runpod.sh
   ```
3. Restart portal to reload config:
   ```bash
   agentwire portal stop
   agentwire portal start
   ```

**When to use bundled vs network volumes:**
- **Bundled**: Voices you'll always need (e.g., default voice)
- **Network volume**: Dynamic voices, testing, user-uploaded voices

## Troubleshooting

**"Voice not found" errors:**
- Voice clones must exist in `~/.agentwire/voices/` when building the Docker image
- Rebuild and redeploy after adding new voices

**Timeout errors:**
- Increase `runpod_timeout` in config (default: 60 seconds)
- Cold starts can take 10-20 seconds on first request

**Endpoint creation fails:**
- Verify RunPod API key is correct
- Check Docker image was pushed to Docker Hub
- Ensure image name matches: `$DOCKER_USERNAME/agentwire-tts:latest`

## Local Testing (Optional)

Test the Docker image locally before deploying:

```bash
# Requires local NVIDIA GPU with Docker
./scripts/test-runpod-local.sh
```

This builds the image and tests the handler without deploying to RunPod.
