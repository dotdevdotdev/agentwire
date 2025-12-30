# AgentWire

> Living document. Update this, don't create new versions.

Multi-room voice web interface for AI coding agents. Push-to-talk voice input from any device to tmux sessions running Claude Code (or any AI coding agent).

## Project Status: Development

**No Backwards Compatibility** - Pre-launch project, no customers.

---

## What Is AgentWire?

A complete voice-enabled orchestration system for AI coding agents:

- **Web Portal** - Voice rooms with push-to-talk, TTS playback, room locking
- **TTS Server** - Host Chatterbox for voice synthesis
- **CLI Tools** - Manage sessions, speak text, orchestrate agents
- **Skills** - Claude Code skills for session orchestration

---

## CLI Commands

```bash
# Initialize configuration
agentwire init

# Portal (web server)
agentwire portal start     # Start in tmux (agentwire-portal)
agentwire portal stop      # Stop the portal
agentwire portal status    # Check if running

# TTS Server
agentwire tts start        # Start Chatterbox in tmux (agentwire-tts)
agentwire tts stop         # Stop TTS server
agentwire tts status       # Check TTS status

# Voice
agentwire say "Hello"      # Speak text locally
agentwire say --room api "Done"  # Send TTS to room

# Development
agentwire dev              # Start orchestrator session (agentwire)
agentwire generate-certs   # Generate SSL certificates
```

---

## Configuration

All config lives in `~/.agentwire/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Main configuration |
| `machines.json` | Remote machine registry |
| `rooms.json` | Per-session settings (voice, role, model) |
| `roles/*.md` | Role context files for Claude sessions |
| `cert.pem`, `key.pem` | SSL certificates |

### config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 8765

tts:
  backend: "chatterbox"
  url: "http://localhost:8100"
  default_voice: "default"

stt:
  backend: "whisperkit"  # whisperkit | whispercpp | openai | none

projects:
  dir: "~/projects"
  worktrees:
    enabled: true
```

---

## Skills (Session Orchestration)

Skills in `skills/` provide Claude Code integration:

| Skill | Command | Purpose |
|-------|---------|---------|
| sessions | `/sessions` | List all tmux sessions |
| send | `/send <session> <prompt>` | Send prompt to session |
| output | `/output <session>` | Read session output |
| spawn | `/spawn <name>` | Smart session creation |
| new | `/new <name> [path]` | Create new session |
| kill | `/kill <session>` | Destroy session |
| status | `/status` | Check all machines |
| jump | `/jump <session>` | Get attach instructions |

### Installing Skills

Copy skills to Claude Code's skills directory:

```bash
cp -r ~/projects/agentwire/skills/* ~/.claude/skills/agentwire/
```

Or symlink:

```bash
ln -s ~/projects/agentwire/skills ~/.claude/skills/agentwire
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Device (phone/tablet/laptop)                               │
│  └── Browser → https://localhost:8765                       │
└─────────────────────────────────────────────────────────────┘
                              │
                         WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│  AgentWire Portal (agentwire-portal tmux session)           │
│  ├── HTTP routes (dashboard, room pages)                    │
│  ├── WebSocket (output streaming, TTS audio)                │
│  ├── /transcribe (STT)                                      │
│  └── /send/{room} (prompt forwarding)                       │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
    Local tmux sessions            Remote via SSH
    (send-keys, capture-pane)      (session@machine)
```

---

## Development

```bash
# Run from source
cd ~/projects/agentwire
uv pip install -e .
agentwire --help

# Test imports
python -c "from agentwire import __version__; print(__version__)"
```

---

## Key Files

| File | Purpose |
|------|---------|
| `__main__.py` | CLI entry point, all commands |
| `server.py` | WebSocket server, HTTP routes, room management |
| `config.py` | Config dataclass, YAML loading, defaults |
| `tts/` | TTS backends (chatterbox, none) |
| `stt/` | STT backends (whisperkit, whispercpp, openai, none) |
| `agents/` | Agent backends (tmux local/remote) |
| `templates/` | HTML templates (dashboard, room) |
| `skills/` | Claude Code skills for orchestration |

---

## Session Naming Convention

| Format | Example | Description |
|--------|---------|-------------|
| `name` | `api` | Local session → ~/projects/api |
| `name/branch` | `api/feature` | Worktree session |
| `name@machine` | `ml@gpu-server` | Remote session |
| `name/branch@machine` | `ml/train@gpu-server` | Remote worktree |
