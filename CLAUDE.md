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

## CRITICAL: Always Use AgentWire CLI

**Never use raw tmux commands when an agentwire CLI alternative exists.**

The agentwire CLI handles complexity that raw tmux commands miss:
- Worktree creation and management
- Remote session handling via SSH
- Session naming conventions (`project/branch@machine`)
- Room configuration (rooms.json)
- Proper Claude Code startup with correct flags
- Clean shutdown sequences

| Instead of... | Use... |
|---------------|--------|
| `tmux new-session -d -s name` | `agentwire new -s name` |
| `tmux send-keys -t name "text" Enter` | `agentwire send -s name "text"` |
| `tmux capture-pane -t name -p` | `agentwire output -s name` |
| `tmux kill-session -t name` | `agentwire kill -s name` |
| `tmux list-sessions` | `agentwire list` |
| `ssh host "tmux ..."` | `agentwire <cmd> -s name@machine` |
| `git worktree add ...` | `agentwire new -s project/branch` |
| `git worktree remove ...` | `agentwire kill -s project/branch` (or `recreate`) |

**Why this matters:**
- `agentwire new` creates worktrees, sets up rooms.json, starts Claude with correct flags
- `agentwire send` handles the pause-before-enter timing that tmux send-keys misses
- `agentwire kill` sends `/exit` first for clean Claude shutdown, then kills session
- `agentwire list` aggregates sessions from all machines, not just local
- Remote commands (`@machine`) work transparently without manual SSH

---

## What Is AgentWire?

A complete voice-enabled orchestration system for AI coding agents:

- **Web Portal** - Voice rooms with push-to-talk, TTS playback, room locking
- **TTS Server** - Host Chatterbox for voice synthesis
- **CLI Tools** - Manage sessions, speak text, orchestrate agents
- **Skills** - Claude Code skills for session orchestration

## Recent Features

**January 2026:**

