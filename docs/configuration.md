# Configuration Guide

AgentWire uses a YAML configuration file located at `~/.agentwire/config.yaml`.

## Full Configuration Reference

```yaml
# Server settings
server:
  host: "0.0.0.0"              # Bind address (0.0.0.0 for all interfaces)
  port: 8765                    # HTTPS port
  ssl:
    cert: "~/.agentwire/cert.pem"   # SSL certificate path
    key: "~/.agentwire/key.pem"     # SSL private key path

# Project directory settings
projects:
  dir: "~/projects"             # Base directory for projects
  worktrees:
    enabled: true               # Enable git worktree sessions
    suffix: "-worktrees"        # Worktree directory suffix
    auto_create_branch: true    # Create branch if it doesn't exist

# Text-to-speech settings
tts:
  backend: "chatterbox"         # TTS backend: chatterbox | elevenlabs | none
  url: "http://localhost:8100"  # Chatterbox server URL
  default_voice: "default"      # Default voice name

# Speech-to-text settings
stt:
  url: "http://localhost:8100"  # agentwire-stt server URL (empty = disabled)

# Agent settings
agent:
  command: "claude --dangerously-skip-permissions"
  # Placeholders available:
  #   {name}  - Session name
  #   {path}  - Working directory path
  #   {model} - Model name (if specified in room config)

# Remote machines registry
machines:
  file: "~/.agentwire/machines.json"

# Room configurations (voice, model per room)
rooms:
  file: "~/.agentwire/rooms.json"

# Session templates (pre-configured setups)
templates:
  dir: "~/.agentwire/templates"

# Damage control security (optional)
safety:
  hooks_dir: "~/.agentwire/hooks/damage-control"
  patterns_file: "~/.agentwire/hooks/damage-control/patterns.yaml"
  logs_dir: "~/.agentwire/logs/damage-control"
```

## Environment Variables

Environment variables override config file settings:

| Variable | Description |
|----------|-------------|
| `AGENTWIRE_CONFIG` | Config file path |
| `AGENTWIRE_PORT` | Server port |
| `AGENTWIRE_HOST` | Server bind address |
| `ELEVENLABS_API_KEY` | For ElevenLabs TTS backend |

## SSL Certificates

HTTPS is required for microphone access in browsers. Generate self-signed certs:

```bash
agentwire --generate-certs
```

Or manually with OpenSSL:

```bash
mkdir -p ~/.agentwire
openssl req -x509 -newkey rsa:4096 -keyout ~/.agentwire/key.pem \
  -out ~/.agentwire/cert.pem -days 365 -nodes \
  -subj "/CN=localhost"
```

## Machines Registry

For remote sessions, create `~/.agentwire/machines.json`:

```json
{
  "machines": [
    {
      "id": "gpu-server",
      "host": "192.168.1.100",
      "user": "developer",
      "projects_dir": "/home/developer/projects"
    },
    {
      "id": "devbox",
      "host": "devbox.local",
      "user": "dev"
    }
  ]
}
```

Requirements for remote machines:
- SSH key authentication configured
- tmux installed
- Your AI agent (Claude Code, etc.) installed

## Room Configurations

Room-specific settings are stored in `~/.agentwire/rooms.json`:

```json
{
  "myapp": {
    "voice": "alloy",
    "model": "sonnet",
    "bypass_permissions": true
  },
  "untrusted-lib": {
    "voice": "nova",
    "bypass_permissions": false
  }
}
```

Room config options:
- `voice` - TTS voice for this room
- `model` - AI model (passed to agent command as {model})
- `bypass_permissions` - If true (default), skips permission prompts; if false, shows prompts in portal
- `restricted` - If true, session only allows voice commands (say/AskUserQuestion), denies all other tools
- `machine` - Remote machine ID for this room
- `path` - Custom project path

## Defaults

If no config file exists, AgentWire uses these defaults:

| Setting | Default |
|---------|---------|
| Port | 8765 |
| Host | 0.0.0.0 |
| Projects dir | ~/projects |
| TTS backend | none |
| STT | Disabled (no URL) |
| Agent command | claude |

## Session Templates

Session templates provide pre-configured setups with initial prompts, voice settings, and permission modes.

Templates are stored as YAML files in `~/.agentwire/templates/`:

```yaml
name: feature-impl
description: Implement a feature with planning and tests
voice: bashbunni
initial_prompt: |
  I'm working on {{project_name}} {{branch}}.

  Before implementing anything:
  1. Read relevant docs and code
  2. Understand existing patterns
  3. Create a todo list to track progress

  Ask me what feature to implement.
bypass_permissions: true
restricted: false
```

### Template Variables

Variables are expanded when sessions are created:

| Variable | Description |
|----------|-------------|
| `{{project_name}}` | Session name (e.g., "myapp") |
| `{{branch}}` | Branch name for worktree sessions (e.g., "feature-auth") |
| `{{machine}}` | Machine ID for remote sessions (e.g., "gpu-server") |

### Using Templates

```bash
# Install sample templates
agentwire template install-samples

# List available templates
agentwire template list

# Create session with template
agentwire new -s myproject --template feature-impl

# Create custom template
agentwire template create my-template
```

See README.md for sample template descriptions.

## Damage Control Security

AgentWire includes optional damage-control hooks that protect against dangerous operations across all Claude Code sessions.

### Installation

```bash
agentwire safety install
```

This registers PreToolUse hooks in `~/.claude/settings.json` that intercept Bash, Edit, and Write tool calls before execution.

### Protected Operations

- **300+ dangerous command patterns** - rm -rf, git push --force, cloud platform destructive operations
- **Sensitive file protection** - Zero-access to .env, SSH keys, credentials
- **Read-only paths** - System configs, lock files
- **No-delete paths** - .git/, README.md, mission files

### Usage

```bash
# Test if command would be blocked
agentwire safety check "rm -rf /tmp"

# View recent blocks
agentwire safety status

# Query audit logs
agentwire safety logs --tail 20
```

All security decisions are logged to `~/.agentwire/logs/damage-control/` in JSONL format.

See `docs/security/damage-control.md` for detailed documentation.
