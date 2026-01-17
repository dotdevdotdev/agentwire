<p align="center">
  <img src="docs/logo.png" alt="AgentWire" width="400">
</p>

<p align="center">
  <strong>Multi-session voice web interface for AI coding agents</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/agentwire-dev/"><img src="https://img.shields.io/pypi/v/agentwire-dev?color=green" alt="PyPI"></a>
  <a href="https://pypi.org/project/agentwire-dev/"><img src="https://img.shields.io/pypi/pyversions/agentwire-dev" alt="Python"></a>
  <a href="https://github.com/dotdevdotdev/agentwire/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dotdevdotdev/agentwire" alt="License"></a>
</p>

---

Push-to-talk voice input from any device to tmux sessions running Claude Code or any AI coding assistant.

## Features

- **Desktop Control Center** - OS-like interface with draggable/resizable windows for managing sessions
- **Session Windows** - Monitor mode (read-only) or Terminal mode (full interactive xterm.js) per session
- **Voice Sessions** - One session per AI agent (tmux + your agent)
- **Push-to-Talk** - Hold to speak, release to send transcription
- **Multiline Input** - Auto-expanding textarea with Enter/Shift+Enter support
- **TTS Playback** - Agent responses spoken back via browser audio
- **Multi-Device** - Access from phone, tablet, laptop on your network
- **Session Locking** - One person talks at a time per session
- **Git Worktrees** - Multiple agents work same project in parallel (CLI + UI support)
- **Remote Machines** - Orchestrate agents on remote servers
- **Session Templates** - Pre-configured session setups with initial prompts, voice, and permission modes
- **Safety Hooks** - Damage control system blocks dangerous operations (rm -rf, secret exposure, etc.)
- **Claude Code Skills** - Session orchestration via `/sessions`, `/send`, `/spawn`, etc.

## Recent Updates

**January 2026:**

