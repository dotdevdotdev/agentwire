# AgentWire

> Living document. Update this, don't create new versions.

Multi-room voice web interface for AI coding agents. Push-to-talk voice input from any device to tmux sessions running Claude Code (or any AI coding agent).

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

This is the correct way to update the installed binary. **Do NOT use:**
- `uv tool install . --force` - uses cached wheel, ignores source changes
- `uv tool uninstall && uv tool install .` - also uses cached wheel

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

# Session management
agentwire session list              # List all tmux sessions
agentwire session new <name> [path] # Create Claude Code session
agentwire session new <name> -f     # Replace existing session
agentwire session output <name>     # Read recent session output
agentwire session kill <name>       # Clean shutdown (/exit then kill)
agentwire send <session> "prompt"   # Send prompt to session

# Machine management
agentwire machine list                # List machines with status
agentwire machine add <id> [options]  # Add a machine to portal
agentwire machine remove <id>         # Remove with cleanup

# Skills (Claude Code integration)
agentwire skills install              # Install Claude Code skills
agentwire skills status               # Check installation status
agentwire skills uninstall            # Remove skills

# Development
agentwire dev              # Start orchestrator session (agentwire)
agentwire rebuild          # Clear uv cache and reinstall from source
agentwire uninstall        # Clear uv cache and remove tool
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

## Permission Modes

Sessions run in one of two permission modes:

| Mode | Setting | Claude Command | Behavior |
|------|---------|----------------|----------|
| **Bypass** | `bypass_permissions: true` | `claude --dangerously-skip-permissions` | No prompts, full trust, fast |
| **Normal** | `bypass_permissions: false` | `claude` | Permission prompts via portal |

**Default:** Bypass mode (existing behavior, recommended for trusted projects)

### How It Works

**Bypass sessions** skip all permission checks - Claude acts immediately without asking.

**Normal sessions** use Claude Code's hook system:
1. Claude triggers a permission-requiring action (edit file, run command)
2. `PermissionRequest` hook fires, calling AgentWire's hook script
3. Hook POSTs to `/api/permission/{room}` and blocks waiting for response
4. Portal shows permission modal with action details and diff preview
5. User clicks Allow or Deny
6. Decision returns to hook, Claude proceeds or aborts

### Permission Modal

When a normal session requires permission, the portal shows:
- Tool name and target (e.g., "Edit /src/auth/login.ts")
- Diff preview for file edits
- Allow/Deny buttons
- TTS announcement: "Claude wants to edit login.ts"

The orb state changes to orange/amber (AWAITING PERMISSION).

### Hook System

Normal sessions require the AgentWire permission hook:

**Hook script:** `~/.claude/hooks/agentwire-permission.sh`
**Installed via:** `agentwire skills install`

The hook:
- Reads permission request JSON from stdin
- POSTs to `https://localhost:8765/api/permission/{room}`
- Waits indefinitely for user decision
- Returns `{decision: "allow"}` or `{decision: "deny"}` to Claude

### Room Configuration

Set per-session in `~/.agentwire/rooms.json`:

```json
{
  "my-project": {
    "voice": "bashbunni",
    "bypass_permissions": true
  },
  "untrusted-lib": {
    "voice": "bashbunni",
    "bypass_permissions": false
  }
}
```

**Migration:** Sessions without `bypass_permissions` default to `true` (bypass).

### When to Use Each Mode

| Use Case | Recommended Mode |
|----------|------------------|
| Trusted projects you own | Bypass |
| Rapid development, exploration | Bypass |
| Reviewing unfamiliar code | Normal |
| Running untrusted prompts | Normal |
| Learning/educational use | Normal |

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

```bash
agentwire skills install
```

This creates a symlink from `~/.claude/skills/agentwire` to the installed package skills.

Other skills commands:
- `agentwire skills status` - Check installation status
- `agentwire skills uninstall` - Remove skills
- `agentwire skills install --copy` - Copy files instead of symlinking

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

### Voice Commands (say/remote-say)

Claude (or users) can trigger TTS by running actual shell commands:

```bash
say "Hello world"           # Runs agentwire say → POSTs to /api/say/{room}
remote-say "Task complete"  # Same, but determines room from machine config
```

**How it works:** These are real executables (not pattern matching on terminal output). When Claude runs `say "message"`, it executes the `agentwire say` command which POSTs to the portal API, which broadcasts TTS audio to connected browser clients.

This command-based approach is more reliable than parsing terminal output, which is noisy (typing echoes, ANSI codes, mixed input/output).

TTS audio includes 300ms silence padding to prevent first-syllable cutoff.

### AskUserQuestion Popup

When Claude Code uses the AskUserQuestion tool, the portal displays a modal with clickable options:

- Question text is spoken aloud via TTS when the popup appears
- Click any option to submit the answer
- "Type something" options show a text input with Send button
- Supports multi-line questions

### Actions Menu (Terminal Mode)

In terminal mode, a ⋯ button appears above the mic button. Hover over action buttons to see labels.

**For regular project sessions:**

| Action | Icon | Description |
|--------|------|-------------|
| New Room | ➕ | Creates a sibling session in a new worktree, opens in new tab (parallel work) |
| Fork Session | 🍴 | Forks the Claude Code conversation context into a new session (preserves history) |
| Recreate Session | 🔄 | Destroys current session/worktree, pulls latest, creates fresh worktree and Claude Code session |

**Fork Session** uses Claude Code's `--resume <id> --fork-session` to create a new session that inherits the conversation context. Creates sessions named `project-fork-1`, `project-fork-2`, etc. Useful when you want to try different approaches without losing the current session's progress.

**For system sessions** (`agentwire`, `agentwire-portal`, `agentwire-tts`):

| Action | Icon | Description |
|--------|------|-------------|
| Restart Service | 🔄 | Properly restarts the service (portal schedules delayed restart, TTS stops/starts, orchestrator restarts Claude) |

### Portal API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sessions` | GET | List all tmux sessions |
| `/api/create` | POST | Create new session |
| `/api/room/{name}/config` | POST | Update room config (voice, etc.) |
| `/api/room/{name}/recreate` | POST | Destroy and recreate session with fresh worktree |
| `/api/room/{name}/spawn-sibling` | POST | Create parallel session in new worktree |
| `/api/room/{name}/fork` | POST | Fork Claude Code session (preserves conversation context) |
| `/api/room/{name}/restart-service` | POST | Restart system service (agentwire, portal, TTS) |
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

### Extending with New Capabilities

The pattern for adding new agent-to-client communication:

1. **Create a CLI command** (e.g., `agentwire notify "title" "body"`)
2. **Command POSTs to API** (e.g., `/api/notify/{room}`)
3. **Server broadcasts via WebSocket** to connected clients
4. **Browser handles message type** and renders UI

This command-based approach is more reliable than pattern-matching terminal output because:
- Terminal output is noisy (typing echoes, ANSI codes, mixed I/O)
- Commands are explicit and unambiguous
- Works consistently across local and remote sessions

**Current capabilities using this pattern:**
- `say/remote-say` → TTS audio playback
- `agentwire send` → Send prompts to sessions
- Image uploads → `@/path` references in messages

---

## Remote Machine Management

### Adding a Machine

Use the `/machine-setup` skill for interactive, guided setup:

```
/machine-setup do-2 167.99.123.45
```

The wizard walks through: SSH access, dependencies, GitHub keys, Claude auth, portal registration, tunnels, and voice commands.

**Quick add (portal only, no wizard):**

```bash
agentwire machine add <id> --host <host> --user <user> --projects-dir <path>
```

Or use the Portal UI: Dashboard → Machines → Add Machine.

### Removing a Machine

Use the `/machine-remove` skill for interactive, guided removal:

```
/machine-remove do-1
```

The wizard handles cleanup levels:
1. **Disconnect only** - Just remove from portal
2. **Full cleanup** - Also remove SSH config + GitHub keys
3. **Complete destruction** - Also destroy the VM

**Quick remove (portal-side only):**

```bash
agentwire machine remove <id>
```

This removes from machines.json, kills tunnel, cleans rooms.json, and prints manual step reminders.

Or use Portal UI: Dashboard → Machines → ✕ button.

### Machine CLI Commands

```bash
agentwire machine list                    # List all machines with status
agentwire machine add <id> [options]      # Add a machine
agentwire machine remove <id>             # Remove with cleanup
```

### Minimum Specs (Remote)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 1GB | 2GB+ |
| Storage | 10GB | 20GB+ |
| CPU | 1 vCPU | 2+ vCPU |

The LLM runs on Anthropic's servers - local machine just needs RAM for Node.js and file operations.

---

## Development

### Running During Development

Use `--dev` flag to run from source - code changes are picked up on restart:

```bash
agentwire portal start --dev   # Runs from source via uv run
agentwire portal stop          # Stop portal
agentwire portal start --dev   # Restart with latest code
```

### Installing as CLI Tool

For production/stable use, install as a uv tool:

```bash
cd ~/projects/agentwire
uv tool install .
agentwire --help
```

To update installed binary after code changes:
```bash
uv tool uninstall agentwire-dev && uv tool install .
```

### Test Imports

```bash
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
| `name-fork-N` | `api-fork-1` | Forked session (preserves conversation context) |
| `name@machine` | `ml@gpu-server` | Remote session |
| `name/branch@machine` | `ml/train@gpu-server` | Remote worktree |
