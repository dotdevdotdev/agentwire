# Mission: RunPod Serverless TTS Deployment

> Living document. Update this, don't create new versions.

**Status:** Active
**Branch:** `mission/runpod-serverless-tts`
**Created:** 2026-01-07

## Goal

Replace the dotdev-pc TTS service with a RunPod serverless function that provides similar latency (<2s response time) at dramatically lower cost (~$0.30-0.99/month vs dedicated machine costs).

**Context:** RunPod provides serverless GPU infrastructure with:
- Sub-200ms cold starts via FlashBoot
- Pay-per-second billing (scales to zero)
- RTX 4090 GPUs at $0.34/hr
- CLI and Python SDK for management

## Current State

**TTS Architecture:**
- Chatterbox TTS running on dotdev-pc (dedicated GPU machine)
- SSH tunnel forwards `localhost:8100` → `dotdev-pc:8100`
- AgentWire portal calls TTS via tunnel
- Portal serves TTS audio to browser clients

**Issues:**
- Dedicated machine costs (24/7 regardless of usage)
- Single point of failure (dotdev-pc down = no TTS)
- Maintenance overhead (OS updates, monitoring)

## Desired State

**RunPod Serverless Architecture:**
- Docker container with Chatterbox TTS
- Published to Docker Hub
- RunPod serverless endpoint configured
- AgentWire portal calls RunPod endpoint directly
- FlashBoot enabled for fast cold starts
- Model caching via persistent volume
- Zero cost when idle

## Prerequisites

**Local machine:**
- ✅ Docker Desktop installed and running
- ✅ RunPod account created
- ✅ RunPod API key generated
- ✅ runpodctl CLI installed
- ✅ RunPod Python SDK installed

**Reference docs:**
- `~/projects/gpu-research/RUNPOD_TTS_GUIDE.md`
- `~/projects/gpu-research/SETUP_COMPLETE.md`
- `~/projects/agentwire/Dockerfile.tts.gpu` (existing)

---

## Wave 1: Environment Setup (Human)

**No agent work - human completes these steps before Wave 2**

### Tasks

- [ ] **1.1: Verify Docker Desktop is running**
  ```bash
  docker ps  # Should not error
  ```

- [ ] **1.2: Add RunPod API key to environment**
  ```bash
  # Add to ~/.zshrc
  export RUNPOD_API_KEY="rpa_YOUR_API_KEY_HERE"
  export RUNPOD_ENDPOINT_ID=""  # Will be set after endpoint creation
  source ~/.zshrc
  ```

- [ ] **1.3: Configure runpodctl**
  ```bash
  runpodctl config --apiKey $RUNPOD_API_KEY
  runpodctl get gpu  # Verify connection
  ```

- [ ] **1.4: Login to Docker Hub**
  ```bash
  docker login
  # Username: dotdevdotdev
  ```

---

## Wave 2: Docker Container Development

**Agent tasks - can run in parallel**

### 2.1: Create RunPod Handler

**File:** `agentwire/tts/runpod_handler.py`

**Requirements:**
- Implements RunPod serverless handler function
- Uses AgentWire's existing Chatterbox TTS integration
- Accepts input format:
  ```json
  {
    "input": {
      "text": "Hello world",
      "voice": "bashbunni",  // optional
      "speed": 1.0            // optional
    }
  }
  ```
- Returns base64-encoded audio or CloudFlare R2 URL
- Handles errors gracefully
- Logs performance metrics

**Reference:** `~/projects/gpu-research/RUNPOD_TTS_GUIDE.md` Phase 3.2

### 2.2: Create RunPod Dockerfile

**File:** `Dockerfile.runpod`

**Requirements:**
- Based on `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`
- Installs Python 3.10+
- Installs AgentWire TTS dependencies:
  - `runpod>=1.6.2`
  - Chatterbox TTS with CUDA support
  - Required audio libraries
- Copies handler code
- Sets environment variables:
  - `MODEL_PATH=/runpod-volume/tts-models`
  - `TORCH_HOME=/runpod-volume/torch`
