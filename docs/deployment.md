# Deployment Guide

AgentWire is designed for flexible deployment across any combination of machines and operating systems.

## Deployment Topologies

### Single Machine (Simple)

Everything runs on one machine:

```
┌─────────────────────────────────────────┐
│  Your Machine                           │
│  ├── agentwire portal (web server)     │
│  ├── agentwire tts (Chatterbox)        │
│  ├── tmux sessions (Claude Code)       │
│  └── STT (WhisperKit/local)            │
└─────────────────────────────────────────┘
```

```bash
agentwire init
agentwire generate-certs
agentwire tts start
agentwire portal start
```

### Distributed (Multi-Machine)

Components spread across machines:

```
┌─────────────────────┐     ┌─────────────────────┐
│  Mac Mini           │     │  GPU Server         │
│  (orchestrator)     │     │  (TTS + workers)    │
│  ├── portal        │────►│  ├── Chatterbox    │
│  ├── dev session   │     │  └── worker sessions│
│  └── STT           │     │                     │
└─────────────────────┘     └─────────────────────┘
         │
         │ HTTPS
         ▼
    ┌─────────┐
    │ Phone/  │
    │ Tablet  │
    └─────────┘
```

### Docker (Containerized)

Run components in containers:

```
┌─────────────────────────────────────────┐
│  Docker Host                            │
│  ├── agentwire-portal (container)      │
│  ├── agentwire-tts (container)         │
│  └── volumes for config/certs          │
└─────────────────────────────────────────┘
         │
         │ SSH
         ▼
┌─────────────────────────────────────────┐
│  Dev Machine(s)                         │
│  └── tmux + Claude Code sessions       │
└─────────────────────────────────────────┘
```

## Configuration

### Full config.yaml Reference

```yaml
# ~/.agentwire/config.yaml

# === Portal Server ===
server:
  host: "0.0.0.0"           # Bind address
  port: 8765                 # HTTPS port
  ssl:
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"
  
  # For distributed: URL clients use to reach portal
  # (important when behind reverse proxy or on different network)
  public_url: "https://192.168.1.100:8765"

# === Projects ===
projects:
  dir: "~/projects"
  worktrees:
    enabled: true
    suffix: "-worktrees"
    auto_create_branch: true

# === Text-to-Speech ===
tts:
  # Backend: chatterbox | elevenlabs | none
  backend: "chatterbox"
  
  # Chatterbox server URL (can be remote!)
  url: "http://localhost:8100"
  # For remote TTS server:
  # url: "http://gpu-server:8100"
  
  default_voice: "default"
  exaggeration: 0.5
  cfg_weight: 0.5

# === Speech-to-Text ===
stt:
  # Backend: whisperkit | whispercpp | openai | none
  backend: "whisperkit"
  
  # For local backends
  model_path: "~/models/whisperkit/large-v3"
  language: "en"
  
  # For OpenAI backend (works anywhere)
  # backend: "openai"
  # api_key: "${OPENAI_API_KEY}"  # From environment

# === Agent Sessions ===
agent:
  # Command to start Claude Code in new sessions
  command: "claude --dangerously-skip-permissions"
  
  # Or with model specification:
  # command: "claude --model {model} --dangerously-skip-permissions"

# === Remote Machines ===
machines:
  file: "~/.agentwire/machines.json"

# === Room Settings ===
rooms:
  file: "~/.agentwire/rooms.json"

# === Docker/Container Settings ===
docker:
  # Network for inter-container communication
  network: "agentwire"
  
  # Volume mounts
  config_volume: "agentwire-config"
  certs_volume: "agentwire-certs"
```

### machines.json (Remote Machines)

```json
{
  "machines": [
    {
      "id": "gpu-server",
      "host": "192.168.1.50",
      "user": "developer",
      "projects_dir": "/home/developer/projects",
      "description": "GPU server for ML workloads"
    },
    {
      "id": "mac-mini",
      "host": "mac-mini.local",
      "user": "dotdev",
      "projects_dir": "/Users/dotdev/projects",
      "description": "Always-on Mac for background tasks"
    },
    {
      "id": "devbox",
      "host": "devbox",
      "user": "dev",
      "projects_dir": "/home/dev/projects",
      "ssh_key": "~/.ssh/devbox_key",
      "description": "Linux development VM"
    }
  ]
}
```

### rooms.json (Per-Session Settings)

```json
{
  "api": {
    "role": "worker",
    "voice": "default",
    "path": "~/projects/api"
  },
  "ml": {
    "role": "worker",
    "voice": "default",
    "machine": "gpu-server",
    "path": "/home/developer/projects/ml"
  },
  "assistant": {
    "role": "chatbot",
    "voice": "tiny-tina",
    "bypass_permissions": true,
    "model": "opus"
  }
}
```

