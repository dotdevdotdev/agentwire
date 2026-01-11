# AgentWire CLI Reference

> Complete CLI command reference. For project overview, see [CLAUDE.md](../CLAUDE.md).

All session commands support the `session@machine` format for remote operations and `--json` for machine-readable output.

```bash
# Initialize configuration
agentwire init                    # Interactive setup wizard
agentwire init --quick            # Skip orchestrator setup at end

# Portal (web server)
agentwire portal start            # Start in tmux (agentwire-portal)
agentwire portal start --dev      # Run from source (picks up code changes)
agentwire portal start --port 8765 --host 0.0.0.0  # Override defaults
agentwire portal start --no-tts   # Disable TTS
agentwire portal start --no-stt   # Disable STT
agentwire portal start --config path/to/config.yaml
agentwire portal serve            # Run in foreground (for debugging)
agentwire portal stop             # Stop the portal
agentwire portal status           # Check if running

# TTS Server
agentwire tts start               # Start Chatterbox in tmux (agentwire-tts)
agentwire tts start --port 8100 --host 0.0.0.0  # Override defaults
agentwire tts serve               # Run in foreground (for debugging)
agentwire tts stop                # Stop TTS server
agentwire tts status              # Check TTS status

# Voice (smart routing: browser if connected, local if not)
agentwire say "Hello"                  # Auto-detect room from env/tmux
agentwire say "Hello" -v voice         # Specify voice
agentwire say "Hello" -r room          # Specify room explicitly
agentwire say "Hello" --exaggeration 0.5  # Voice exaggeration (0-1)
agentwire say "Hello" --cfg 0.5        # CFG weight (0-1)

# Voice input (push-to-talk recording)
agentwire listen                       # Toggle recording (start/stop)
agentwire listen -s <session>          # Set target session
agentwire listen --no-prompt           # Don't prepend voice prompt hint
agentwire listen start                 # Start recording
agentwire listen stop                  # Stop and send to session
agentwire listen stop -s <session>     # Stop and send to specific session
agentwire listen stop --no-prompt      # Stop without prompt hint
agentwire listen cancel                # Cancel recording

# Voice cloning
agentwire voiceclone start        # Start recording voice sample
agentwire voiceclone stop <name>  # Stop and upload as voice clone
agentwire voiceclone cancel       # Cancel current recording
agentwire voiceclone list         # List available voices
agentwire voiceclone delete <name>  # Delete a voice clone

# Session management
agentwire list                              # List sessions from ALL machines
agentwire list --local                      # List only local sessions
agentwire list --json                       # JSON output
agentwire new -s <name> [-p path] [-f]      # Create Claude Code session
agentwire new -s <name> -t <template>       # Create session with template
agentwire new -s <name> --no-bypass         # Normal mode (permission prompts)
agentwire new -s <name> --restricted        # Restricted mode (voice-only)
agentwire new -s <name> --worker            # Worker session (autonomous)
agentwire new -s <name> --orchestrator      # Orchestrator session (voice-first)
agentwire new -s <name> --json              # JSON output
agentwire output -s <session> [-n lines]    # Read recent session output
agentwire kill -s <session>                 # Clean shutdown (/exit then kill)
agentwire send -s <session> "prompt"        # Send prompt + Enter
agentwire send-keys -s <session> "text" Enter  # Send keys with pause between
agentwire recreate -s <name>                # Destroy and recreate with fresh worktree
agentwire recreate -s <name> --no-bypass    # Recreate in normal mode
agentwire recreate -s <name> --restricted   # Recreate in restricted mode
agentwire fork -s <source> -t <target>      # Fork session (preserves conversation)
agentwire fork -s <source> -t <target> --no-bypass    # Fork in normal mode
agentwire fork -s <source> -t <target> --restricted   # Fork in restricted mode

# Machine management
agentwire machine list                      # List machines with status
agentwire machine add <id>                  # Add machine (interactive)
agentwire machine add <id> --host <host>    # SSH host (defaults to id)
agentwire machine add <id> --user <user>    # SSH user
agentwire machine add <id> --projects-dir ~/projects  # Remote projects dir
agentwire machine remove <id>               # Remove with cleanup

# Session templates
agentwire template list                     # List available templates
agentwire template list --json              # JSON output
agentwire template show <name>              # Show template details
agentwire template show <name> --json       # JSON output
agentwire template create <name>            # Create new template (interactive)
agentwire template create <name> --description "desc"  # Set description
agentwire template create <name> --voice bashbunni     # Set voice
agentwire template create <name> --role orchestrator   # Set role file
agentwire template create <name> --project ~/projects/foo  # Default path
agentwire template create <name> --prompt "initial prompt"  # Initial prompt
agentwire template create <name> --no-bypass   # Use normal permission mode
agentwire template create <name> --restricted  # Use restricted mode
agentwire template create <name> -f            # Overwrite existing
agentwire template create <name> --json        # Non-interactive mode
agentwire template delete <name>            # Delete a template
agentwire template delete <name> -f         # Skip confirmation
agentwire template delete <name> --json     # JSON output
agentwire template install-samples          # Install sample templates
agentwire template install-samples -f       # Overwrite existing
agentwire template install-samples --json   # JSON output

# Safety & Security (Damage Control)
agentwire safety check "command"            # Test if command would be blocked
agentwire safety check "command" -v         # Verbose output
agentwire safety status                     # Show pattern counts and recent blocks
agentwire safety logs                       # Query audit logs
agentwire safety logs --tail 20             # Show last N entries
agentwire safety logs -s <session>          # Filter by session
agentwire safety logs --today               # Show only today's logs
agentwire safety logs -p "pattern"          # Filter by pattern (regex)
agentwire safety install                    # Install damage control hooks

# Skills (Claude Code integration)
agentwire skills install                    # Install Claude Code skills
agentwire skills install -f                 # Overwrite existing
agentwire skills install --copy             # Copy files instead of symlink
agentwire skills status                     # Check installation status
agentwire skills uninstall                  # Remove skills

# Network & Tunnels
agentwire network status              # Show complete network health
agentwire tunnels up                  # Create all required SSH tunnels
agentwire tunnels down                # Tear down all tunnels
agentwire tunnels status              # Show tunnel health
agentwire tunnels check               # Verify tunnels with health checks
agentwire doctor                      # Auto-diagnose and fix common issues
agentwire doctor --yes                # Auto-fix without prompting
agentwire doctor --dry-run            # Show what would be fixed

# Development
agentwire dev              # Start orchestrator session (agentwire)
agentwire rebuild          # Clear uv cache and reinstall from source
agentwire uninstall        # Clear uv cache and remove tool
agentwire generate-certs   # Generate SSL certificates
```

