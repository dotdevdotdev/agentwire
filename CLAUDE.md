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
  default_voice: "bashbunni"
  voices_dir: "~/.agentwire/voices"  # Where voice clones are stored

stt:
  backend: "whisperkit"  # whisperkit | whispercpp | openai | none
  model_path: "~/Library/Application Support/MacWhisper/models/..."
  language: "en"

audio:
  input_device: 1  # Audio input device index (use `agentwire init` to select)

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

## Portal Features

### Room UI Controls

The room page header provides device and voice controls:

| Control | Purpose |
|---------|---------|
| Mode toggle | Switch between ambient (orb) and terminal view |
| Mic selector | Choose audio input device (saved to localStorage) |
| Speaker selector | Choose audio output device (Chrome/Edge only) |
| Voice selector | TTS voice for this room (saved to rooms.json) |

### Orb States

The ambient mode orb shows the current interaction state:

| State | Color | Meaning |
|-------|-------|---------|
| Ready | Green | Idle, waiting for input |
| Listening | Yellow | Recording voice input |
| Processing | Purple | Transcribing or agent working |
| Generating | Blue | TTS generating voice |
| Speaking | Green | Playing audio response |

The portal auto-detects session activity - if any output appears (even from manual commands), it switches to Processing. Returns to Ready after 10s of inactivity.

### Image Attachments

Attach images to messages for debugging, sharing screenshots, or reference:

| Method | Description |
|--------|-------------|
| Paste (Ctrl/Cmd+V) | Paste image from clipboard |
| Attach button (📎) | Click to select image file |

Images are uploaded to the configured `uploads.dir` and referenced in messages using Claude Code's `@/path/to/file` syntax. Configure in `config.yaml`:

```yaml
uploads:
  dir: "~/.agentwire/uploads"  # Should be accessible from all machines
  max_size_mb: 10
  cleanup_days: 7              # Auto-delete old uploads
```

### Say Command Detection

The portal monitors terminal output for `say` and `remote-say` commands:

```bash
say "Hello world"           # Detected from output, triggers TTS
remote-say "Task complete"  # Also posts to /api/say/{room}
```

TTS audio includes 300ms silence padding to prevent first-syllable cutoff.

### Portal API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sessions` | GET | List all tmux sessions |
| `/api/create` | POST | Create new session |
| `/api/room/{name}/config` | POST | Update room config (voice, etc.) |
| `/api/say/{name}` | POST | Generate TTS and broadcast to room |
| `/api/voices` | GET | List available TTS voices |
| `/transcribe` | POST | Transcribe audio (multipart form) |
| `/upload` | POST | Upload image (multipart form) |
| `/send/{name}` | POST | Send text to session |

---

## TTS Server Setup (GPU Machine)

The TTS server runs Chatterbox TurboTTS and requires a CUDA GPU. Install on a GPU machine:

```bash
# Clone and install
cd ~/projects
git clone git@github.com:dotdevdotdev/agentwire.git
cd agentwire

# Create venv and install with TTS extras
uv venv
uv pip install -e '.[tts]'

# Start TTS server in tmux
source .venv/bin/activate
agentwire tts start     # Runs in tmux session 'agentwire-tts'
```

### TTS Commands

| Command | Purpose |
|---------|---------|
| `agentwire tts start` | Start server in tmux (agentwire-tts) |
| `agentwire tts serve` | Run in foreground (for debugging) |
| `agentwire tts stop` | Stop the tmux session |
| `agentwire tts status` | Check if running |

### TTS API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/tts` | POST | Generate audio from text |
| `/voices` | GET | List available voices |
| `/voices/{name}` | POST | Upload voice clone (~10s WAV) |
| `/voices/{name}` | DELETE | Delete voice clone |
| `/transcribe` | POST | Transcribe audio (Whisper) |
| `/health` | GET | Health check |

### Voice Cloning

Record a ~10 second WAV file and upload:

```bash
agentwire voiceclone start   # Start recording
agentwire voiceclone stop myvoice  # Stop and upload
agentwire voiceclone list    # List voices
```

Voices are stored in `~/.agentwire/voices/` and synced across portal config.

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
│  ├── /send/{room} (prompt forwarding)                       │
│  └── /api/say/{room} (TTS broadcast)                        │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
    Local tmux sessions            Remote via SSH
    (send-keys, capture-pane)      (session@machine)