- CMD runs handler: `python3 -u runpod_handler.py`
- Target image size: <5 GB (for fast cold starts)

**Reference:**
- Existing: `Dockerfile.tts.gpu`
- Guide: `~/projects/gpu-research/RUNPOD_TTS_GUIDE.md` Phase 3.3

### 2.3: Create requirements-runpod.txt

**File:** `requirements-runpod.txt`

**Requirements:**
- Lists all TTS dependencies for RunPod environment
- Includes:
  - `runpod>=1.6.2`
  - Chatterbox TTS
  - Audio processing libraries
  - PyTorch with CUDA support

**Reference:** `~/projects/gpu-research/RUNPOD_TTS_GUIDE.md` Phase 3.4

### 2.4: Create test input file

**File:** `test_runpod_input.json`

**Content:**
```json
{
  "input": {
    "text": "Testing AgentWire TTS on RunPod serverless infrastructure.",
    "voice": "bashbunni",
    "speed": 1.0
  }
}
```

### 2.5: Create local test script

**File:** `scripts/test-runpod-local.sh`

**Purpose:** Test Docker container locally before deploying

**Requirements:**
```bash
#!/bin/bash
set -e

echo "Building RunPod TTS container..."
docker build --platform linux/amd64 -f Dockerfile.runpod -t tts-runpod:test .

echo "Testing handler with sample input..."
docker run --rm \
  -v $(pwd)/test_runpod_input.json:/test_input.json \
  tts-runpod:test \
  python3 -c "import json; from runpod_handler import handler; print(handler(json.load(open('/test_input.json'))))"

echo "✅ Local test complete"
```

---

## Wave 3: Deployment Scripts

**Agent tasks - depend on Wave 2 completion**

### 3.1: Create deployment script

**File:** `scripts/deploy-runpod.sh`

**Purpose:** Build and push Docker image to Docker Hub

**Requirements:**
```bash
#!/bin/bash
set -e

IMAGE_NAME="dotdevdotdev/agentwire-tts"
VERSION="${1:-latest}"

echo "Building AgentWire TTS for RunPod (${VERSION})..."

# Build for linux/amd64 (RunPod platform)
docker buildx build --platform linux/amd64 \
  -f Dockerfile.runpod \
  -t ${IMAGE_NAME}:${VERSION} \
  -t ${IMAGE_NAME}:latest \
  --push .

echo "✅ Deployed ${IMAGE_NAME}:${VERSION}"
echo "📦 Image: ${IMAGE_NAME}:latest"
echo "⚠️  RunPod endpoint will pull new image on next cold start"
```

### 3.2: Create endpoint management script

**File:** `scripts/runpod-endpoint.py`

**Purpose:** Create/update RunPod serverless endpoint via Python SDK

**Requirements:**
```python
#!/usr/bin/env python3
"""
Manage RunPod serverless endpoint for AgentWire TTS.

Usage:
  python scripts/runpod-endpoint.py create
  python scripts/runpod-endpoint.py status
  python scripts/runpod-endpoint.py update
"""

import runpod
import os
import sys

runpod.api_key = os.environ["RUNPOD_API_KEY"]
IMAGE_NAME = "dotdevdotdev/agentwire-tts:latest"

def create_endpoint():
    """Create new serverless endpoint"""
    endpoint = runpod.Endpoint.create(
        name="agentwire-tts-production",
        template_id=IMAGE_NAME,
        gpu_ids=["AMPERE_24"],  # RTX 4090
        workers_min=0,  # Scale to zero
        workers_max=3,
        idle_timeout=5,
        flashboot=True,  # Enable fast cold starts
        env={
            "MODEL_PATH": "/runpod-volume/tts-models",
            "TORCH_HOME": "/runpod-volume/torch"
        }
    )

    print(f"✅ Endpoint created: {endpoint.id}")
    print(f"🔑 Add to ~/.zshrc: export RUNPOD_ENDPOINT_ID=\"{endpoint.id}\"")
    return endpoint

def get_status():
    """Get endpoint status"""
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")
    if not endpoint_id:
        print("❌ RUNPOD_ENDPOINT_ID not set")
        sys.exit(1)

    endpoint = runpod.Endpoint(endpoint_id)
    health = endpoint.health()
    print(f"Workers: {health['workers']}")
    print(f"Jobs: {health['jobs']}")

def update_endpoint():
    """Update endpoint configuration"""
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")
    if not endpoint_id:
        print("❌ RUNPOD_ENDPOINT_ID not set")
        sys.exit(1)

    endpoint = runpod.Endpoint(endpoint_id)
    endpoint.update(flashboot=True, idle_timeout=5)
    print("✅ Endpoint updated")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "create":
        create_endpoint()
    elif cmd == "status":
        get_status()
    elif cmd == "update":
        update_endpoint()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
```

