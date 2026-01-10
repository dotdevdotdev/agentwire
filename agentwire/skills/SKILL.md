---
name: agentwire
description: Orchestrate Claude Code sessions across tmux. Use for managing worker sessions - list sessions (/sessions), send prompts (/send), read output (/output), spawn sessions (/spawn), create new sessions (/new), kill sessions (/kill), check status (/status), or get attach instructions (/jump).
---

# AgentWire - Session Orchestration

Orchestrate multiple Claude Code sessions running in tmux, locally or on remote machines.

## Available Commands

### Session Management

| Command | Purpose |
|---------|---------|
| `/spawn <name> [--force]` | Smart create - checks if exists, offers options |
| `/sessions` | List all tmux sessions (local + remote) |
| `/send <session> <prompt>` | Send a prompt to a session |
| `/output <session> [lines]` | Read recent output from a session |
| `/new <name> [path] [@machine]` | Create new Claude Code session (fails if exists) |
| `/kill <session>` | Cleanly destroy a session |
| `/status` | Check all machines and their sessions |
| `/jump <session>` | Get instructions to attach manually |

### Machine Management

| Command | Purpose |
|---------|---------|
| `/machine-setup [id] [ip]` | Interactive wizard for adding a remote machine |
| `/machine-remove [id]` | Interactive wizard for removing a machine |

CLI equivalents:
- `agentwire machine list` - List registered machines
- `agentwire machine add <id>` - Quick add (no wizard)
- `agentwire machine remove <id>` - Remove with cleanup

## Session Naming

- `api` - local session, maps to ~/projects/api
- `ml@devbox-1` - remote session on devbox-1

## Configuration

All config lives in `~/.agentwire/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Main configuration |
| `machines.json` | Remote machine registry |
| `rooms.json` | Per-session settings (voice, model, role) |
| `roles/*.md` | Role context files for Claude sessions |

### machines.json

```json
{
  "machines": [
    {"id": "devbox-1", "host": "devbox-1", "projects_dir": "/home/user/projects"}
  ]
}
```

### rooms.json

```json
{
  "api": {
    "voice": "default",
    "bypass_permissions": true
  },
  "untrusted-lib": {
    "voice": "default",
    "bypass_permissions": false
  }
}
```

## Example Workflow

```
You: /sessions
Claude: Shows all active sessions

You: /spawn api
Claude: Creates tmux session 'api', starts claude in ~/projects/api
        (or shows options if session already exists)

You: /spawn api --force
Claude: Kills existing 'api' session (cleanly), creates fresh one

You: /send api "add rate limiting to auth endpoints"
Claude: Sends prompt to api session

You: /output api
Claude: Shows recent output from api session

You: /status
Claude: Shows all machines online/offline with their sessions
```

## Implementation

Use the `agentwire` CLI commands:

```bash
# List sessions
agentwire list

# Create session (uses --dangerously-skip-permissions automatically)
agentwire new -s <name> [-p path] [-f]
agentwire new -s dotdev.dev              # Creates dotdev_dev session in ~/projects/dotdev.dev
agentwire new -s api -p /path/to/api     # Explicit path
agentwire new -s api -f                  # Replace existing

# Send prompt
agentwire send -s <session> "<prompt>"

# Read output
agentwire output -s <session>
agentwire output -s <session> -n 100

# Kill session (sends /exit first for clean Claude shutdown)
agentwire kill -s <session>
```

**Session Naming:**
- Dots in names become underscores: `dotdev.dev` → session `dotdev_dev`
- Path lookup uses original name: `~/projects/dotdev.dev/`

For remote sessions, wrap commands in SSH:
```bash
ssh <host> "agentwire list"
```

**Important:** `agentwire new` automatically starts Claude with `--dangerously-skip-permissions` for autonomous work.

## Voice Integration

AgentWire integrates TTS for voice responses:

### say Command

In Claude sessions, use `say "message"` to speak to connected clients:

```bash
# Local session - speaks via agentwire portal
say "Task completed successfully"

# Remote session - say routes automatically
say "Task completed on remote machine"
```

### Voice Input Flow

1. User holds push-to-talk on web UI or via hotkey
2. Audio recorded and sent to `/transcribe`
3. Transcription sent to target session via `agentwire send`
4. Claude processes and responds
5. `say "..."` commands detected and streamed as TTS audio

## Notes

- Requires tmux installed locally and on remote machines
- SSH must be configured for passwordless access to remotes
- Requires jq for parsing JSON configs
- 3-second timeout for unresponsive machines
