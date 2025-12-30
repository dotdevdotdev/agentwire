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

### New Feature: Git Worktree Sessions

**Problem:** Multiple sessions working on the same project cause git conflicts.

**Solution:** Each session gets its own git worktree, enabling parallel work on different branches.

```
~/projects/
├── myapp/                      # Main repo (origin)
│   └── .git/
└── myapp-worktrees/            # Worktree container
    ├── feature-auth/           # Session 1 worktree (branch: feature-auth)
    ├── bugfix-login/           # Session 2 worktree (branch: bugfix-login)
    └── refactor-api/           # Session 3 worktree (branch: refactor-api)
```

**Session creation flow:**
1. User creates session "myapp/feature-auth"
2. AgentWire parses: project=myapp, branch=feature-auth
3. If worktree doesn't exist: `git worktree add ../myapp-worktrees/feature-auth -b feature-auth`
4. tmux session starts in worktree directory
5. Agent works on isolated branch

**Benefits:**
- Multiple agents work on same codebase simultaneously
- Each has its own working directory (no file conflicts)
- Changes stay on separate branches until merged
- Clean parallel development workflow

**Git-provider agnostic:** Works with any remote - GitHub, GitLab, Bitbucket, self-hosted, or no remote at all. AgentWire only uses local git commands (`git worktree add`, etc.).

### Project Types

| Type | Has Git? | Sessions | Use Case |
|------|----------|----------|----------|
| **Scratch** | No | Single only | Brainstorming, new ideas, experimentation |
| **Full** | Yes | Multiple (via worktrees) | Active development with parallel agents |

**Scratch → Full upgrade path:**
1. Create scratch session: `ideas` → `~/projects/ideas/`
2. Brainstorm with agent, create initial files
3. Initialize git: `git init && git add . && git commit -m "Initial"`
4. Now can create worktree sessions: `ideas/feature-a`, `ideas/feature-b`

**UI indication:**
- Scratch projects show "scratch" badge, no branch selector
- Full projects show current branch, option to create worktree session

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
| 2.6 | Implement git worktree session management |

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
  worktrees:
    enabled: true                    # Use git worktrees for parallel sessions
    suffix: "-worktrees"             # ~/projects/myapp-worktrees/
    auto_create_branch: true         # Create branch if it doesn't exist

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

## Session Naming Convention

| Format | Example | Result |
|--------|---------|--------|
| `project` | `myapp` | Single session in `~/projects/myapp` |
| `project/branch` | `myapp/feature-auth` | Worktree session in `~/projects/myapp-worktrees/feature-auth` |
| `project@machine` | `ml@devbox-1` | Remote session on devbox-1 |
| `project/branch@machine` | `ml/train-v2@gpu-server` | Remote worktree session |

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
- [ ] Git worktree sessions work (project/branch naming)
- [ ] Branding is "AgentWire" throughout
- [ ] README has clear installation + usage instructions
- [ ] MIT licensed

## Notes

- Keep the single-file aesthetic where possible (server.py should be readable)
- Prioritize developer experience - should "just work" for common setups
- Support both Claude Code and generic tmux session agents
