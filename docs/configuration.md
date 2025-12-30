# Configuration Guide

AgentWire uses a YAML configuration file located at `~/.agentwire/config.yaml`.

## Full Configuration Reference

```yaml
# Server settings
server:
  host: "0.0.0.0"              # Bind address (0.0.0.0 for all interfaces)
  port: 8765                    # HTTPS port
  ssl:
    cert: "~/.agentwire/cert.pem"   # SSL certificate path
    key: "~/.agentwire/key.pem"     # SSL private key path

# Project directory settings
projects:
  dir: "~/projects"             # Base directory for projects
  worktrees:
    enabled: true               # Enable git worktree sessions
    suffix: "-worktrees"        # Worktree directory suffix
    auto_create_branch: true    # Create branch if it doesn't exist

# Text-to-speech settings
tts:
  backend: "chatterbox"         # TTS backend: chatterbox | elevenlabs | none
  url: "http://localhost:8100"  # Chatterbox server URL
  default_voice: "default"      # Default voice name

# Speech-to-text settings
stt:
  backend: "whisperkit"         # STT backend: whisperkit | whispercpp | openai | none
  model_path: "~/models/whisperkit/large-v3"  # Model path (for local backends)
  language: "en"                # Language code for transcription

# Agent settings
agent:
  command: "claude --dangerously-skip-permissions"
  # Placeholders available:
  #   {name}  - Session name
  #   {path}  - Working directory path
  #   {model} - Model name (if specified in room config)

# Remote machines registry
machines:
  file: "~/.agentwire/machines.json"

# Room configurations (voice, model per room)
rooms:
  file: "~/.agentwire/rooms.json"
```

## Environment Variables

Environment variables override config file settings:

| Variable | Description |
|----------|-------------|
| `AGENTWIRE_CONFIG` | Config file path |
| `AGENTWIRE_PORT` | Server port |
| `AGENTWIRE_HOST` | Server bind address |
| `OPENAI_API_KEY` | For OpenAI STT backend |
| `ELEVENLABS_API_KEY` | For ElevenLabs TTS backend |

## SSL Certificates

HTTPS is required for microphone access in browsers. Generate self-signed certs:

```bash
agentwire --generate-certs
```

Or manually with OpenSSL:

```bash
mkdir -p ~/.agentwire
openssl req -x509 -newkey rsa:4096 -keyout ~/.agentwire/key.pem \
  -out ~/.agentwire/cert.pem -days 365 -nodes \
  -subj "/CN=localhost"
```

## Machines Registry

For remote sessions, create `~/.agentwire/machines.json`:

```json
{
  "machines": [
    {
      "id": "gpu-server",
      "host": "192.168.1.100",
      "user": "developer",
      "projects_dir": "/home/developer/projects"
    },
    {
      "id": "devbox",
      "host": "devbox.local",
      "user": "dev"
    }
  ]
}
```

Requirements for remote machines:
- SSH key authentication configured
- tmux installed
- Your AI agent (Claude Code, etc.) installed

## Room Configurations

Room-specific settings are stored in `~/.agentwire/rooms.json`:

```json
{
  "myapp": {
    "voice": "alloy",
    "model": "sonnet",
    "chatbot_mode": false
  },
  "assistant": {
    "voice": "nova",
    "chatbot_mode": true
  }
}
```

Room config options:
- `voice` - TTS voice for this room
- `model` - AI model (passed to agent command as {model})
- `chatbot_mode` - If true, optimizes for fast conversational responses
- `machine` - Remote machine ID for this room
- `path` - Custom project path

## Defaults

If no config file exists, AgentWire uses these defaults:

| Setting | Default |
|---------|---------|
| Port | 8765 |
| Host | 0.0.0.0 |
| Projects dir | ~/projects |
| TTS backend | none |
| STT backend | Platform-dependent* |
| Agent command | claude |

*STT default: `whisperkit` on macOS, `whispercpp` on Linux/WSL2