### 3.3: Create test client script

**File:** `scripts/test-runpod-remote.sh`

**Purpose:** Test deployed RunPod endpoint

**Requirements:**
```bash
#!/bin/bash
set -e

TEXT="${1:-Testing AgentWire TTS on RunPod serverless.}"
VOICE="${2:-bashbunni}"

if [ -z "$RUNPOD_ENDPOINT_ID" ]; then
  echo "❌ RUNPOD_ENDPOINT_ID not set"
  exit 1
fi

echo "🔊 Testing TTS: \"$TEXT\""
echo "🎤 Voice: $VOICE"

python3 << EOF
import runpod
import os
import time

runpod.api_key = os.environ["RUNPOD_API_KEY"]
endpoint = runpod.Endpoint(os.environ["RUNPOD_ENDPOINT_ID"])

start = time.time()
result = endpoint.run_sync(
    {"input": {"text": "$TEXT", "voice": "$VOICE"}},
    timeout=60
)
elapsed = time.time() - start

print(f"\n✅ Response in {elapsed:.2f}s")
print(f"📊 Result: {result}")
EOF
```

---

## Wave 4: AgentWire Integration

**Agent tasks - depend on Wave 3, endpoint creation**

### 4.1: Add RunPod TTS backend

**File:** `agentwire/tts/runpod_backend.py`

**Purpose:** TTS backend that calls RunPod serverless endpoint

**Requirements:**
```python
"""RunPod serverless TTS backend for AgentWire."""

import runpod
import os
import base64
from pathlib import Path
from typing import Optional

class RunPodTTSBackend:
    """TTS backend using RunPod serverless GPU."""

    def __init__(self, api_key: str, endpoint_id: str):
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        runpod.api_key = api_key
        self.endpoint = runpod.Endpoint(endpoint_id)

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0
    ) -> bytes:
        """
        Generate TTS audio via RunPod.

        Args:
            text: Text to synthesize
            voice: Voice ID (optional)
            speed: Speech speed multiplier

        Returns:
            Audio bytes (WAV format)

        Raises:
            TimeoutError: If request exceeds 60s
            Exception: For other errors
        """
        result = self.endpoint.run_sync(
            {
                "input": {
                    "text": text,
                    "voice": voice,
                    "speed": speed
                }
            },
            timeout=60
        )

        if "error" in result:
            raise Exception(f"RunPod TTS error: {result['error']}")

        # Decode base64 audio
        audio_b64 = result.get("audio")
        if not audio_b64:
            raise Exception("No audio in response")

        return base64.b64decode(audio_b64)

    def health_check(self) -> dict:
        """Check endpoint health."""
        return self.endpoint.health()
```

### 4.2: Update config.yaml schema

**File:** `agentwire/config.py`

**Changes:**
- Add `runpod` to TTS backend options
- Add RunPod-specific config fields:
  ```python
  @dataclass
  class TTSConfig:
      backend: Literal["chatterbox", "runpod", "none"]
      url: str  # For chatterbox
      default_voice: str
      voices_dir: Path

      # RunPod specific
      runpod_api_key: Optional[str] = None
      runpod_endpoint_id: Optional[str] = None
  ```