## Session Name Formats

| Format | Example | Description |
|--------|---------|-------------|
| `name` | `api` | Local session in ~/projects/api |
| `project/branch` | `api/feature` | Local worktree session |
| `name@machine` | `ml@gpu-server` | Remote session |
| `project/branch@machine` | `ml/train@gpu-server` | Remote worktree session |
| `name-fork-N` | `api-fork-1` | Forked session (auto-generated by `fork` command) |

## Command Details

### Portal Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Custom config file path |
| `--port PORT` | Override server port (default: 8765) |
| `--host HOST` | Override server host (default: 0.0.0.0) |
| `--no-tts` | Disable TTS functionality |
| `--no-stt` | Disable STT functionality |
| `--dev` | Run from source using `uv run` (picks up code changes) |

### TTS Options

| Option | Description |
|--------|-------------|
| `--port PORT` | Server port (default: 8100) |
| `--host HOST` | Server host (default: 0.0.0.0) |

### Say Options

| Option | Description |
|--------|-------------|
| `-v, --voice NAME` | Voice name for TTS |
| `-r, --room NAME` | Room name (auto-detected from env/tmux) |
| `--exaggeration FLOAT` | Voice exaggeration 0-1 (default: varies by voice) |
| `--cfg FLOAT` | CFG weight 0-1 (default: varies by voice) |

