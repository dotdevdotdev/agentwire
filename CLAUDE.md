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

Step-by-step guide for adding a new remote machine to run Claude Code sessions.

### Prerequisites

- SSH access to the machine (initially as root)
- Machine added to `~/.ssh/config` on your local machine
- GitHub deploy keys for private repos

### Step 1: Create Non-Root User

Claude Code refuses to run as root. Create a dedicated user first:

```bash
# SSH in as root initially
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
```

Update your local `~/.ssh/config` to use the new user:

```
Host do-1
    HostName <ip-address>
    User agentwire
    IdentityFile ~/.ssh/<your-key>
```

### Step 2: Install Dependencies

```bash
ssh do-1  # Now connects as agentwire user

# Install system packages (as agentwire with sudo)
sudo apt-get update
sudo apt-get install -y python3 python3-pip tmux git curl jq

# Install Node.js 22.x
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt-get install -y nodejs

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'source ~/.local/bin/env' >> ~/.bashrc
echo 'export COLORTERM=truecolor' >> ~/.bashrc
source ~/.local/bin/env

# Install Claude Code
sudo npm install -g @anthropic-ai/claude-code
```

### Step 3: Setup GitHub SSH Keys

Each private repo needs its own deploy key (GitHub limitation):

```bash
# Generate keys for each repo
ssh-keygen -t ed25519 -f ~/.ssh/github-agentwire -N "" -C "machine-agentwire"
ssh-keygen -t ed25519 -f ~/.ssh/github-claude -N "" -C "machine-claude"
ssh-keygen -t ed25519 -f ~/.ssh/github-<project> -N "" -C "machine-<project>"

# Add to SSH config
cat >> ~/.ssh/config << 'EOF'
Host github-agentwire
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-agentwire

Host github-claude
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-claude

Host github-<project>
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-<project>
EOF

chmod 600 ~/.ssh/config
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

Add each public key as a deploy key on GitHub:
```bash
# From your LOCAL machine with gh CLI
gh repo deploy-key add <(cat pubkey) --repo owner/repo --title "machine-name"
```

### Step 4: Clone Repos and Install

```bash
# Create projects directory
mkdir -p ~/projects

# Clone agentwire (use github-agentwire host alias)
cd ~/projects
git clone git@github-agentwire:user/agentwire.git
cd agentwire

# Install agentwire in isolated environment
uv venv ~/.local/share/agentwire-venv
source ~/.local/share/agentwire-venv/bin/activate
uv pip install -e .
deactivate

# Add to PATH
echo 'export PATH="$HOME/.local/share/agentwire-venv/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
agentwire --help

# Clone .claude config (use host alias for different key)
git clone git@github-claude:user/.claude.git ~/.claude

# Clone project repos (use host alias if needed)
git clone git@github-<project>:user/<project>.git ~/projects/<project>
```

### Step 5: Authenticate Claude Code

**This must be done interactively before sessions will work:**

```bash
ssh do-1
claude
# Follow prompts to authenticate via browser or API key
# Exit with Ctrl+C after authentication succeeds
```

### Step 6: Register Machine Locally

Add to `~/.agentwire/machines.json` on your local machine:

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

Restart the portal to pick up the new machine:
```bash
agentwire portal stop && agentwire portal start
```

### Step 7: Connect to AgentWire Network

Remote machines need access to the portal for voice commands (`remote-say`). Since the portal machine is often behind NAT, use a **reverse tunnel** from the portal machine to the remote machine.

**On the PORTAL machine (your Mac/main machine), run:**
```bash
# One-time tunnel (for testing)
ssh -f -N -R 8765:localhost:8765 do-1

