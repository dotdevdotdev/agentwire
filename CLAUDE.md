# AgentWire

> Living document. Update this, don't create new versions.

Multi-room voice web interface for AI coding agents. Push-to-talk voice input from any device to tmux sessions running Claude Code.

## Project Status: Development

**No Backwards Compatibility** - Pre-launch project, no customers.

---

## CRITICAL: Development Workflow

**`uv tool install` caches builds and won't pick up source changes.**

### Option 1: Run from source with `--dev` (recommended)

```bash
agentwire portal stop
agentwire portal start --dev   # Uses uv run, picks up code changes instantly
```

### Option 2: Rebuild the installed tool

```bash
agentwire rebuild   # Clears uv cache, uninstalls, reinstalls from source
```

**Do NOT use:**
- `uv tool install . --force` - uses cached wheel, ignores source changes
- `uv tool uninstall && uv tool install .` - also uses cached wheel

---

## CRITICAL: Always Use AgentWire CLI

**Never use raw tmux commands when an agentwire CLI alternative exists.**

| Instead of... | Use... |
|---------------|--------|
| `tmux new-session -d -s name` | `agentwire new -s name` |
| `tmux send-keys -t name "text" Enter` | `agentwire send -s name "text"` |
| `tmux capture-pane -t name -p` | `agentwire output -s name` |
| `tmux kill-session -t name` | `agentwire kill -s name` |
| `tmux list-sessions` | `agentwire list` |
| `ssh host "tmux ..."` | `agentwire <cmd> -s name@machine` |
| `git worktree add ...` | `agentwire new -s project/branch` |
| `git worktree remove ...` | `agentwire kill -s project/branch` |

**Why:** CLI handles worktrees, rooms.json, Claude startup flags, clean shutdown sequences, and remote SSH transparently.

---

## Quick Start

```bash
pip install git+https://github.com/dotdevdotdev/agentwire.git
agentwire init                    # Interactive setup
agentwire generate-certs          # SSL certificates
agentwire skills install          # Claude Code skills
agentwire portal start            # Start web portal
```

See [docs/installation.md](docs/installation.md) for platform-specific notes and troubleshooting.

---

## CLI Commands

All commands support `session@machine` format for remote operations and `--json` for machine-readable output.

### Core Commands

| Command | Description | Example |
|---------|-------------|---------|
| `agentwire init` | Interactive configuration setup | |
| `agentwire portal start` | Start web portal in tmux | `--dev` for source mode |
| `agentwire portal stop` | Stop portal | |
| `agentwire tts start` | Start TTS server | |
| `agentwire say "text"` | Smart TTS routing | `-v voice`, `-r room` |

### Session Management

| Command | Description | Example |
|---------|-------------|---------|
| `agentwire list` | List all sessions (all machines) | `--local` for local only |
| `agentwire new -s <name>` | Create Claude Code session | `-t template`, `--worker` |
| `agentwire send -s <session> "prompt"` | Send prompt | |
| `agentwire output -s <session>` | Read output | `-n 100` for more lines |
| `agentwire kill -s <session>` | Clean shutdown | |
| `agentwire recreate -s <name>` | Fresh worktree restart | |
| `agentwire fork -s <src> -t <dst>` | Fork with conversation | |

### Session Name Formats

| Format | Example | Description |
|--------|---------|-------------|
| `name` | `api` | Local session |
| `project/branch` | `api/feature` | Local worktree |
| `name@machine` | `ml@gpu-server` | Remote session |
| `project/branch@machine` | `ml/train@gpu-server` | Remote worktree |

### Other Commands

| Category | Commands |
|----------|----------|
| **Voice** | `say`, `listen`, `voiceclone` |
| **Templates** | `template list/show/create/delete` |
| **Safety** | `safety check/status/logs/install` |
| **Skills** | `skills install/status/uninstall` |
| **Machines** | `machine list/add/remove` |
| **Network** | `network status`, `tunnels up/down/status`, `doctor` |
| **Dev** | `dev`, `rebuild`, `uninstall`, `generate-certs` |

See [docs/CLI-REFERENCE.md](docs/CLI-REFERENCE.md) for complete examples and JSON output formats.

---

## Configuration