### Machine Add Options

| Option | Description |
|--------|-------------|
| `--host HOST` | SSH host (defaults to machine_id) |
| `--user USER` | SSH user |
| `--projects-dir PATH` | Projects directory on remote machine |

### Template Create Options

| Option | Description |
|--------|-------------|
| `--description TEXT` | Template description |
| `--voice NAME` | TTS voice |
| `--role NAME` | Role file name (from ~/.agentwire/roles/) |
| `--project PATH` | Default project path |
| `--prompt TEXT` | Initial prompt text |
| `--no-bypass` | Use normal permission mode |
| `--restricted` | Use restricted mode |
| `-f, --force` | Overwrite existing template |
| `--json` | Non-interactive JSON mode |

### Safety Logs Options

| Option | Description |
|--------|-------------|
| `--tail, -n N` | Show last N entries |
| `--session, -s ID` | Filter by session ID |
| `--today` | Show only today's logs |
| `--pattern, -p REGEX` | Filter by pattern (regex or substring) |

## Command Examples

### List Sessions

```bash
# List all sessions (local + all machines)
agentwire list

# Output:
# LOCAL:
#   api: 1 window (~/projects/api)
#   auth/feature: 1 window (~/projects/auth-worktrees/feature)
#
# dotdev-pc:
#   ml: 1 window (~/projects/ml)
#   training: 1 window (~/projects/training)

# JSON output
agentwire list --json
# {"local": [{"name": "api", "windows": 1, "path": "/Users/dotdev/projects/api"}], "machines": {"dotdev-pc": [...]}}
```

### Create Sessions

```bash
# Local session (standard project)
agentwire new -s api

# Local worktree session
agentwire new -s api/feature

# Remote session
agentwire new -s ml@gpu-server

# Remote worktree session
agentwire new -s ml/experiment@gpu-server

# With custom path
agentwire new -s api -p ~/custom/path

# With template
agentwire new -s api -t code-review

# Restricted mode (voice-only)
agentwire new -s assistant --restricted

# JSON output
agentwire new -s api/feature --json
# {"success": true, "session": "api/feature", "path": "/Users/dotdev/projects/api-worktrees/feature", "branch": "feature", "machine": null}

agentwire new -s ml@gpu-server --json
# {"success": true, "session": "ml@gpu-server", "path": "/home/user/projects/ml", "branch": null, "machine": "gpu-server"}
```

### Send Prompts

```bash
# Send to local session
agentwire send -s api "run the tests"

# Send to local worktree session
agentwire send -s api/feature "check the build"

# Send to remote session
agentwire send -s ml@gpu-server "start training"

# Send to remote worktree session
agentwire send -s ml/experiment@gpu-server "analyze results"

# JSON output
agentwire send -s api "run tests" --json
# {"success": true, "session": "api", "message": "Prompt sent"}
```

### Read Output

```bash
# Read from local session (last 50 lines by default)
agentwire output -s api

# Read more lines
agentwire output -s api -n 100

# Read from local worktree session
agentwire output -s api/feature -n 30

# Read from remote session
agentwire output -s ml@gpu-server -n 100

# Read from remote worktree session
agentwire output -s ml/experiment@gpu-server

# JSON output
agentwire output -s api --json
# {"success": true, "session": "api", "output": "...", "lines": 50}
```

### Kill Sessions

```bash
# Kill local session
agentwire kill -s api

# Kill local worktree session (also removes worktree)
agentwire kill -s api/feature

# Kill remote session
agentwire kill -s ml@gpu-server

# Kill remote worktree session (removes remote worktree)
agentwire kill -s ml/experiment@gpu-server

# JSON output
agentwire kill -s api --json
# {"success": true, "session": "api", "message": "Session killed"}
```

### Recreate Sessions (Fresh Worktree)