# Persistent tunnel with autossh
brew install autossh  # or apt-get install autossh
autossh -M 0 -f -N -o "ServerAliveInterval=30" -R 8765:localhost:8765 do-1
```

This exposes the portal's port 8765 on the remote machine's localhost:8765.

**For multiple remote machines**, run a tunnel to each:
```bash
autossh -M 0 -f -N -R 8765:localhost:8765 do-1
autossh -M 0 -f -N -R 8765:localhost:8765 gpu-server
# etc.
```

**Create agentwire config (on remote machine):**
```bash
mkdir -p ~/.agentwire
cat > ~/.agentwire/config.yaml << 'EOF'
# Remote machine config - portal accessed via reverse tunnel

projects:
  dir: "~/projects"

# Portal URL - localhost because portal tunnels here
# (default is https://localhost:8765, so this line is optional)
portal:
  url: "https://localhost:8765"

tts:
  backend: "none"  # Portal handles TTS

stt:
  backend: "none"  # Portal handles STT

agent:
  command: "claude --dangerously-skip-permissions"
EOF
```

**Install voice commands:**
```bash
# remote-say - uses agentwire say which reads portal.url from config
# Install to /usr/local/bin so it's in PATH for all shells (including Claude Code)
sudo tee /usr/local/bin/remote-say << 'EOF'
#!/bin/bash
TEXT="$1"
ROOM=$(tmux display-message -p '#S' 2>/dev/null || echo "default")
[ -z "$TEXT" ] && echo "Usage: remote-say \"message\"" && exit 1
exec /home/agentwire/.local/share/agentwire-venv/bin/agentwire say --room "$ROOM" "$TEXT"
EOF
sudo chmod +x /usr/local/bin/remote-say

# say - alias to remote-say (no local audio on servers)
sudo ln -sf /usr/local/bin/remote-say /usr/local/bin/say
```

**Test the connection:**
```bash
# Test portal access (requires tunnel from portal machine)
curl -sk https://localhost:8765/api/sessions | head -c 100

# Test voice
remote-say "Hello from remote machine"
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Claude won't run | Must authenticate first: `ssh machine && claude` |
| Session not in portal | Restart portal after adding machine |
| Deploy key "already in use" | Each repo needs a unique key |
| Permission denied (SSH) | Check user in ~/.ssh/config matches |
| `remote-say` fails | Start reverse tunnel from portal: `ssh -f -N -R 8765:localhost:8765 machine` |
| `curl localhost:8765` fails | Tunnel not running - start it from portal machine |

### Minimum Specs

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 1GB | 2GB+ |
| Storage | 10GB | 20GB+ |
| CPU | 1 vCPU | 2+ vCPU |

A 1GB droplet runs 1-2 Claude sessions comfortably. The LLM runs on Anthropic's servers - local machine just needs RAM for Node.js and file operations.

---

## Portal Machine Setup (After Adding Remote Machines)

After setting up a remote machine, run these commands on the **portal machine** (where agentwire portal runs):

### 1. Install autossh (one-time)

```bash
# macOS
brew install autossh

# Linux
sudo apt-get install -y autossh
```

### 2. Start Tunnel to New Machine

```bash
# Start persistent reverse tunnel (exposes portal on remote's localhost:8765)
autossh -M 0 -f -N -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -R 8765:localhost:8765 <machine-name>
```

### 3. Add to Startup

Create a script to start all tunnels:

```bash
cat > ~/.local/bin/agentwire-tunnels << 'EOF'
#!/bin/bash
# Start reverse tunnels to all remote machines

MACHINES="do-1"  # Add more: "do-1 gpu-server devbox-2"

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
EOF
chmod +x ~/.local/bin/agentwire-tunnels
```

Run on login or via cron:
```bash
# Add to crontab
(crontab -l 2>/dev/null; echo "@reboot ~/.local/bin/agentwire-tunnels") | crontab -
```

### 4. Register Machine

Add to `~/.agentwire/machines.json`:
```json
{
  "machines": [
    {"id": "do-1", "host": "do-1", "projects_dir": "/home/agentwire/projects"}
  ]
}
```

Restart portal to pick up new machine:
```bash
agentwire portal stop && agentwire portal start
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
