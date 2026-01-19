<p align="center">
  <img src="docs/logo.png" alt="AgentWire" width="400">
</p>

<p align="center">
  <strong>Multi-session voice web interface for AI coding agents</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/agentwire-dev/"><img src="https://img.shields.io/pypi/v/agentwire-dev?color=green" alt="PyPI"></a>
  <a href="https://pypi.org/project/agentwire-dev/"><img src="https://img.shields.io/pypi/pyversions/agentwire-dev" alt="Python"></a>
  <a href="https://github.com/dotdevdotdev/agentwire-dev/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dotdevdotdev/agentwire-dev" alt="License"></a>
</p>

---

Push-to-talk voice input from any device to tmux sessions running Claude Code or any AI coding assistant.

## Features

- **Desktop Control Center** - WinBox-powered window management with draggable/resizable session windows
- **Session Windows** - Monitor mode (read-only output) or Terminal mode (full xterm.js) per session
- **Push-to-Talk Voice** - Hold to speak, release to send transcription from any device
- **TTS Playback** - Agent responses spoken back via browser audio with smart routing
- **Multi-Device Access** - Control sessions from phone, tablet, or laptop on your network
- **Git Worktrees** - Multiple agents work the same project in parallel on separate branches
- **Remote Machines** - Orchestrate Claude Code sessions on remote servers via SSH
- **Safety Hooks** - 300+ dangerous command patterns blocked (rm -rf, git push --force, secret exposure)
- **Session Roles** - Orchestrator sessions coordinate voice, workers execute focused tasks
- **Permission Hooks** - Claude Code integration for permission dialogs in the portal

## What's New

**v0.1.0 (January 2026):**

- Desktop Control Center with WinBox-based window management
- Safety hooks with 300+ dangerous command patterns blocked
- Git worktree support for parallel agent work
- Session roles (orchestrator/worker) for coordinated workflows

## Quick Start

### System Requirements

Before installing, ensure you have:

| Requirement | Minimum | Check |
|-------------|---------|-------|
| **Claude Code** | Any recent | `claude --version` |
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
pip install agentwire-dev
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
pip install agentwire-dev
```

**WSL2:**

```bash
# Same as Ubuntu
sudo apt install tmux ffmpeg python3-pip
pip install agentwire-dev

# Note: Audio support limited in WSL
# Recommended: Use as remote worker with portal on Windows host
```

### Setup & Run

```bash
# Interactive setup (configures audio, creates config)
agentwire init

# Generate SSL certs (required for browser mic access)
agentwire generate-certs

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
# Setup & Diagnostics
agentwire init              # Interactive setup wizard
agentwire generate-certs    # Generate SSL certificates
agentwire doctor            # Auto-diagnose and fix common issues
agentwire network status    # Check service health

# Portal (web server)
agentwire portal start      # Start in background (tmux)
agentwire portal stop       # Stop the portal
agentwire portal status     # Check if running

# TTS Server (on GPU machine)
agentwire tts start         # Start TTS server in tmux
agentwire tts stop          # Stop TTS server
agentwire tts status        # Check if running

# STT Server (speech-to-text)
agentwire stt start         # Start STT server
agentwire stt stop          # Stop STT server
agentwire stt status        # Check if running

# Voice
agentwire say "Hello"              # Speak (auto-routes to browser or local)
agentwire say -s api "Done"        # Send TTS to specific session
agentwire listen start             # Start recording voice input
agentwire listen stop              # Stop and send transcription

# Voice Cloning
agentwire voiceclone start         # Start recording voice sample
agentwire voiceclone stop name     # Stop and upload as voice clone
agentwire voiceclone list          # List available voices
agentwire voiceclone delete name   # Delete a voice clone

# Session Management
agentwire list                         # List all tmux sessions
agentwire new -s <name> [-p path] [-f] # Create new Claude session
agentwire output -s <session> [-n 100] # Read session output
agentwire info -s <session>            # Get session info (cwd, panes)
agentwire kill -s <session>            # Kill session (clean shutdown)
agentwire send -s <session> "prompt"   # Send prompt to session
agentwire recreate -s <session>        # Destroy and recreate session
agentwire fork -s <session>            # Fork into new worktree

# Pane Management (workers)
agentwire spawn --roles worker    # Spawn worker pane in current session
agentwire split -s <session>      # Add terminal pane(s)
agentwire jump --pane <N>         # Focus a pane
agentwire detach -s <session>     # Move pane to its own session

# Safety & Security
agentwire safety check "command"  # Test if command would be blocked
agentwire safety status           # Show pattern counts and recent blocks
agentwire safety logs --tail 20   # Query audit logs
agentwire safety install          # Install damage control hooks
agentwire hooks status            # Check hook installation status

# Remote Machines & Tunnels
agentwire machine list            # List registered machines
agentwire machine add <id>        # Add a machine
agentwire machine remove <id>     # Remove a machine
agentwire tunnels up              # Create SSH tunnels for services
agentwire tunnels down            # Tear down tunnels
agentwire tunnels status          # Check tunnel health

# Session History
agentwire history list            # List conversation history
agentwire history show <id>       # Show session details
agentwire history resume <id>     # Resume session (forks)

# Roles & Projects
agentwire roles list              # List available roles
agentwire roles show <name>       # Show role details
agentwire projects list           # Discover projects

# Development
agentwire dev                     # Start agentwire session
agentwire rebuild                 # Reinstall from source
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

AgentWire provides TTS via the `agentwire say` command with automatic audio routing:

```bash
# In sessions, Claude (or users) can trigger TTS:
agentwire say "Hello world"  # Automatically routes to browser or local speakers
```

**How it works:**
- `agentwire say` automatically detects if a browser is connected to the session
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
git clone https://github.com/dotdevdotdev/agentwire-dev
cd agentwire-dev

# Install with uv
uv venv && uv pip install -e .

# Run in dev mode (picks up source changes)
agentwire portal start --dev

# After structural changes (pyproject.toml, new files)
agentwire rebuild
```

## Contributing

Contributions welcome! Please open an issue first to discuss changes.

- [Report bugs](https://github.com/dotdevdotdev/agentwire-dev/issues)
- [Request features](https://github.com/dotdevdotdev/agentwire-dev/issues)

## License

MIT License - see [LICENSE](LICENSE)