```bash
# Recreate local worktree session
# 1. Kills session and removes worktree
# 2. Pulls latest from main branch
# 3. Creates fresh worktree
# 4. Starts new Claude Code session
agentwire recreate -s api/feature

# Recreate in restricted mode
agentwire recreate -s api/feature --restricted

# Recreate remote worktree session
agentwire recreate -s ml/experiment@gpu-server

# JSON output
agentwire recreate -s api/feature --json
# {"success": true, "session": "api/feature", "path": "/Users/dotdev/projects/api-worktrees/feature", "branch": "feature", "recreated": true}
```

### Fork Sessions (Preserve Conversation)

```bash
# Fork local session (creates api-fork-1)
agentwire fork -s api -t api-fork-1

# Fork local worktree session (creates new worktree)
agentwire fork -s api/feature -t api/experiment

# Fork in restricted mode
agentwire fork -s api -t api-fork-1 --restricted

# Fork remote session
agentwire fork -s ml@gpu-server -t ml-fork-1@gpu-server

# Fork remote worktree session
agentwire fork -s ml/train@gpu-server -t ml/test@gpu-server

# JSON output
agentwire fork -s api -t api-fork-1 --json
# {"success": true, "source": "api", "target": "api-fork-1", "forked": true, "path": "/Users/dotdev/projects/api"}
```

## Worktree Session Patterns

When worktrees are enabled (`projects.worktrees.enabled: true`), sessions with `/` in the name trigger worktree creation:

```bash
# Pattern: project/branch creates worktree at ~/projects/{project}-worktrees/{branch}/

# Local worktree
agentwire new -s api/feature
# -> Creates: ~/projects/api-worktrees/feature/
# -> Branch: feature
# -> Session: api/feature

# Remote worktree
agentwire new -s ml/experiment@gpu-server
# -> Creates: /home/user/projects/ml-worktrees/experiment/
# -> Branch: experiment
# -> Session: ml/experiment@gpu-server

# Recreate pattern (fresh start)
agentwire recreate -s api/feature
# 1. Kill session + remove worktree
# 2. Pull latest main
# 3. Create fresh worktree from main
# 4. Start new session

# Fork pattern (preserve context)
agentwire fork -s api/feature -t api/experiment
# 1. Create new worktree (api/experiment)
# 2. Fork Claude conversation context
# 3. New session can continue from where original left off
```

## JSON Output Examples

All commands support `--json` for machine-readable output. Examples:

```bash
# List sessions
agentwire list --json
{
  "local": [
    {"name": "api", "windows": 1, "path": "/Users/dotdev/projects/api"},
    {"name": "api/feature", "windows": 1, "path": "/Users/dotdev/projects/api-worktrees/feature"}
  ],
  "machines": {
    "dotdev-pc": [
      {"name": "ml", "windows": 1, "path": "/home/user/projects/ml"}
    ],
    "gpu-server": [
      {"name": "training", "windows": 1, "path": "/home/user/projects/training"}
    ]
  }
}

# Create session
agentwire new -s api/feature --json
{
  "success": true,
  "session": "api/feature",
  "path": "/Users/dotdev/projects/api-worktrees/feature",
  "branch": "feature",
  "machine": null
}

# Create remote session
agentwire new -s ml@gpu-server --json
{
  "success": true,
  "session": "ml@gpu-server",
  "path": "/home/user/projects/ml",
  "branch": null,
  "machine": "gpu-server"
}

# Send prompt
agentwire send -s api "run tests" --json
{
  "success": true,
  "session": "api",
  "message": "Prompt sent"
}

# Read output
agentwire output -s api --json
{
  "success": true,
  "session": "api",
  "output": "...",
  "lines": 50
}

# Kill session
agentwire kill -s api/feature --json
{
  "success": true,
  "session": "api/feature",
  "message": "Session killed, worktree removed"
}

# Recreate session
agentwire recreate -s api/feature --json
{
  "success": true,
  "session": "api/feature",
  "path": "/Users/dotdev/projects/api-worktrees/feature",
  "branch": "feature",
  "recreated": true
}

# Fork session
agentwire fork -s api -t api-fork-1 --json
{
  "success": true,
  "source": "api",
  "target": "api-fork-1",
  "forked": true,
  "path": "/Users/dotdev/projects/api"
}
```
