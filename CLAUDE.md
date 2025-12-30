# AgentWire

> Living document. Update this, don't create new versions.

Multi-room voice web interface for AI coding agents. Push-to-talk voice input from any device to tmux sessions running Claude Code (or any AI coding agent).

## Project Status: Development

**No Backwards Compatibility** - Pre-launch project, no customers.

---

## What Is AgentWire?

A web server that provides:
- **Voice rooms** - One room per AI agent session (tmux + Claude Code)
- **Push-to-talk** - Hold button to speak, release to send transcription to agent
- **TTS playback** - Agent responses are spoken back via browser audio
- **Multi-device** - Access from phone, tablet, laptop on same network
- **Room locking** - Only one person can talk at a time per room

```
Phone/Tablet ──► AgentWire Server ──► tmux session
   (voice)          (WebSocket)         (Claude Code)
```

---

## Architecture

```
agentwire/
├── __main__.py      # CLI entry point
├── server.py        # Main aiohttp web server
├── config.py        # YAML config loading
├── tts/             # Text-to-speech backends
├── stt/             # Speech-to-text backends
├── agents/          # Agent command templates
└── templates/       # HTML templates (dashboard, room)
```

---

## Configuration

Config file: `~/.agentwire/config.yaml`

Key settings:
| Setting | Default | Description |
|---------|---------|-------------|
| `server.port` | 8765 | HTTPS port |
| `tts.backend` | none | TTS backend (chatterbox, elevenlabs, none) |
| `stt.backend` | whisperkit | STT backend (whisperkit, openai, none) |
| `agent.command` | claude | Command to start agent in tmux |

---

## Development

```bash
# Run from source
cd ~/projects/agentwire
uv run python -m agentwire

# Install editable
uv pip install -e .
agentwire
```

---

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | WebSocket server, HTTP routes, room management |
| `config.py` | Config dataclass, YAML loading, defaults |
| `tts/chatterbox.py` | Chatterbox TTS integration |
| `stt/whisperkit.py` | WhisperKit STT integration |
| `templates/room.html` | Voice room UI (orb, push-to-talk) |

---

## Inherited From Nerve

This project extracts and generalizes `nerve-web` from the private nerve project. Key differences:

| nerve-web | AgentWire |
|-----------|-----------|
| Hardcoded paths | Configurable via YAML |
| `~/.claude/nerve/` | `~/.agentwire/` |
| Claude-specific | Agent-agnostic |
| Private use | Open source (MIT) |
