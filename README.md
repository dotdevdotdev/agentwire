<p align="center">
  <img src="docs/logo.png" alt="AgentWire" width="400">
</p>

<p align="center">
  <strong>Multi-room voice web interface for AI coding agents</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/agentwire-dev/"><img src="https://img.shields.io/pypi/v/agentwire-dev?color=green" alt="PyPI"></a>
  <a href="https://pypi.org/project/agentwire-dev/"><img src="https://img.shields.io/pypi/pyversions/agentwire-dev" alt="Python"></a>
  <a href="https://github.com/dotdevdotdev/agentwire/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dotdevdotdev/agentwire" alt="License"></a>
</p>

---

Push-to-talk voice input from any device to tmux sessions running Claude Code or any AI coding assistant.

## Features

- **Voice Rooms** - One room per AI agent session (tmux + your agent)
- **Push-to-Talk** - Hold to speak, release to send transcription
- **TTS Playback** - Agent responses spoken back via browser audio
- **Multi-Device** - Access from phone, tablet, laptop on your network
- **Room Locking** - One person talks at a time per room
- **Git Worktrees** - Multiple agents work same project in parallel
- **Remote Machines** - Orchestrate agents on remote servers
- **Claude Code Skills** - Session orchestration via `/sessions`, `/send`, `/spawn`, etc.

## Quick Start

```bash
# Install
pip install agentwire-dev

# Interactive setup (configures audio devices, creates config)
agentwire init

# Generate SSL certs (required for mic access in browsers)
agentwire generate-certs

# Start the portal
agentwire portal start

# Open in browser
# https://localhost:8765
```

## Requirements

- Python 3.10+
- tmux
- ffmpeg (for audio conversion)
- Claude Code or other AI agent (optional but recommended)

### Platform-specific

| Platform | Install Dependencies |
|----------|---------------------|
| macOS | `brew install tmux ffmpeg` |
| Linux | `apt install tmux ffmpeg` |
| WSL2 | `apt install tmux ffmpeg` |

## CLI Commands

```bash
# Setup
agentwire init              # Interactive setup wizard
agentwire generate-certs    # Generate SSL certificates

# Portal (web server)
agentwire portal start      # Start in background (tmux)
agentwire portal stop       # Stop the portal
agentwire portal status     # Check if running

# TTS Server (on GPU machine)
agentwire tts start         # Start TTS server in tmux
agentwire tts stop          # Stop TTS server
agentwire tts status        # Check if running

# Voice
agentwire say "Hello"           # Speak locally
agentwire say --room api "Done" # Send TTS to a room

# Voice Cloning
agentwire voiceclone start      # Start recording voice sample
agentwire voiceclone stop name  # Stop and upload as voice clone
agentwire voiceclone list       # List available voices

# Session Management
agentwire list                        # List all tmux sessions
agentwire new -s <name> [-p path] [-f] # Create new Claude session
agentwire output -s <session> [-n 100] # Read session output
agentwire kill -s <session>           # Kill session (clean shutdown)
agentwire send -s <session> "prompt"  # Send prompt to session

# Remote Machines
agentwire machine list          # List registered machines
agentwire machine add <id>      # Add a machine
agentwire machine remove <id>   # Remove a machine

# Development
agentwire dev               # Start orchestrator session
```

## Configuration

Run `agentwire init` for interactive setup, or create `~/.agentwire/config.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8765

projects:
  dir: "~/projects"
  worktrees:
    enabled: true

tts:
  backend: "chatterbox"  # chatterbox | none
  url: "http://localhost:8100"
  default_voice: "default"

stt:
  backend: "whisperkit"  # whisperkit | whispercpp | openai | none
  model_path: "~/models/whisperkit/large-v3"
  language: "en"

agent:
  command: "claude --dangerously-skip-permissions"
```

## Claude Code Skills

AgentWire includes skills for session orchestration from within Claude Code:

```bash
# Install skills
agentwire skills install
```

Then use in Claude Code:

| Command | Purpose |
|---------|---------|
| `/sessions` | List all tmux sessions |
| `/send <session> <prompt>` | Send prompt to session |
| `/output <session>` | Read session output |
| `/spawn <name>` | Smart session creation |
| `/new <name> [path]` | Create new session |
| `/kill <session>` | Destroy session |
| `/status` | Check all machines |
| `/machine-setup` | Interactive guide for adding remote machines |
| `/machine-remove` | Interactive guide for removing machines |

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

## TTS Setup

TTS requires a GPU machine running the Chatterbox server:

```bash
# On GPU machine
pip install agentwire-dev[tts]
agentwire tts start
```

Or run with TTS disabled (text-only):

```yaml
# In config.yaml
tts:
  backend: "none"
```

## STT Backends

| Backend | Platforms | Setup |
|---------|-----------|-------|
| `whisperkit` | macOS (Apple Silicon) | Install WhisperKit |
| `whispercpp` | All | Install whisper.cpp |
| `openai` | All | Set `OPENAI_API_KEY` |
| `none` | All | Typing only, no voice |

## Architecture

```
Phone/Tablet ──► AgentWire Portal ──► tmux session
   (voice)          (WebSocket)         (Claude Code)
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

# Install with uv
uv venv && uv pip install -e .

# Run
agentwire portal start
```

## License

MIT License - see [LICENSE](LICENSE)