### 4.3: Update TTS router

**File:** `agentwire/tts_router.py`

**Changes:**
- Import `RunPodTTSBackend`
- Initialize RunPod backend when `config.tts.backend == "runpod"`
- Route to RunPod instead of Chatterbox when configured

**Example routing logic:**
```python
if self.config.tts.backend == "runpod":
    # Use RunPod serverless
    audio = self.runpod_backend.synthesize(text, voice)
    # Play locally or send to portal
elif self.config.tts.backend == "chatterbox":
    # Existing Chatterbox logic
    pass
```

### 4.4: Update CLAUDE.md documentation

**File:** `CLAUDE.md`

**Changes:**
- Add RunPod TTS setup section
- Document config.yaml RunPod settings
- Update TTS architecture diagram
- Add latency expectations (sub-2s with FlashBoot)
- Document cost estimates

---

## Wave 5: Testing & Optimization

**Agent tasks - verification and optimization**

### 5.1: Create latency benchmark script

**File:** `scripts/benchmark-tts-latency.sh`

**Purpose:** Compare dotdev-pc vs RunPod latency

**Requirements:**
```bash
#!/bin/bash
set -e

ITERATIONS="${1:-10}"
TEXT="Testing TTS latency with AgentWire."

echo "🔬 Benchmarking TTS latency (${ITERATIONS} iterations)"
echo ""

# Test dotdev-pc (if available)
echo "📊 dotdev-pc (current):"
for i in $(seq 1 $ITERATIONS); do
  start=$(date +%s%3N)
  curl -s -X POST http://localhost:8100/tts \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$TEXT\",\"voice\":\"bashbunni\"}" \
    > /dev/null
  end=$(date +%s%3N)
  echo "  Request $i: $((end - start))ms"
done

echo ""
echo "📊 RunPod serverless:"
for i in $(seq 1 $ITERATIONS); do
  start=$(date +%s%3N)
  python3 << EOF
import runpod, os
runpod.api_key = os.environ["RUNPOD_API_KEY"]
endpoint = runpod.Endpoint(os.environ["RUNPOD_ENDPOINT_ID"])
endpoint.run_sync({"input": {"text": "$TEXT", "voice": "bashbunni"}}, timeout=60)
EOF
  end=$(date +%s%3N)
  echo "  Request $i: $((end - start))ms"
done
```

### 5.2: Document latency results

**File:** `docs/runpod-latency-results.md`

**Purpose:** Record benchmarking results

**Format:**
```markdown
# RunPod TTS Latency Benchmark

**Date:** 2026-01-07
**Iterations:** 10 per backend

## Results

| Backend | Cold Start | Warm Request | Average | P95 |
|---------|-----------|--------------|---------|-----|
| dotdev-pc | N/A | 500ms | 520ms | 580ms |
| RunPod (no FlashBoot) | 2500ms | 600ms | 850ms | 2400ms |
| RunPod (with FlashBoot) | 800ms | 550ms | 620ms | 750ms |

## Conclusion

[Analysis of results - is RunPod viable?]
```

### 5.3: Enable FlashBoot (if not already)

**Action:** Via web UI or API
- Endpoint Settings → Advanced → FlashBoot: ✅

### 5.4: Set up model caching volume

**Actions:**
1. Create network volume via RunPod Console:
   - Name: `agentwire-tts-models`
   - Size: 20 GB
   - Region: Same as endpoint
2. Attach to endpoint at `/runpod-volume`
3. Pre-download models to volume (one-time setup)

**Reference:** `~/projects/gpu-research/RUNPOD_TTS_GUIDE.md` Phase 6.2

---

## Wave 6: Production Cutover

**Human tasks - switching production traffic**

- [ ] **6.1: Verify RunPod endpoint is healthy**
  ```bash
  python scripts/runpod-endpoint.py status
  ```

