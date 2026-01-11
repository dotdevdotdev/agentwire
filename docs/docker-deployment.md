# Docker Deployment

AgentWire can run fully containerized with Docker Compose. The containerized stack provides:
- **Portal** - Web UI, session orchestration, WebSocket server
- **STT** - Speech-to-text service (faster-whisper)
- **TTS** - RunPod serverless (external) or local Chatterbox container (optional)

## Quick Start

```bash
# Build and start the stack
docker-compose up --build

# Or run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Architecture

The containerized portal is **coordination-only** - it doesn't run tmux sessions internally. Instead, it manages sessions on remote machines via SSH, including the host machine.

```
┌─────────────────────────────────────────────────┐
│  Host Machine (Your Mac/Linux)                  │
│  ├── Browser → https://localhost:8765           │
│  ├── tmux sessions (managed via SSH)            │
│  └── ~/.agentwire/machines.json:                │
│      {                                           │
│        "id": "local",                            │
│        "host": "host.docker.internal"  ← magic! │
│      }                                           │
└─────────────────────────────────────────────────┘
          │
          ├─ Portal Container (port 8765) - COORDINATION ONLY
          │  ├── WebSocket server (voice UI)
          │  ├── HTTP API (session management)
          │  └── SSH client → manages sessions on ALL machines
          │                    (including host via "local")
          │
          ├─ STT Container (internal port 8100)
          │  ├── faster-whisper
          │  └── FastAPI server
          │
          └─ TTS (RunPod Serverless)
```

**Key Design:** The portal container treats the host as a remote machine using Docker's `host.docker.internal` hostname. This keeps the portal stateless and makes all session management consistent (everything via SSH).

**Session Listing:**
- From host: Groups by actual hostname (e.g., "Jordans-Mini:")
- From container: Groups by machine ID (e.g., "local:", "dotdev-pc:")

## Environment Variables

Configure via `.env` file or shell environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `STT_ARCH` | `cpu` | STT architecture: `cpu` or `gpu` |
| `WHISPER_MODEL` | `base` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3` |
| `WHISPER_DEVICE` | `cpu` | Whisper device: `cpu` or `cuda` |
| `WHISPER_LANGUAGE` | `en` | Language code or `auto` |
| `TTS_BACKEND` | `runpod` | TTS backend: `runpod` or `chatterbox` (if local TTS container enabled) |

## Volume Mounts

The Portal container mounts:
- `~/.agentwire` - Configuration, rooms.json, certificates
- `~/.ssh` (read-only) - SSH keys for remote machine access
- `~/projects` - Projects directory for worktrees

## Configuration Override

Docker Compose automatically configures the Portal to use the containerized STT service:

```yaml
environment:
  - AGENTWIRE_STT__BACKEND=remote
  - AGENTWIRE_STT__URL=http://stt:8100
  - AGENTWIRE_TTS__BACKEND=${TTS_BACKEND:-runpod}
```

**Note:** If using local Chatterbox TTS, uncomment the `tts` service in `docker-compose.yml`.

## Multi-Arch Builds

Build and push images for multiple architectures:

```bash
# Build locally
./scripts/build-local.sh

# Build and push to Docker Hub (multi-arch)
export DOCKER_USERNAME=yourname
./scripts/build-containers.sh
```

Builds create:
- **Portal** - `linux/amd64`, `linux/arm64`
- **STT CPU** - `linux/amd64`, `linux/arm64`
- **STT GPU** - `linux/amd64` only (NVIDIA CUDA)

See `scripts/README.md` for detailed build documentation.

## GPU Support (STT)

For GPU-accelerated STT, use the GPU variant:

```bash
# Build GPU variant
STT_ARCH=gpu ./scripts/build-local.sh

# Run with GPU support (requires NVIDIA Docker runtime)
docker-compose -f docker-compose.gpu.yml up
```

Requires:
- NVIDIA GPU
- NVIDIA Docker runtime installed
- `docker-compose.gpu.yml` configured with GPU resources

## Troubleshooting

| Issue | Solution |
|-------|----------|
| STT container unhealthy | Check logs: `docker logs agentwire-stt` |
| Portal can't reach STT | Verify network: `docker exec agentwire-portal curl http://stt:8100/health` |
| Port 8765 already in use | Change port in `docker-compose.yml` or stop conflicting service |
| Build fails with "gcc not found" | Fixed in Dockerfile.stt (includes build-essential) |
| Volume mount permission errors | Ensure `~/.agentwire` exists and is accessible |

**Health checks:**

```bash
# Portal health
curl -k https://localhost:8765/health

# STT health (from portal container)
docker exec agentwire-portal curl http://stt:8100/health
```

**Restart services:**

```bash
# Restart all services
docker-compose restart

# Rebuild specific service
docker-compose up -d --build portal

# View logs
docker-compose logs -f portal stt
```

## Future: Sandbox Sessions

**Concept:** Dedicated worker containers for volatile/untrusted projects.

```
Portal Container (coordinator)
  └─> spawns ephemeral worker containers
      ├── Isolated filesystem (no host access)
      ├── GPU support (optional)
      ├── Limited network access
      └── Auto-destroyed after session ends
```

**Use cases:**
- Running untrusted code from third parties
- Testing volatile/experimental projects
- CTF challenges and security research
- Temporary development environments
- Learning/educational contexts

**Benefits:**
- Complete isolation from host
- No risk to personal data or projects
- GPU acceleration for ML/AI workflows
- Fresh environment every time

This would be a future enhancement tracked as a mission in `docs/missions/`.