All config lives in `~/.agentwire/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Main configuration |
| `machines.json` | Remote machine registry |
| `rooms.json` | Per-session settings (voice, role, permissions) |
| `templates/*.yaml` | Session templates |
| `roles/*.md` | Role context for Claude sessions |
| `cert.pem`, `key.pem` | SSL certificates |

### config.yaml Overview

```yaml
server:
  host: "0.0.0.0"
  port: 8765

tts:
  backend: "runpod"       # runpod | chatterbox | none
  default_voice: "bashbunni"

stt:
  backend: "whisperkit"   # whisperkit | whispercpp | openai | remote | none

projects:
  dir: "~/projects"
  worktrees:
    enabled: true
```

### Session Templates

Templates pre-configure sessions with voice, permissions, and initial prompts.

```bash
agentwire template list                    # List templates
agentwire template install-samples         # Install samples
agentwire new -s project -t code-review    # Use template
```

Template format (`~/.agentwire/templates/code-review.yaml`):

```yaml
name: code-review
voice: bashbunni
initial_prompt: "Review the codebase for bugs and improvements."
bypass_permissions: true
```

---

## Permission Modes

Sessions run in one of three permission modes:

| Mode | Setting | Behavior |
|------|---------|----------|
| **Bypass** | `bypass_permissions: true` | No prompts, full trust (default) |
| **Normal** | `bypass_permissions: false` | Permission prompts via portal |
| **Restricted** | `restricted: true` | Only voice/questions allowed |

### When to Use Each Mode

| Use Case | Mode |
|----------|------|
| Trusted projects you own | Bypass |
| Rapid development | Bypass |
| Reviewing unfamiliar code | Normal |
| Untrusted prompts | Normal |
| Voice-only agent | Restricted |
| Public demo/kiosk | Restricted |

### How Permission Modes Work

**Bypass:** Claude acts immediately without asking.

**Normal:** Uses hook system:
1. Claude triggers permission-requiring action
2. Portal shows modal with details and diff preview
3. User clicks Allow/Deny
4. Decision sent back to Claude

**Restricted:** Auto-handles permissions:
- `AskUserQuestion` → allowed
- `say`/`remote-say` → allowed
- Everything else → auto-denied

### Room Configuration

Set per-session in `~/.agentwire/rooms.json`:

```json
{
  "my-project": {
    "voice": "bashbunni",
    "bypass_permissions": true
  },
  "voice-only-agent": {
    "restricted": true
  }
}
```

---

## Session Types (Orchestrator + Workers)

Sessions can be typed as **orchestrator** or **worker** to separate voice/interaction from execution.

### Session Type Comparison

| Aspect | Orchestrator | Worker |
|--------|--------------|--------|
| **Purpose** | Voice interface, coordination | Autonomous execution |
| **Create with** | `agentwire new -s project` | `agentwire new -s project/task --worker` |
| **Voice** | ✅ Can use say/remote-say | ❌ No voice output |
| **File access** | ❌ No Edit/Write/Read | ✅ Full Claude Code |
| **User questions** | ✅ AskUserQuestion | ❌ Cannot ask user |

### Orchestrator Workflow

```bash
# Spawn parallel workers
agentwire new myproject/auth --worker
agentwire new myproject/tests --worker

# Send instructions
agentwire send -s myproject/auth "Implement login"
agentwire send -s myproject/tests "Write integration tests"

# Monitor progress
agentwire output -s myproject/auth
```

### Tool Restrictions

**Orchestrator:**
- BLOCKED: Edit, Write, Read, Glob, Grep, NotebookEdit
- ALLOWED: Task, Bash (agentwire only), AskUserQuestion, WebFetch, TodoWrite

**Worker:**
- BLOCKED: AskUserQuestion, say, remote-say
- ALLOWED: Everything else

### Role Files

| Type | Role File |
|------|-----------|
| Orchestrator | `~/.agentwire/roles/orchestrator.md` |
| Worker | `~/.agentwire/roles/worker.md` |

---

## Voice Layer

TTS via unified `agentwire say` command with smart audio routing.

```bash
agentwire say "Hello"              # Smart routing
agentwire say "Hello" -v bashbunni # Specify voice
agentwire say "Hello" -r myroom    # Specify room
```

### Smart Audio Routing

1. Determine room: `--room` arg → `AGENTWIRE_ROOM` env → tmux session name
2. Check portal connections for that room
3. Route: Browser connected → portal (plays on browser). No connections → local audio

### TTS Backends

| Backend | Config | Description |
|---------|--------|-------------|
| `runpod` | `tts.backend: "runpod"` | RunPod serverless (recommended) |
| `chatterbox` | `tts.backend: "chatterbox"` | Local GPU server (CUDA required) |

See [docs/runpod-tts.md](docs/runpod-tts.md) for RunPod setup.

### Voice Cloning

```bash
agentwire voiceclone start         # Start recording
agentwire voiceclone stop myvoice  # Stop and upload
agentwire voiceclone list          # List voices
```

---

## Safety & Security (Damage Control)

PreToolUse hooks protect against dangerous operations.

### What's Protected

**300+ dangerous patterns:** `rm -rf`, `git reset --hard`, `git push --force`, AWS/GCP/Firebase deletions, SQL DROP, Redis FLUSHALL, Terraform destroy, etc.

**Three-tier path protection:**

| Level | Operations | Examples |
|-------|------------|----------|
| **Zero-Access** | None allowed | `.env`, `~/.ssh/`, `*.pem`, API tokens |
| **Read-Only** | Read only | `/etc/`, lock files |
| **No-Delete** | Read/write, no delete | `.git/`, `README.md` |

### CLI Commands

```bash
agentwire safety check "rm -rf /tmp"  # Test if blocked
agentwire safety status               # Pattern counts, recent blocks
agentwire safety logs --tail 20       # Query audit logs
agentwire safety install              # Install hooks
```

### Hook System

Hooks intercept Bash, Edit, Write before execution:
1. Pattern matching against `~/.agentwire/hooks/damage-control/patterns.yaml`
2. Decision: Block (prevented), Allow (proceeds), Ask (user confirms)
3. Logged to `~/.agentwire/logs/damage-control/`

See `docs/security/damage-control.md` for customizing patterns.

---

## Skills (Claude Code Integration)

Skills provide session orchestration from within Claude Code.

| Skill | Command | Purpose |
|-------|---------|---------|
| `/sessions` | List all sessions | |
| `/send <session> <prompt>` | Send prompt | |
| `/output <session>` | Read output | |
| `/new <name>` | Create session | |
| `/kill <session>` | Destroy session | |
| `/workers` | List workers | |
| `/spawn-worker <name>` | Create worker | |
| `/status` | Check all machines | |

### Installing Skills

```bash
agentwire skills install    # Creates symlink to ~/.claude/skills/agentwire
agentwire skills status     # Check installation
agentwire skills uninstall  # Remove
```

---

## Portal Features

Three modes for interacting with sessions (all work simultaneously):

| Mode | Input | Output | Use For |
|------|-------|--------|---------|
| **Ambient** | Voice (push-to-talk) | Orb visualization | Hands-free, voice-driven |
| **Monitor** | Text input | Polling display | Observing, text prompts |
| **Terminal** | xterm.js | Full terminal | Real development work |

### Key Features

- **Voice input/output** via push-to-talk and TTS
- **AskUserQuestion popups** with clickable options
- **Permission modals** with diff preview
- **Image attachments** via paste or file upload
- **Multiline input** with Enter/Shift+Enter

See [docs/PORTAL.md](docs/PORTAL.md) for complete portal documentation.

---

## Key Files

| File | Purpose |
|------|---------|
| `__main__.py` | CLI entry point |
| `server.py` | WebSocket server, HTTP routes |
| `config.py` | Config loading |
| `tts/` | TTS backends |
| `stt/` | STT backends |
| `agents/` | Agent backends (tmux) |
| `templates/` | HTML templates |
| `skills/` | Claude Code skills |
| `worktree.py` | Git worktree utilities |
| `tunnels.py` | SSH tunnel management |

---

## Further Reading

| Document | Content |
|----------|---------|
| [docs/installation.md](docs/installation.md) | Platform-specific install, troubleshooting |
| [docs/CLI-REFERENCE.md](docs/CLI-REFERENCE.md) | Complete CLI examples, JSON output |
| [docs/PORTAL.md](docs/PORTAL.md) | Portal modes, API, WebSocket |
| [docs/docker-deployment.md](docs/docker-deployment.md) | Container deployment |
| [docs/runpod-tts.md](docs/runpod-tts.md) | RunPod serverless TTS setup |
| [docs/architecture.md](docs/architecture.md) | System architecture, network topology |
| [docs/remote-machines.md](docs/remote-machines.md) | Remote machine management |
| [docs/security/damage-control.md](docs/security/damage-control.md) | Security hooks customization |