- [ ] **6.2: Update config.yaml to use RunPod**
  ```yaml
  tts:
    backend: "runpod"
    runpod_api_key: "${RUNPOD_API_KEY}"  # From env
    runpod_endpoint_id: "${RUNPOD_ENDPOINT_ID}"
    default_voice: "bashbunni"
  ```

- [ ] **6.3: Restart AgentWire portal**
  ```bash
  agentwire portal stop
  agentwire portal start
  ```

- [ ] **6.4: Test end-to-end TTS**
  ```bash
  # From AgentWire session
  remote-say "Testing RunPod serverless TTS integration."
  ```

- [ ] **6.5: Monitor for 24 hours**
  - Check latency
  - Check error rates
  - Monitor RunPod costs

- [ ] **6.6: Decommission dotdev-pc TTS (optional)**
  - Stop TTS service: `ssh dotdev-pc "agentwire tts stop"`
  - Remove SSH tunnel: `agentwire tunnels down`
  - Update machines.json if fully decommissioning

---

## Completion Criteria

- [ ] Docker container built and tested locally
- [ ] Image published to Docker Hub: `dotdevdotdev/agentwire-tts:latest`
- [ ] RunPod serverless endpoint created and configured
- [ ] FlashBoot enabled
- [ ] Model caching volume set up
- [ ] AgentWire integrated with RunPod backend
- [ ] Latency benchmarked (<2s average with FlashBoot)
- [ ] Production traffic cut over to RunPod
- [ ] Documentation updated
- [ ] Cost monitoring configured

---

## Cost Analysis

### Before (dotdev-pc)
- **GPU machine**: ~$50-100/month (24/7 operation)
- **Electricity**: ~$10-20/month
- **Total**: **~$60-120/month**

### After (RunPod Serverless)
- **Usage**: 30 requests/day @ 5s each
- **Compute**: ~2.91 hours/month
- **With FlashBoot**: **~$0.30/month**
- **Storage**: ~$0.10/month (model cache)
- **Total**: **~$0.40/month**

**Savings**: ~$60-120/month → **98-99% cost reduction**

---

## Rollback Plan

If RunPod latency is unacceptable:

1. Revert config.yaml to `backend: "chatterbox"`
2. Restart portal: `agentwire portal restart`
3. Ensure dotdev-pc TTS is running
4. Ensure tunnel is up: `agentwire tunnels up`
5. Keep RunPod endpoint for future optimization

---

## Related Issues

- Closes: (none - proactive optimization)
- Related: TTS architecture cleanup (#18)
- Depends: Docker Desktop installed, RunPod account created

---

## Testing Checklist

### Local Testing
- [ ] Docker builds successfully
- [ ] Local test with `test-runpod-local.sh` passes
- [ ] Image size < 5 GB

### RunPod Testing
- [ ] Endpoint creation succeeds
- [ ] Health check returns success
- [ ] Test request completes in <5s
- [ ] Error handling works (invalid input, timeout)

### Integration Testing
- [ ] AgentWire portal can call RunPod backend
- [ ] Browser TTS playback works
- [ ] Local speaker playback works
- [ ] Voice selection works
- [ ] Error messages surface to user

### Performance Testing
- [ ] Cold start < 2s (with FlashBoot)
- [ ] Warm request < 1s
- [ ] Concurrent requests work (up to 3 workers)
- [ ] Model caching eliminates re-downloads

---

## Notes

**Docker on dotdev-pc:** User mentioned Docker Desktop might be needed on dotdev-pc as well. This is NOT required for RunPod deployment - RunPod runs containers in their cloud. Docker is only needed on the local development machine for building and testing containers.

**Migration strategy:** This mission doesn't remove dotdev-pc immediately. It sets up RunPod as an alternative, measures latency, and only cuts over if performance is acceptable. The rollback plan allows reverting quickly if needed.

**FlashBoot importance:** FlashBoot is critical for achieving <2s response times. Without it, cold starts can take 2-3 seconds, making the experience feel sluggish. With FlashBoot, cold starts drop to <1s, making serverless viable for interactive TTS.