```

---

## Remote Machine Setup (Ubuntu/Linux)

Complete guide for adding a new remote machine to run Claude Code sessions with voice support.

### Overview

| Step | Where | What |
|------|-------|------|
| 1-5 | Remote machine | System setup, deps, repos, Claude auth |
| 6-7 | Portal machine | Register machine, start tunnel |
| 8-9 | Remote machine | Config, voice commands |
| 10 | Either | Test |

---

### Step 1: Create Non-Root User (Remote)

Claude Code refuses to run as root. SSH in as root and create a user:

```bash
ssh root@<ip-address>

# Create user with sudo access
useradd -m -s /bin/bash agentwire
echo "agentwire ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/agentwire

# Copy SSH authorized_keys
mkdir -p /home/agentwire/.ssh
cp /root/.ssh/authorized_keys /home/agentwire/.ssh/
chown -R agentwire:agentwire /home/agentwire/.ssh
chmod 700 /home/agentwire/.ssh
chmod 600 /home/agentwire/.ssh/authorized_keys
exit
```

**On your LOCAL machine**, add to `~/.ssh/config`:
```
Host do-1
    HostName <ip-address>
    User agentwire
    IdentityFile ~/.ssh/<your-key>
```

### Step 2: Install Dependencies (Remote)

```bash
ssh do-1

# System packages
sudo apt-get update
sudo apt-get install -y python3 python3-pip tmux git curl jq

# Node.js 22.x
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt-get install -y nodejs

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Environment setup
cat >> ~/.bashrc << 'EOF'
source ~/.local/bin/env
export COLORTERM=truecolor
export PATH="$HOME/.local/share/agentwire-venv/bin:$PATH"
EOF
source ~/.bashrc

# Claude Code
sudo npm install -g @anthropic-ai/claude-code
```

### Step 3: Setup GitHub SSH Keys (Remote)

Each private repo needs its own deploy key (GitHub limitation):

```bash
# Generate keys
ssh-keygen -t ed25519 -f ~/.ssh/github-agentwire -N "" -C "do-1-agentwire"
ssh-keygen -t ed25519 -f ~/.ssh/github-claude -N "" -C "do-1-claude"
ssh-keygen -t ed25519 -f ~/.ssh/github-myproject -N "" -C "do-1-myproject"

# SSH config
cat >> ~/.ssh/config << 'EOF'
Host github-agentwire
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-agentwire

Host github-claude
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-claude

Host github-myproject
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-myproject
EOF

chmod 600 ~/.ssh/config
ssh-keyscan github.com >> ~/.ssh/known_hosts

# Print public keys to add to GitHub
echo "=== Add these as deploy keys on GitHub ==="
echo "--- agentwire repo ---"
cat ~/.ssh/github-agentwire.pub
echo "--- .claude repo ---"
cat ~/.ssh/github-claude.pub
echo "--- myproject repo ---"
cat ~/.ssh/github-myproject.pub
```

**On your LOCAL machine**, add deploy keys:
```bash
# Copy each public key and add via gh CLI
gh repo deploy-key add <(echo "ssh-ed25519 AAAA... do-1-agentwire") --repo youruser/agentwire --title "do-1"
gh repo deploy-key add <(echo "ssh-ed25519 AAAA... do-1-claude") --repo youruser/.claude --title "do-1"
gh repo deploy-key add <(echo "ssh-ed25519 AAAA... do-1-myproject") --repo youruser/myproject --title "do-1"
```

### Step 4: Clone Repos and Install AgentWire (Remote)

```bash
ssh do-1

# Projects directory
mkdir -p ~/projects
cd ~/projects

# Clone agentwire
git clone git@github-agentwire:youruser/agentwire.git
cd agentwire

# Install in isolated venv
uv venv ~/.local/share/agentwire-venv
source ~/.local/share/agentwire-venv/bin/activate
uv pip install -e .
deactivate

# Verify
agentwire --help

# Clone .claude config
git clone git@github-claude:youruser/.claude.git ~/.claude