| Feature | PR | Description |
|---------|-----|-------------|
| Multiline Input | [#12](https://github.com/dotdevdotdev/agentwire/pull/12) | Auto-expanding textarea with Enter/Shift+Enter support |
| CLI Worktree Support | [#11](https://github.com/dotdevdotdev/agentwire/pull/11) | Complete worktree operations via CLI (new, fork, recreate) |
| Session Activity Status | [#10](https://github.com/dotdevdotdev/agentwire/pull/10) | Real-time active/idle indicators on dashboard |
| Damage Control Hooks | [#9](https://github.com/dotdevdotdev/agentwire/pull/9) | PreToolUse security hooks for parallel agent protection |
| Session Templates | [#8](https://github.com/dotdevdotdev/agentwire/pull/8) | Pre-configured session setups with voice, permissions, initial prompts |

---

## CLI Commands

All session commands support the `session@machine` format for remote operations and `--json` for machine-readable output.

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
agentwire list                              # List sessions from ALL machines
agentwire new -s <name> [-p path] [-f]      # Create Claude Code session
agentwire new -s <name> -t <template>       # Create session with template
agentwire new -s <name> --restricted        # Create restricted mode session
agentwire output -s <session> [-n lines]    # Read recent session output
agentwire kill -s <session>                 # Clean shutdown (/exit then kill)
agentwire send -s <session> "prompt"        # Send prompt + Enter
agentwire send-keys -s <session> "text" Enter  # Send keys with pause between
agentwire recreate -s <name>                # Destroy and recreate with fresh worktree
agentwire fork -s <source> -t <target>      # Fork session (preserves conversation)

# Machine management
agentwire machine list                # List machines with status
agentwire machine add <id> [options]  # Add a machine to portal
agentwire machine remove <id>         # Remove with cleanup

# Session templates
agentwire template list               # List available templates
agentwire template show <name>        # Show template details
agentwire template create <name>      # Create new template interactively
agentwire template delete <name>      # Delete a template
agentwire template install-samples    # Install sample templates

# Safety & Security (Damage Control)
agentwire safety check "command"      # Test if command would be blocked
agentwire safety status               # Show pattern counts and recent blocks
agentwire safety logs --tail 20       # Query audit logs
agentwire safety install              # Install damage control hooks

# Skills (Claude Code integration)
agentwire skills install              # Install Claude Code skills
agentwire skills status               # Check installation status
agentwire skills uninstall            # Remove skills

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

### Session Name Formats

| Format | Example | Description |
|--------|---------|-------------|
| `name` | `api` | Local session in ~/projects/api |
| `project/branch` | `api/feature` | Local worktree session |
| `name@machine` | `ml@gpu-server` | Remote session |
| `project/branch@machine` | `ml/train@gpu-server` | Remote worktree session |
| `name-fork-N` | `api-fork-1` | Forked session (auto-generated by `fork` command) |

### Command Examples

#### List Sessions

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

#### Create Sessions

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

#### Send Prompts

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

#### Read Output

```bash
# Read from local session (last 20 lines)
agentwire output -s api

# Read more lines
agentwire output -s api -n 50

# Read from local worktree session
agentwire output -s api/feature -n 30

# Read from remote session
agentwire output -s ml@gpu-server -n 100

# Read from remote worktree session
agentwire output -s ml/experiment@gpu-server

# JSON output
agentwire output -s api --json
# {"success": true, "session": "api", "output": "...", "lines": 20}
```

#### Kill Sessions

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

#### Recreate Sessions (Fresh Worktree)

```bash
# Recreate local worktree session
# 1. Kills session and removes worktree
# 2. Pulls latest from main branch
# 3. Creates fresh worktree
# 4. Starts new Claude Code session
agentwire recreate -s api/feature

# Recreate remote worktree session
agentwire recreate -s ml/experiment@gpu-server

# JSON output
agentwire recreate -s api/feature --json
# {"success": true, "session": "api/feature", "path": "/Users/dotdev/projects/api-worktrees/feature", "branch": "feature", "recreated": true}
```

#### Fork Sessions (Preserve Conversation)

```bash
# Fork local session (creates api-fork-1)
agentwire fork -s api -t api-fork-1

# Fork local worktree session (creates new worktree)
agentwire fork -s api/feature -t api/experiment

# Fork remote session
agentwire fork -s ml@gpu-server -t ml-fork-1@gpu-server

# Fork remote worktree session
agentwire fork -s ml/train@gpu-server -t ml/test@gpu-server

# JSON output
agentwire fork -s api -t api-fork-1 --json
# {"success": true, "source": "api", "target": "api-fork-1", "forked": true, "path": "/Users/dotdev/projects/api"}
```

### Worktree Session Patterns

When worktrees are enabled (`projects.worktrees.enabled: true`), sessions with `/` in the name trigger worktree creation:

```bash
# Pattern: project/branch creates worktree at ~/projects/{project}-worktrees/{branch}/

# Local worktree
agentwire new -s api/feature
# → Creates: ~/projects/api-worktrees/feature/
# → Branch: feature
# → Session: api/feature

# Remote worktree
agentwire new -s ml/experiment@gpu-server
# → Creates: /home/user/projects/ml-worktrees/experiment/
# → Branch: experiment
# → Session: ml/experiment@gpu-server

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

### JSON Output Examples

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
  "lines": 20
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

---

## Configuration

All config lives in `~/.agentwire/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Main configuration |
| `machines.json` | Remote machine registry |
| `rooms.json` | Per-session settings (voice, role, model) |
| `templates/*.yaml` | Session templates (voice, initial prompt, settings) |
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

## Session Templates

Session templates provide pre-configured settings for common use cases: initial prompts, voice, permission modes, and more.

### Template CLI Commands

```bash
# List available templates
agentwire template list

# Show template details
agentwire template show <name>

# Create a new template (interactive)
agentwire template create <name>

# Install sample templates
agentwire template install-samples

# Delete a template
agentwire template delete <name>
```

### Using Templates

```bash
# Create session with a template
agentwire new -s my-project -t code-review

# Template settings apply:
# - Voice
# - Permission mode (bypass/normal/restricted)
# - Initial prompt (sent after Claude is ready)
```

### Template File Format

Templates are YAML files in `~/.agentwire/templates/`:

```yaml
name: code-review
description: Review code and find bugs
voice: bashbunni
initial_prompt: |
  Review the codebase and provide:
  1. Code quality issues
  2. Potential bugs
  3. Performance improvements

  Start by exploring the project structure.
bypass_permissions: true
restricted: false
```

### Template Variables

Use these in `initial_prompt` - they're expanded when the session starts:

| Variable | Description |
|----------|-------------|
| `{{project_name}}` | Project name from session |
| `{{branch}}` | Git branch (if worktree session) |
| `{{machine}}` | Machine ID (if remote) |

### Sample Templates

Install sample templates with:

```bash
agentwire template install-samples
```

Included samples:
- `code-review` - Review code, find bugs, suggest improvements
- `feature-impl` - Implement features with planning
- `bug-fix` - Systematic bug investigation and fixing
- `voice-assistant` - Voice-only assistant (restricted mode)

---

## Permission Modes

Sessions run in one of three permission modes:

| Mode | Setting | Claude Command | Behavior |
|------|---------|----------------|----------|
| **Bypass** | `bypass_permissions: true` | `claude --dangerously-skip-permissions` | No prompts, full trust, fast |
| **Normal** | `bypass_permissions: false` | `claude` | Permission prompts via portal |
| **Restricted** | `restricted: true` | `claude` | Only say/remote-say/AskUserQuestion allowed, all else auto-denied |

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

**Restricted sessions** auto-handle permissions without user interaction:
1. Claude triggers a permission-requiring action
2. Hook POSTs to `/api/permission/{room}`
3. Portal checks if tool is allowed:
   - `AskUserQuestion` - allowed (no keystroke needed)
   - `Bash` with `say "..."` or `remote-say "..."` - allowed (sends "2" keystroke)
   - Everything else - denied (sends "Escape" keystroke)
4. Returns immediately, no UI popup, no user interaction required

### Permission Modal

When a normal session requires permission, the portal shows:
- Tool name and target (e.g., "Edit /src/auth/login.ts")
- Diff preview for file edits
- Allow/Deny buttons
- TTS announcement: "Claude wants to edit login.ts"

The orb state changes to orange/amber (AWAITING PERMISSION).

### Hook System

Normal and Restricted sessions require the AgentWire permission hook:

**Hook script:** `~/.claude/hooks/agentwire-permission.sh`
**Installed via:** `agentwire skills install`

The hook:
- Reads permission request JSON from stdin
- Gets portal URL from: `AGENTWIRE_URL` env var → `~/.agentwire/portal_url` file → `https://localhost:8765`
- POSTs to `{portal_url}/api/permission/{room}`
- Waits indefinitely for user decision (Normal) or returns immediately (Restricted)
- Returns `{decision: "allow"}` or `{decision: "deny"}` to Claude

**Remote machines:** Must configure `~/.agentwire/portal_url` with the portal host's URL:
```bash
echo "https://192.168.1.100:8765" > ~/.agentwire/portal_url
```

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
  },
  "voice-only-agent": {
    "voice": "bashbunni",
    "restricted": true
  }
}
```

**Migration:** Sessions without `bypass_permissions` default to `true` (bypass). Sessions without `restricted` default to `false`.

### When to Use Each Mode

| Use Case | Recommended Mode |
|----------|------------------|
| Trusted projects you own | Bypass |
| Rapid development, exploration | Bypass |
| Reviewing unfamiliar code | Normal |
| Running untrusted prompts | Normal |
| Learning/educational use | Normal |
| Voice-only agent (no code changes) | Restricted |
| Public demo or kiosk | Restricted |
| Sandboxed experimentation | Restricted |

---

## Safety & Security (Damage Control)

AgentWire integrates damage-control security hooks that protect against dangerous operations across all Claude Code sessions.

### What's Protected

**300+ Dangerous Command Patterns:**
- **Destructive file operations:** `rm -rf`, `shred`, `truncate`, `dd`
- **Git operations:** `git reset --hard`, `git push --force`, `git stash clear`
- **Cloud platforms:** AWS, GCP, Firebase, Vercel, Netlify, Cloudflare resource deletion
- **Databases:** SQL DROP/TRUNCATE, Redis FLUSHALL, MongoDB dropDatabase
- **Containers:** Docker/Kubernetes destructive operations
- **Infrastructure:** Terraform destroy, Pulumi destroy, CloudFormation delete

**Three-Tier Path Protection:**

| Protection Level | Operations | Examples |
|------------------|------------|----------|
| **Zero-Access** | None allowed (read/write/edit/delete) | `.env`, `.env.*`, `~/.ssh/`, `*.pem`, `*-credentials.json`, API tokens |
| **Read-Only** | Read allowed, modifications blocked | `/etc/`, system configs, lock files |
| **No-Delete** | Read/write/edit allowed, delete blocked | `.git/`, `README.md`, `.agentwire/mission.md` |

**AgentWire-Specific Protections:**
- `~/.agentwire/credentials/`, `~/.agentwire/api-keys/`, `~/.agentwire/secrets/` (zero-access)
- `~/.agentwire/sessions/`, `~/.agentwire/missions/` (no-delete)
- `tmux kill-server`, `tmux kill-session -t agentwire-*` (blocked)
- `rm -rf ~/.agentwire/` (blocked)

### CLI Commands

```bash
# Test if command would be blocked (dry-run)
agentwire safety check "rm -rf /tmp"
# → ✗ Decision: BLOCK
#   Reason: rm with recursive or force flags

# Show system status
agentwire safety status
# → Shows pattern counts, recent blocks, audit log location

# Query audit logs
agentwire safety logs --tail 20
# → Shows recent blocked/allowed operations with timestamps

# Install hooks (first time setup)
agentwire safety install
```

### How It Works

**PreToolUse Hooks** intercept Bash, Edit, and Write operations before execution:

1. Claude attempts operation (e.g., `rm -rf /tmp/test`)
2. Hook script runs (`~/.agentwire/hooks/damage-control/bash-tool-damage-control.py`)
3. Pattern matching against `patterns.yaml`
4. Decision made:
   - **Block** → Operation prevented, security message shown
   - **Allow** → Operation proceeds
   - **Ask** → User confirmation required (for risky but valid operations)
5. Decision logged to `~/.agentwire/logs/damage-control/YYYY-MM-DD.jsonl`

**Audit Logging:** All security decisions are logged with:
- Timestamp
- Session ID
- Tool (Bash/Edit/Write)
- Command/path
- Decision (blocked/allowed/asked)
- Pattern matched
- User approval (if asked)

### Hook Registration

Hooks are registered in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "uv run ~/.agentwire/hooks/damage-control/bash-tool-damage-control.py",
          "timeout": 5
        }]
      },
      {
        "matcher": "Edit",
        "hooks": [{
          "type": "command",
          "command": "uv run ~/.agentwire/hooks/damage-control/edit-tool-damage-control.py",
          "timeout": 5
        }]
      },
      {
        "matcher": "Write",
        "hooks": [{
          "type": "command",
          "command": "uv run ~/.agentwire/hooks/damage-control/write-tool-damage-control.py",
          "timeout": 5
        }]
      }
    ]
  }
}
```

### Customizing Patterns

Edit `~/.agentwire/hooks/damage-control/patterns.yaml` to customize:

```yaml
bashToolPatterns:
  - pattern: '\brm\s+-[rRf]'
    reason: rm with recursive or force flags

  - pattern: '\bgit\s+push\s+.*--force(?!-with-lease)'
    reason: git push --force (use --force-with-lease)

zeroAccessPaths:
  - ".env"
  - ".env.*"
  - "~/.ssh/"
  - "*.pem"
  - "*-credentials.json"

readOnlyPaths:
  - "/etc/"
  - "*.lock"

noDeletePaths:
  - ".git/"
  - "README.md"
```

### Testing Hooks

Interactive test tool:

```bash
cd ~/.agentwire/hooks/damage-control
uv run test-damage-control.py -i

# Test specific commands
uv run test-damage-control.py bash "rm -rf /" --expect-blocked
```

### Documentation

- **Integration Guide:** `docs/security/damage-control.md`
- **Migration Guide:** `docs/security/damage-control-migration.md`
- **Source Patterns:** `~/.agentwire/hooks/damage-control/patterns.yaml`

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

### Multiline Text Input

The text input area supports multiline messages with auto-resize:

| Action | Result |
|--------|--------|
| Type text | Textarea auto-expands as content grows |
| **Enter** | Submits the message |
| **Shift+Enter** | Adds a newline (for multi-paragraph messages) |
| Clear text | Textarea collapses back to single line |

The textarea starts as a single line and dynamically expands up to 10 lines before scrolling. This provides a natural typing experience for both quick single-line messages and longer multi-paragraph prompts.

### Voice Commands (say/remote-say)

Claude (or users) can trigger TTS by running actual shell commands:

```bash
say "Hello world"           # Local: plays via system audio
remote-say "Task complete"  # Remote: POSTs to portal, streams to browser
```

**How it works:** These are real executables (not pattern matching on terminal output).

- `say` - Uses `agentwire say` to generate TTS locally and play via system speakers
- `remote-say` - POSTs to portal API, broadcasts TTS audio to connected browser clients

**Room detection for remote-say:**
1. Uses `AGENTWIRE_ROOM` env var (set automatically when session is created)
2. Falls back to tmux session name if not set
3. For remote sessions, `AGENTWIRE_ROOM` includes `@machine` suffix (e.g., `myproject@dotdev-pc`)

**Portal URL for remote machines:** `remote-say` reads the portal URL from `~/.agentwire/portal_url`.

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

### Create Session Form

The dashboard's Create Session form supports machine selection, input validation, git detection, and worktree creation:

| Field | Description |
|-------|-------------|
| Session Name | Project name (blocks `@ / \ : * ? " < > |` and spaces) |
| Machine | Dropdown: Local or any configured remote machine |
| Project Path | Auto-fills to `{projectsDir}/{sessionName}` (editable) |
| Voice | TTS voice for the room |
| Permission Mode | Bypass (recommended) or Normal (prompted) |

**Git Repository Detection:**
When the project path points to a git repo, additional options appear:
- Current branch indicator (e.g., "on main")
- **Create worktree** checkbox (checked by default)
- **Branch Name** input with auto-suggested unique name (e.g., `jan-3-2026--1`)

**Smart Defaults:**
- Session name auto-fills path: typing `api` → `~/projects/api`
- Machine selection updates path placeholder to remote's `projects_dir`
- Branch names auto-increment to avoid conflicts
- Last selected machine is remembered in localStorage

**Session Name Derivation:**

| Machine | Worktree | CLI Session Name |
|---------|----------|------------------|
| local | no | `myapp` |
| local | yes | `myapp/jan-3-2026--1` |
| gpu-server | no | `myapp@gpu-server` |
| gpu-server | yes | `myapp/jan-3-2026--1@gpu-server` |

### Portal API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sessions` | GET | List all tmux sessions |
| `/api/create` | POST | Create new session (accepts machine, worktree, branch) |
| `/api/check-path` | GET | Check if path exists and is git repo |
| `/api/check-branches` | GET | Get existing branches matching prefix |
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

## Network Architecture

AgentWire services can run on different machines. The **service topology** concept lets you specify where each service runs (portal, TTS), with SSH tunnels providing connectivity between them.

### Service Topology

| Service | Purpose | Typical Location |
|---------|---------|------------------|
| Portal | Web UI, WebSocket server, session management | Local machine (laptop/desktop) |
| TTS | Voice synthesis (Chatterbox) | GPU machine (requires CUDA) |
| STT | Voice transcription | Local machine |
| Sessions | Claude Code instances | Local or remote machines |

**Single-machine setup:** Portal and TTS run locally. No tunnels needed.

**Multi-machine setup:** TTS runs on GPU server, portal runs locally. Tunnel forwards localhost:8100 to gpu-server:8100.

### Configuration: services Section

Add `services` to `~/.agentwire/config.yaml` to define where services run:

```yaml
services:
  # Portal runs locally (default)
  portal:
    machine: null    # null = local
    port: 8765
    health_endpoint: "/health"

  # TTS runs on GPU server
  tts:
    machine: "gpu-server"  # Must exist in machines.json
    port: 8100
    health_endpoint: "/health"
```

**machine field:**
- `null` = service runs on this machine
- `"machine-id"` = service runs on a machine from machines.json

### SSH Tunnels

When a service is configured to run on a remote machine, you need an SSH tunnel to reach it from your local machine.

```bash
# Tunnel management
agentwire tunnels up       # Create all required tunnels
agentwire tunnels down     # Tear down all tunnels
agentwire tunnels status   # Show tunnel health
agentwire tunnels check    # Verify with health checks
```

**How tunnels work:**

1. Config says `services.tts.machine: "gpu-server"`
2. AgentWire calculates: need tunnel from localhost:8100 to gpu-server:8100
3. `agentwire tunnels up` creates: `ssh -L 8100:localhost:8100 -N -f user@gpu-server`
4. Local code can now use `http://localhost:8100` to reach TTS on gpu-server

**Tunnel state** is stored in `~/.agentwire/tunnels/` (PID files for process tracking).

### Network Commands

```bash
# Show complete network health at a glance
agentwire network status

# Auto-diagnose and fix common issues
agentwire doctor              # Interactive - asks before fixing
agentwire doctor --yes        # Auto-fix everything
agentwire doctor --dry-run    # Show what would be fixed
```

### Troubleshooting Guide

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| TTS not responding | Tunnel not running | `agentwire tunnels up` |
| Tunnel fails to create | SSH key not configured | Check `ssh gpu-server` works |
| Port already in use | Stale tunnel or other process | `lsof -i :8100` to find process |
| Machine not found | Not in machines.json | `agentwire machine add gpu-server --host <ip>` |
| Service responding on wrong port | Port mismatch in config | Check `services.tts.port` matches TTS server |

**Quick diagnostics:**

```bash
# Full diagnostic with auto-fix
agentwire doctor

# Check specific components
agentwire tunnels status    # Are tunnels up?
agentwire network status    # Overall health
agentwire config validate   # Config file issues
```

**Common issues:**

1. **"Connection refused" to TTS:**
   ```bash
   # Check if tunnel exists
   agentwire tunnels status

   # Create missing tunnels
   agentwire tunnels up

   # Verify TTS is running on remote
   ssh gpu-server "curl http://localhost:8100/health"
   ```

2. **Tunnel created but service still unreachable:**
   ```bash
   # Check if port is actually listening locally
   lsof -i :8100

   # Test health endpoint
   curl -k https://localhost:8100/health
   ```

3. **SSH timeout when creating tunnel:**
   ```bash
   # Verify SSH connectivity
   ssh -o ConnectTimeout=5 gpu-server echo ok

   # Check machine config
   agentwire machine list
   ```

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

