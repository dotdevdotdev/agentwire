# Mission: AgentWire Initial Release

> Extract nerve-web into a standalone open source project

**Branch:** `main` (greenfield)

## Objective

Create a clean, configurable, open source version of nerve-web called AgentWire. This is the multi-room voice web interface for AI coding agents (Claude Code sessions).

## Current State (nerve-web inventory)

### Hardcoded Values to Make Configurable

| Current | Description | Config Key |
|---------|-------------|------------|
| `~/projects` | Projects directory | `projects_dir` |
| `~/.claude/nerve/` | Config directory | CLI flag / env var |
| `rooms.json` | Room configurations | `rooms_file` |
| `http://localhost:8100` | TTS API URL | `tts_url` |
| `bashbunni` | Default TTS voice | `default_voice` |
| `0.0.0.0:8765` | Server host/port | `host`, `port` |
| WhisperKit model path | Speech-to-text model | `stt_model_path` |
| `cert.pem` / `key.pem` | SSL certificates | `ssl_cert`, `ssl_key` |
| `claude --dangerously-skip-permissions` | Agent command | `agent_command` |
| `machines.json` | Remote machine registry | `machines_file` |

### Features to Keep

- Multi-room WebSocket architecture
- Push-to-talk voice input with transcription
- TTS audio playback via browser
- Room locking (one person talks at a time)
- Terminal output display with ANSI color support
- Ambient mode (visual orb) vs terminal mode
- Voice/TTS settings per room
- Remote machine support via SSH

### Features to Make Optional/Pluggable

- TTS backend (chatterbox, elevenlabs, local, none)
- STT backend (whisperkit, whisper.cpp, openai, none)
- Agent command (claude, aider, cursor, custom)

## Target Project Structure

```
agentwire/
├── README.md                   # Overview, quick start, screenshots
├── LICENSE                     # MIT
├── pyproject.toml              # Package config (uv/pip installable)
├── agentwire/
│   ├── __init__.py
│   ├── __main__.py             # CLI entry point
│   ├── server.py               # Main web server (extracted from nerve-web)
│   ├── config.py               # Configuration loading/defaults
│   ├── tts/
│   │   ├── __init__.py
│   │   ├── base.py             # TTS interface
│   │   ├── chatterbox.py       # Chatterbox implementation
│   │   └── none.py             # No-op TTS (text only)
│   ├── stt/
│   │   ├── __init__.py
│   │   ├── base.py             # STT interface
│   │   ├── whisperkit.py       # WhisperKit implementation
│   │   └── none.py             # No-op STT (typing only)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py             # Agent interface
│   │   └── claude.py           # Claude Code implementation
│   └── templates/
│       ├── dashboard.html
│       └── room.html
├── examples/
│   ├── config.yaml             # Example config file
│   └── machines.json           # Example machines registry
└── docs/
    ├── configuration.md
    ├── tts-backends.md
    └── remote-machines.md
```

## Wave 1: Project Setup

| Task | Description |
|------|-------------|
| 1.1 | Create pyproject.toml with dependencies (aiohttp, pyyaml) |
| 1.2 | Create config.py with Config dataclass and YAML loading |
| 1.3 | Create CLI entry point (__main__.py) with argparse |
| 1.4 | Create example config.yaml |

## Wave 2: Core Server Extraction

| Task | Description |
|------|-------------|
| 2.1 | Extract HTML templates to separate files |
| 2.2 | Create server.py from nerve-web (use Config for all values) |
| 2.3 | Create TTS interface + chatterbox implementation |
| 2.4 | Create STT interface + whisperkit implementation |
| 2.5 | Create agent interface + claude implementation |

## Wave 3: Branding & Polish

| Task | Description |
|------|-------------|
| 3.1 | Update all branding from "Nerve" to "AgentWire" |
| 3.2 | Add logo to dashboard (use generated logo) |
| 3.3 | Create README.md with installation, quick start, screenshots |
| 3.4 | Add MIT LICENSE file |
| 3.5 | Add docs/configuration.md |

## Wave 4: Testing & Release

| Task | Description |
|------|-------------|
| 4.1 | Test with config file |
| 4.2 | Test without TTS (text-only mode) |
| 4.3 | Test installation via pip/uv |
| 4.4 | Create GitHub release |

## Configuration Format

```yaml
# ~/.agentwire/config.yaml

server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

projects:
  dir: "~/projects"

tts:
  backend: "chatterbox"  # chatterbox | elevenlabs | none
  url: "http://localhost:8100"
  default_voice: "bashbunni"

stt:
  backend: "whisperkit"  # whisperkit | openai | none
  model_path: "~/models/whisperkit/large-v3"
  language: "en"

agent:
  command: "claude --dangerously-skip-permissions"
  # Placeholders: {name}, {path}, {model}

machines:
  file: "~/.agentwire/machines.json"

rooms:
  file: "~/.agentwire/rooms.json"
```

## CLI Interface

```bash
# Run with default config
agentwire

# Run with custom config
agentwire --config /path/to/config.yaml

# Override specific settings
agentwire --port 9000 --no-tts

# Generate self-signed SSL certs
agentwire --generate-certs

# Show version
agentwire --version
```

## Completion Criteria

- [ ] Installable via `pip install agentwire` or `uv pip install agentwire`
- [ ] Works with zero config (sensible defaults)
- [ ] All paths/URLs configurable via YAML
- [ ] TTS/STT backends pluggable (can run without either)
- [ ] Branding is "AgentWire" throughout
- [ ] README has clear installation + usage instructions
- [ ] MIT licensed

## Notes

- Keep the single-file aesthetic where possible (server.py should be readable)
- Prioritize developer experience - should "just work" for common setups
- Support both Claude Code and generic tmux session agents