# Clone project repos
git clone git@github-myproject:youruser/myproject.git ~/projects/myproject
```

### Step 5: Authenticate Claude Code (Remote)

**Must be done interactively:**

```bash
ssh do-1
claude
# Follow prompts to authenticate
# Ctrl+C after success
```

### Step 6: Register Machine (Portal Machine)

Add to `~/.agentwire/machines.json` on your **portal machine**:

```json
{
  "machines": [
    {
      "id": "do-1",
      "host": "do-1",
      "projects_dir": "/home/agentwire/projects"
    }
  ]
}
```

Restart portal:
```bash
agentwire portal stop && agentwire portal start
```

### Step 7: Start Reverse Tunnel (Portal Machine)

The portal is behind NAT, so tunnel FROM portal TO remote:

```bash
# Install autossh (one-time)
brew install autossh  # macOS
# sudo apt-get install -y autossh  # Linux

# Start persistent tunnel
autossh -M 0 -f -N -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -R 8765:localhost:8765 do-1
```

**For multiple machines**, add to `~/.local/bin/agentwire-tunnels`:
```bash
#!/bin/bash
MACHINES="do-1 gpu-server"  # space-separated list

for machine in $MACHINES; do
    if ! pgrep -f "autossh.*$machine" > /dev/null; then
        echo "Starting tunnel to $machine..."
        autossh -M 0 -f -N \
            -o "ServerAliveInterval=30" \
            -o "ServerAliveCountMax=3" \
            -R 8765:localhost:8765 \
            "$machine"
    fi
done
echo "All tunnels running"
```

Add to crontab for startup:
```bash
chmod +x ~/.local/bin/agentwire-tunnels
(crontab -l 2>/dev/null; echo "@reboot ~/.local/bin/agentwire-tunnels") | crontab -
```

### Step 8: Configure AgentWire (Remote)

```bash
ssh do-1

mkdir -p ~/.agentwire
cat > ~/.agentwire/config.yaml << 'EOF'
projects:
  dir: "~/projects"

# IMPORTANT: must match id in portal's machines.json
machine:
  id: "do-1"

# Portal accessed via reverse tunnel from portal machine
portal:
  url: "https://localhost:8765"

tts:
  backend: "none"

stt:
  backend: "none"

agent:
  command: "claude --dangerously-skip-permissions"
EOF
```

### Step 9: Install Voice Commands (Remote)

```bash
# remote-say script (reads machine.id from config)
sudo tee /usr/local/bin/remote-say > /dev/null << 'SCRIPT'
#!/bin/bash
TEXT="$1"
SESSION=$(tmux display-message -p '#S' 2>/dev/null || echo "default")
MACHINE=$(grep -A1 "^machine:" "$HOME/.agentwire/config.yaml" | grep "id:" | sed 's/.*id: *"\([^"]*\)".*/\1/')
if [ -n "$MACHINE" ]; then
    ROOM="${SESSION}@${MACHINE}"
else
    ROOM="$SESSION"
fi
[ -z "$TEXT" ] && echo "Usage: remote-say \"message\"" && exit 1
exec "$HOME/.local/share/agentwire-venv/bin/agentwire" say --room "$ROOM" "$TEXT"
SCRIPT

sudo chmod +x /usr/local/bin/remote-say
sudo ln -sf /usr/local/bin/remote-say /usr/local/bin/say
```

### Step 10: Test Everything

**From remote machine:**
```bash
ssh do-1

# Test portal connectivity (via tunnel)
curl -sk https://localhost:8765/api/sessions | head -c 100

# Test voice (with browser open to room)
say "Hello from remote machine"
```

**Checklist:**
- [ ] Portal shows machine in dashboard
- [ ] Can create sessions on remote machine
- [ ] `say` command produces audio in browser

---

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Claude won't run | Authenticate first: `ssh machine && claude` |
| Session not in portal | Restart portal after adding to machines.json |
| Deploy key "already in use" | Each repo needs a unique key per machine |
| `say` command not found | Install to /usr/local/bin (Step 9) |
| `say` no audio | Check browser connected to room, tunnel running |
| `curl localhost:8765` fails | Tunnel not running - start from portal machine |
| Wrong room name | Check `machine.id` in config matches machines.json |

### Minimum Specs

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 1GB | 2GB+ |
| Storage | 10GB | 20GB+ |
| CPU | 1 vCPU | 2+ vCPU |

The LLM runs on Anthropic's servers - local machine just needs RAM for Node.js and file operations.

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