- ✅ **Desktop Control Center** - Full frontend rewrite with WinBox-based window management
- ✅ **Multiline Input** - Auto-expanding textarea with natural Enter/Shift+Enter behavior ([#12](https://github.com/dotdevdotdev/agentwire/pull/12))
- ✅ **CLI Worktree Support** - Complete worktree operations: new, fork, recreate ([#11](https://github.com/dotdevdotdev/agentwire/pull/11))
- ✅ **Damage Control Hooks** - PreToolUse security hooks for parallel agent protection ([#9](https://github.com/dotdevdotdev/agentwire/pull/9))
- ✅ **Session Templates** - Pre-configured session setups with voice, permissions, initial prompts ([#8](https://github.com/dotdevdotdev/agentwire/pull/8))

## Quick Start

### System Requirements

Before installing, ensure you have:

| Requirement | Minimum | Check |
|-------------|---------|-------|
| **Python** | 3.10+ | `python3 --version` |
| **tmux** | Any recent | `tmux -V` |
| **ffmpeg** | Any recent | `ffmpeg -version` |

**Important for Ubuntu 24.04+ users:** Ubuntu's externally-managed Python requires using a virtual environment. See the Ubuntu installation instructions below.

### Platform-Specific Installation

**macOS:**

```bash
# Install dependencies
brew install tmux ffmpeg

# If Python < 3.10, upgrade via pyenv
brew install pyenv
pyenv install 3.12.0
pyenv global 3.12.0

# Install AgentWire
pip install git+https://github.com/dotdevdotdev/agentwire.git
```

**Ubuntu/Debian:**

```bash
# Install dependencies
sudo apt update
sudo apt install tmux ffmpeg python3-pip

# For Ubuntu 24.04+ (recommended approach):
# Create venv to avoid externally-managed error
python3 -m venv ~/.agentwire-venv
source ~/.agentwire-venv/bin/activate
echo 'source ~/.agentwire-venv/bin/activate' >> ~/.bashrc

# Install AgentWire
pip install git+https://github.com/dotdevdotdev/agentwire.git
```

**WSL2:**

```bash
# Same as Ubuntu
sudo apt install tmux ffmpeg python3-pip
pip install git+https://github.com/dotdevdotdev/agentwire.git

# Note: Audio support limited in WSL
# Recommended: Use as remote worker with portal on Windows host
```

### Setup & Run

```bash
# Interactive setup (configures audio, creates config)
agentwire init

# Generate SSL certs (required for browser mic access)
agentwire generate-certs

# Install Claude Code skills and damage control hooks
agentwire skills install

# Start the portal
agentwire portal start

# Open in browser
# https://localhost:8765
```

**Expected Install Time:**
- **First time:** 20-30 minutes (including dependency installation, configuration)
- **Subsequent installs:** 5 minutes (if dependencies already present)

### Common First-Time Issues

| Issue | Solution |
|-------|----------|
| "Python 3.X.X not in '>=3.10'" | Upgrade Python (see platform instructions above) |
| "externally-managed-environment" (Ubuntu) | Use venv approach (see Ubuntu instructions above) |
| "agentwire: command not found" | Add to PATH: `export PATH="$HOME/.local/bin:$PATH"` |
| "ffmpeg not found" | Install ffmpeg (see platform commands above) |
| SSL warnings in browser | Run `agentwire generate-certs`, then accept cert in browser |

**Full troubleshooting guide:** See `docs/TROUBLESHOOTING.md` after installation

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
agentwire say --session api "Done" # Send TTS to a session

# Voice Cloning
agentwire voiceclone start      # Start recording voice sample
agentwire voiceclone stop name  # Stop and upload as voice clone
agentwire voiceclone list       # List available voices

# Session Management
agentwire list                        # List all tmux sessions
agentwire new -s <name> [-p path] [-f] # Create new Claude session
agentwire new -s <name> --template <template> # Create session with template
agentwire output -s <session> [-n 100] # Read session output
agentwire kill -s <session>           # Kill session (clean shutdown)
agentwire send -s <session> "prompt"  # Send prompt to session

# Session Templates
agentwire template list               # List available templates
agentwire template show <name>        # Show template details
agentwire template create <name>      # Create new template
agentwire template delete <name>      # Delete a template
agentwire template install-samples    # Install sample templates

# Safety & Security
agentwire safety check "command"      # Test if command would be blocked
agentwire safety status               # Show pattern counts and recent blocks
agentwire safety logs --tail 20       # Query audit logs
agentwire safety install              # Install damage control hooks

# Remote Machines
agentwire machine list          # List registered machines
agentwire machine add <id>      # Add a machine
agentwire machine remove <id>   # Remove a machine

# Development
agentwire dev               # Start agentwire session
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

## Session Templates

Session templates provide pre-configured setups with initial prompts, voice settings, and permission modes.

### Install Sample Templates

```bash
agentwire template install-samples
```

### Available Templates

| Template | Description | Mode | Use Case |
|----------|-------------|------|----------|
| `bug-fix` | Systematic debugging assistant | bypass | Investigating and fixing bugs |
| `code-review` | Code review and improvements | bypass | Reviewing code quality |
| `feature-impl` | Feature implementation with planning | bypass | Building new features |
| `voice-assistant` | Voice-only assistant, no code execution | restricted | Conversational assistance |

### Usage

```bash
# Create session with template
agentwire new -s myproject --template feature-impl

# Create custom template
agentwire template create my-template
```

Templates can include:
- **Initial prompts** - Auto-sent when session starts
- **Voice settings** - Default TTS voice for the session
- **Permission modes** - bypass (fast) or restricted (voice-only)
- **Variable expansion** - `{{project_name}}`, `{{branch}}`

## Safety & Security

AgentWire includes damage control hooks that protect against dangerous operations across all Claude Code sessions.

### What's Protected

**300+ dangerous command patterns:**
- Destructive operations: `rm -rf`, `git push --force`, `git reset --hard`
- Cloud platforms: AWS, GCP, Firebase, Vercel, Netlify, Cloudflare
- Databases: SQL DROP/TRUNCATE, Redis FLUSHALL, MongoDB dropDatabase
- Containers: Docker/Kubernetes destructive operations
- Infrastructure: Terraform destroy, Pulumi destroy

**Sensitive file protection:**
- **Zero-access paths** (no operations): `.env`, SSH keys, credentials, API tokens
- **Read-only paths**: System configs, lock files
- **No-delete paths**: `.git/`, `README.md`, mission files

### Usage

```bash
# Test if command would be blocked
agentwire safety check "rm -rf /tmp"
# → ✗ Decision: BLOCK (rm with recursive or force flags)

# Check system status
agentwire safety status
# → Shows pattern counts, recent blocks, audit log location

# Query audit logs
agentwire safety logs --tail 20
# → Shows recent blocked/allowed operations with timestamps

# Install hooks (first time setup)
agentwire safety install
```

### How It Works

PreToolUse hooks intercept Bash, Edit, and Write operations before execution:
- **Blocked** → Operation prevented, security message shown
- **Allowed** → Operation proceeds normally
- **Ask** → User confirmation required (for risky but valid operations)

All decisions are logged to `~/.agentwire/logs/damage-control/` for audit trails.

## Voice Integration

AgentWire provides TTS via the `say` command with automatic audio routing:

```bash
# One-time setup
agentwire skills install  # Installs say command + Claude Code skills

# In sessions, Claude (or users) can trigger TTS:
say "Hello world"  # Automatically routes to browser or local speakers
```

**How it works:**
- `say` automatically detects if a browser is connected to the session
- If connected: streams audio to browser (tablet/phone/laptop)
- If not connected: plays audio locally (Mac speakers)
- Session detection uses `AGENTWIRE_SESSION` env var (set automatically when session is created)
- For remote machines, configure portal URL in `~/.agentwire/portal_url`


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

## STT (Speech-to-Text)

STT runs locally using WhisperKit (Apple's CoreML-optimized Whisper). No server or Docker needed.

**Requirements:**
- macOS with Apple Silicon (M1/M2/M3)
- [whisperkit-cli](https://github.com/argmaxinc/WhisperKit): `brew install whisperkit-cli`
- A WhisperKit model (e.g., via [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper))

**Default model path:** `~/Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930`

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
