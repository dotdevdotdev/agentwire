# AgentWire

Multi-room voice web interface for AI coding agents. Push-to-talk voice input from any device to tmux sessions running Claude Code, Aider, or any AI coding assistant.

## Features

- **Voice Rooms** - One room per AI agent session (tmux + your agent)
- **Push-to-Talk** - Hold to speak, release to send transcription
- **TTS Playback** - Agent responses spoken back via browser audio
- **Multi-Device** - Access from phone, tablet, laptop on your network
- **Room Locking** - One person talks at a time per room
- **Git Worktrees** - Multiple agents work same project in parallel
- **Cross-Platform** - macOS, Linux, WSL2

## Quick Start

```bash
# Install
pip install agentwire

# Generate SSL certs (required for mic access)
agentwire --generate-certs

# Start server
agentwire

# Open in browser
# https://localhost:8765
```

## Requirements

- Python 3.10+
- tmux
- ffmpeg (for audio conversion)
- SSL certificates (for microphone access in browser)

### Platform-specific

| Platform | Install Dependencies |
|----------|---------------------|
| macOS | `brew install tmux ffmpeg` |
| Linux | `apt install tmux ffmpeg` |
| WSL2 | `apt install tmux ffmpeg` |

## Configuration

Create `~/.agentwire/config.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

projects:
  dir: "~/projects"
  worktrees:
    enabled: true
    suffix: "-worktrees"

tts:
  backend: "chatterbox"  # chatterbox | elevenlabs | none
  url: "http://localhost:8100"
  default_voice: "default"

stt:
  backend: "whisperkit"  # whisperkit | whispercpp | openai | none
  model_path: "~/models/whisperkit/large-v3"
  language: "en"

agent:
  command: "claude --dangerously-skip-permissions"
```

## Session Types

### Simple Session
```
myapp -> ~/projects/myapp/
```
Single agent working on a project.

### Worktree Session
```
myapp/feature-auth -> ~/projects/myapp-worktrees/feature-auth/
```
Multiple agents working on the same project in parallel, each on their own branch.

### Remote Session
```
ml@gpu-server -> SSH to gpu-server, session "ml"
```
Agent running on a remote machine.

## CLI Options

```bash
agentwire                      # Start with defaults
agentwire --config /path/to   # Custom config file
agentwire --port 9000          # Override port
agentwire --no-tts             # Disable text-to-speech
agentwire --no-stt             # Disable speech-to-text
agentwire --generate-certs     # Generate SSL certificates
agentwire --version            # Show version
```

## TTS Backends

| Backend | Description | Setup |
|---------|-------------|-------|
| `chatterbox` | Self-hosted Chatterbox TTS | Run Chatterbox server |
| `elevenlabs` | ElevenLabs API | Set `ELEVENLABS_API_KEY` |
| `none` | Disabled | No audio output |

## STT Backends

| Backend | Platforms | Setup |
|---------|-----------|-------|
| `whisperkit` | macOS | Install WhisperKit CLI |
| `whispercpp` | All | Install whisper.cpp |
| `openai` | All | Set `OPENAI_API_KEY` |
| `none` | All | Typing only, no voice |

## Architecture

```
Phone/Tablet ──► AgentWire Server ──► tmux session
   (voice)          (WebSocket)         (Claude/Aider)
     │                   │                    │
     │    push-to-talk   │   transcription    │
     │◄─────────────────►│◄──────────────────►│
     │    TTS audio      │   agent output     │
```

## Development

```bash
# Clone
git clone https://github.com/dotdevdotdev/agentwire
cd agentwire

# Install editable
pip install -e .

# Run
agentwire
```

## License

MIT License - see [LICENSE](LICENSE)

## Links

- Website: https://agentwire.dev
- Repository: https://github.com/dotdevdotdev/agentwire