## Environment Variables

All config values can be overridden via environment variables:

```bash
# Server
export AGENTWIRE_SERVER__PORT=9000
export AGENTWIRE_SERVER__HOST=0.0.0.0

# TTS
export AGENTWIRE_TTS__URL=http://gpu-server:8100
export AGENTWIRE_TTS__BACKEND=chatterbox

# STT
export AGENTWIRE_STT__BACKEND=openai
export OPENAI_API_KEY=sk-...

# Projects
export AGENTWIRE_PROJECTS__DIR=/data/projects
```

## Distributed Setup Examples

### Example 1: Mac + GPU Server

**Mac Mini** (orchestrator, portal, STT):

```yaml
# ~/.agentwire/config.yaml
server:
  port: 8765
  public_url: "https://mac-mini.local:8765"

tts:
  backend: "chatterbox"
  url: "http://gpu-server:8100"  # Remote TTS

stt:
  backend: "whisperkit"  # Local on Mac
  model_path: "~/models/whisperkit/large-v3"
```

```json
// ~/.agentwire/machines.json
{
  "machines": [
    {"id": "gpu-server", "host": "gpu-server", "user": "dev", "projects_dir": "/home/dev/projects"}
  ]
}
```

**GPU Server** (TTS + worker sessions):

```bash
# Start Chatterbox with GPU
docker run -d --gpus all -p 8100:8100 resemble/chatterbox serve

# Or natively
chatterbox serve --device cuda --port 8100
```

### Example 2: All Docker

```yaml
# docker-compose.yml on any Linux host
version: '3.8'

services:
  portal:
    image: agentwire/portal
    ports:
      - "8765:8765"
    volumes:
      - ./config:/root/.agentwire
      - ./certs:/root/.agentwire/certs
    environment:
      - AGENTWIRE_TTS__URL=http://tts:8100
      - AGENTWIRE_STT__BACKEND=openai
      - OPENAI_API_KEY=${OPENAI_API_KEY}

  tts:
    image: resemble/chatterbox
    command: serve --port 8100
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
```

### Example 3: Laptop + Cloud VM

**Laptop** (just browser access):
- Open `https://cloud-vm.example.com:8765`

**Cloud VM** (portal, TTS, sessions):

```yaml
# ~/.agentwire/config.yaml
server:
  host: "0.0.0.0"
  port: 8765
  public_url: "https://cloud-vm.example.com:8765"

tts:
  backend: "chatterbox"
  url: "http://localhost:8100"

stt:
  backend: "openai"  # Use API, no local model needed
```

## SSH Configuration

For remote sessions, configure passwordless SSH:

```bash
# Generate key if needed
ssh-keygen -t ed25519 -f ~/.ssh/agentwire

# Copy to remote machines
ssh-copy-id -i ~/.ssh/agentwire user@gpu-server
ssh-copy-id -i ~/.ssh/agentwire user@devbox

# Add to SSH config
cat >> ~/.ssh/config << EOF
Host gpu-server
  HostName 192.168.1.50
  User developer
  IdentityFile ~/.ssh/agentwire

Host devbox
  HostName devbox.local
  User dev
  IdentityFile ~/.ssh/agentwire
EOF
```

## Network Requirements

| Component | Port | Protocol | Notes |
|-----------|------|----------|-------|
| Portal | 8765 | HTTPS | SSL required for mic access |
| TTS | 8100 | HTTP | Can be internal only |
| SSH | 22 | TCP | For remote sessions |

### Firewall Rules

```bash
# On portal host
ufw allow 8765/tcp  # Portal

# On TTS host (if separate)
ufw allow from 192.168.1.0/24 to any port 8100  # TTS (internal only)
```

## Health Checks

```bash
# Check portal
curl -sk https://localhost:8765/health

# Check TTS
curl -s http://localhost:8100/voices

# Check remote machine
ssh gpu-server "tmux list-sessions"
```

## Troubleshooting

### Portal can't reach TTS

```bash
# Test connectivity
curl http://gpu-server:8100/voices

# Check TTS is running
ssh gpu-server "docker ps | grep chatterbox"
```

### Remote sessions not working

```bash
# Test SSH
ssh -o BatchMode=yes gpu-server "echo ok"

# Check tmux on remote
ssh gpu-server "which tmux"
```

### SSL certificate issues

```bash
# Regenerate certs
agentwire generate-certs

# For production, use Let's Encrypt
certbot certonly --standalone -d your-domain.com
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ~/.agentwire/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem ~/.agentwire/key.pem
```
