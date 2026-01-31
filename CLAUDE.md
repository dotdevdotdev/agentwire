# AgentWire

Voice interface for AI coding agents. Push-to-talk from any device to tmux sessions running Claude Code or OpenCode.

**No Backwards Compatibility** - Pre-launch, no customers. Change things completely, no legacy fallbacks.

**Hierarchical Delegation** - Before editing files in OTHER projects (e.g., `~/projects/agentwire-website/`), check `agentwire_sessions_list()`. If a session exists for that project, use `agentwire_session_send()` instead of editing directly. See `~/.claude/rules/delegation.md`.

## Dev Workflow

`uv tool install` caches builds and ignores source changes.

```bash
# During development (picks up changes instantly)
agentwire portal start --dev

# After structural changes (pyproject.toml, new files)
agentwire rebuild
```

## CLI is the Single Source of Truth

**Always use `agentwire` CLI for session management.** The CLI is the authoritative interface - the web portal wraps CLI commands via `run_agentwire_cmd()`.

### Architecture Principle

All session/machine logic lives in CLI commands (`__main__.py`). The portal (`server.py`) is a thin wrapper that:
1. Calls CLI via `run_agentwire_cmd(["command", "args"])`
2. Parses JSON output (`--json` flag)
3. Adds WebSocket/real-time features

**When adding new functionality:**
1. Implement in CLI first with `--json` output
2. Portal calls CLI, doesn't duplicate logic
3. Never bypass CLI with direct tmux/subprocess calls

### CLI Commands

```bash
# Session management
agentwire new -s name           # not: tmux new-session
agentwire send -s name "prompt" # not: tmux send-keys
agentwire send-keys -s name key1 key2  # raw keys with pauses
agentwire output -s name        # not: tmux capture-pane
agentwire info -s name          # session metadata (cwd, panes) as JSON
agentwire kill -s name          # not: tmux kill-session
agentwire list                  # not: tmux list-sessions
agentwire recreate -s name      # destroy and recreate with fresh worktree
agentwire fork -s name          # fork session into new worktree

# Pane commands (for workers within same session)
agentwire spawn --roles worker  # spawn worker pane
agentwire send --pane 1 "task"  # send to pane
agentwire output --pane 1       # read pane output
agentwire kill --pane 1         # kill pane
agentwire jump --pane 1         # focus pane
agentwire split -s name         # add terminal pane(s)
agentwire detach -s name        # move pane to its own session
agentwire resize -s name        # resize window to fit largest client

# Portal management
agentwire portal start          # start in tmux
agentwire portal stop           # stop portal
agentwire portal restart        # stop + start
agentwire portal status         # check health

# TTS/STT servers
agentwire tts start|stop|status # TTS server management
agentwire stt start|stop|status # STT server management

# Voice
agentwire say "text"            # speak (auto-routes to browser or local)
agentwire say -s name "text"    # speak to specific session
agentwire alert "text"          # text notification to parent (no audio)
agentwire alert --to name "text" # text notification to specific session
agentwire listen start|stop     # voice recording

# Voice cloning
agentwire voiceclone start      # start recording voice sample
agentwire voiceclone stop name  # stop and save as voice clone
agentwire voiceclone list       # list available voices
agentwire voiceclone delete name # delete a voice clone

# Email notifications
agentwire email --to addr --subject "Subject" --body "Body"
agentwire email --body "msg" # uses default_to from config
agentwire email --attach file.pdf --body "See attached"

# Machine management
agentwire machine list
agentwire machine add <id> --host <host> --user <user>
agentwire machine remove <id>

# SSH tunnels (for remote services)
agentwire tunnels up            # create all required tunnels
agentwire tunnels down          # tear down all tunnels
agentwire tunnels status        # show tunnel health

# Lock management (for scheduled tasks)
agentwire lock list             # list all locks
agentwire lock clean            # remove stale locks
agentwire lock remove <session> # force-remove a specific lock

# Project discovery
agentwire projects list         # discover projects from projects_dir
agentwire projects list --json  # JSON output for scripting

# Session history
agentwire history list          # list conversation history
agentwire history show <id>     # show session details
agentwire history resume <id>   # resume session (always forks)

# Roles management
agentwire roles list            # list available roles
agentwire roles show <name>     # show role details

# Scheduled workloads
agentwire ensure -s name --task task  # run named task reliably
agentwire task list [session]         # list tasks for session/project
agentwire task show session/task      # show task definition
agentwire task validate session/task  # validate task syntax

# Safety & diagnostics
agentwire safety check "cmd"    # test if command would be blocked
agentwire safety status         # show pattern counts and recent blocks
agentwire safety logs           # query audit logs
agentwire safety install        # install damage control hooks
agentwire hooks install         # install permission hook (Claude Code only)
agentwire hooks uninstall       # remove permission hook (Claude Code only)
agentwire hooks status          # check hook installation status
agentwire network status        # complete network health check
agentwire doctor                # auto-diagnose and fix issues

# Setup & Development
agentwire init                  # interactive setup wizard
agentwire generate-certs        # generate SSL certificates
agentwire dev                   # start/attach to dev session
agentwire rebuild               # clear uv cache and reinstall
agentwire uninstall             # uninstall the tool
```

Session formats: `name`, `project/branch` (worktree), `name@machine` (remote)
Pane targeting: `--pane N` auto-detects session from `$TMUX_PANE`

For CLI details: `agentwire --help` or `agentwire <cmd> --help`

## MCP Server (For Agents)

**Agents running in agentwire sessions should use MCP tools instead of CLI commands.**

The agentwire MCP server provides tools that wrap CLI functionality. Use these instead of `Bash: agentwire <cmd>`:

| CLI Command | MCP Tool |
|-------------|----------|
| `agentwire say "text"` | `agentwire_say(text="...")` |
| `agentwire alert "text"` | `agentwire_alert(text="...")` |
| `agentwire spawn --roles worker` | `agentwire_pane_spawn(roles="worker")` |
| `agentwire send --pane 1 "msg"` | `agentwire_pane_send(pane=1, message="...")` |
| `agentwire send -s name "msg"` | `agentwire_session_send(session="name", message="...")` |
| `agentwire list` | `agentwire_sessions_list()` |
| `agentwire output --pane 1` | `agentwire_pane_output(pane=1)` |
| `agentwire kill --pane 1` | `agentwire_pane_kill(pane=1)` |
| `agentwire ensure -s x --task y` | `agentwire_task_run(session="x", task="y")` |
| `agentwire task list x` | `agentwire_task_list(session="x")` |
| `agentwire task show x/y` | `agentwire_task_show(session="x", task="y")` |

**When to use CLI vs MCP:**
- **MCP tools** - Agents in sessions (orchestrators, workers)
- **CLI commands** - Humans, shell scripts, automation outside of agent sessions

The MCP server runs as part of the portal. All 26 tools are documented via `agentwire roles show leader`.

## Config

All in `~/.agentwire/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Main config (see structure below) |
| `machines.json` | Remote machines registry |
| `voices/` | Custom TTS voice samples |
| `uploads/` | Uploaded images for cross-machine sharing |
| `logs/` | Audit logs for damage-control |

Per-session config (type, roles, voice) lives in `.agentwire.yml` in each project directory.

### config.yaml Structure

```yaml
server:
  host: "0.0.0.0"
  port: 8765
  activity_threshold_seconds: 3  # Seconds before session considered idle
  ssl:
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

projects:
  dir: "~/projects"
  worktrees:
    enabled: true
    suffix: "-worktrees"

tts:
  backend: "runpod"  # runpod | chatterbox | none
  runpod_endpoint_id: "your-endpoint-id"
  runpod_api_key: "your-api-key"
  default_voice: "dotdev"

stt:
  url: "http://localhost:8100"
  timeout: 30

agent:
  command: "claude --dangerously-skip-permissions"  # or "opencode" for OpenCode

dev:
  source_dir: "~/projects/agentwire-dev"  # agentwire source for TTS/STT venv

services:  # Where services run (for multi-machine setups)
  portal:
    machine: null  # null = local
    port: 8765
    session_name: "agentwire-portal"  # tmux session name
  tts:
    machine: "gpu-server"  # or null for local
    port: 8100
    session_name: "agentwire-tts"
  stt:
    session_name: "agentwire-stt"

executables:  # Override executable paths (optional, auto-detected by default)
  ffmpeg: "/opt/homebrew/bin/ffmpeg"
  whisperkit-cli: "/opt/homebrew/bin/whisperkit-cli"
  hs: "/opt/homebrew/bin/hs"
  agentwire: "~/.local/bin/agentwire"

uploads:
  dir: "~/.agentwire/uploads"
  max_size_mb: 10
  cleanup_days: 7

portal:
  url: "https://localhost:8765"

notifications:
  email:
    api_key: ""  # Resend API key (or set RESEND_API_KEY env var)
    from_address: "Echo <echo@yourdomain.com>"
    default_to: "user@example.com"
    # Branding images (hosted publicly)
    banner_image_url: "https://yourdomain.com/images/banner.png"
    echo_image_url: "https://yourdomain.com/images/echo.png"
    echo_small_url: "https://yourdomain.com/images/echo-small.png"
    logo_image_url: "https://yourdomain.com/images/logo.png"
```

### .agentwire.yml (Project Config)

Each project can have a `.agentwire.yml` in its root directory. This configures session type, roles, voice, and parent for that project.

**Format is FLAT (no nesting):**

```yaml
# Leader session (any level of hierarchy)
type: claude-bypass
roles:
  - leader
  - glm-orchestration
voice: may
parent: main  # Notify parent session when idle (optional)
```

```yaml
# WRONG - don't nest under "session:"
session:
  type: claude
  roles: [...]  # This won't be loaded!
```

| Field | Values | Description |
|-------|--------|-------------|
| `type` | `claude-bypass`, `claude-prompted`, `opencode-bypass`, etc. | Session permission level |
| `roles` | List of role names | Roles to load (from bundled or `~/.agentwire/roles/`) |
| `voice` | Voice name | TTS voice for this project |
| `parent` | Session name | Parent session for hierarchical notifications |
| `shell` | `/bin/sh`, `/bin/bash`, etc. | Default shell for task commands |
| `tasks` | Task definitions | Scheduled workload configurations |

### Task Schema

Tasks are defined in `.agentwire.yml` for use with `agentwire ensure`:

```yaml
shell: /bin/sh  # Project-level default shell

tasks:
  morning-briefing:
    shell: /bin/bash           # Task-level override
    retries: 2                 # Retry on failure (default: 0)
    retry_delay: 30            # Seconds between retries (default: 30)
    idle_timeout: 30           # Seconds of idle before completion (default: 30)
    exit_on_complete: true     # Exit session after completion (default: true)
    pre:                       # Data gathering (NO {{ }} - these PRODUCE variables)
      weather: "curl -s wttr.in/?format=3"
      calendar:
        cmd: "gcal-cli today --json"
        required: true         # Fail if empty (default: false)
        validate: "jq . > /dev/null"  # Validation command
        timeout: 30            # Command timeout
    prompt: |                  # Main prompt (supports {{ variables }})
      Weather: {{ weather }}
      Calendar: {{ calendar }}
      Summarize my day.
    on_task_end: |             # Optional: after system summary
      Read {{ summary_file }}.
      If complete, save to ~/briefings/{{ date }}.md
    post:                      # Commands after completion
      - "echo 'Status: {{ status }}'"
    output:
      capture: 50              # Lines to capture
      save: ~/logs/{{ task }}.log
      notify: voice            # voice, alert, webhook ${URL}, command "..."
```

**Built-in variables:**
- `{{ date }}`, `{{ time }}`, `{{ datetime }}` - Current date/time
- `{{ session }}`, `{{ task }}`, `{{ project_root }}` - Task identity
- `{{ attempt }}` - Current attempt number (1-based)
- `{{ status }}`, `{{ summary }}`, `{{ summary_file }}` - After completion
- `{{ output }}` - Captured session output (in post phase)
- `{{ var_name }}` - Pre-command outputs

**Exit codes:** 0=complete, 1=failed, 2=incomplete, 3=lock conflict, 4=pre failure, 5=timeout, 6=session error

### Hierarchical Idle Notifications

When a session goes idle, it notifies up the hierarchy via `agentwire alert` (text-only, no audio):

```
parent leader ← receives "[ALERT from child] ..."
    ↑ alert --to parent
child leader   ← receives "[ALERT from pane N] ..."
    ↑ auto-notify pane 0
worker panes
```

**Worker summary files:**
- Workers write summaries to `.agentwire/worker-{pane}.md` before going idle
- Summaries include: task, status, what worked, what didn't, notes for orchestrator
- Orchestrators read these files to understand worker results

**Auto-exit (workers auto-kill on idle):**
- Worker panes (index > 0) automatically exit when idle
- Use `parent: <session-name>` in `.agentwire.yml` for child → parent notifications

**Queue system files:**
- `~/.agentwire/queue-processor.sh` - Processes queue with 15s delays between alerts
- `~/.agentwire/queues/{session}.jsonl` - Per-session notification queues

**Worker idle sequence:**
1. `session.idle` fires → wait 2s (let agent settle)
2. Worker writes summary to `.agentwire/worker-{pane}.md`
3. Queue notification to `{session}.jsonl`
4. Start queue processor if not running
5. Worker auto-exits

**Both Claude Code and OpenCode** support idle notifications:
- Claude Code: via `~/.claude/hooks/suppress-bg-notifications.sh`
- OpenCode: via `~/.config/opencode/plugin/agentwire-notify.ts`

**Creating a project with roles:**

```bash
# Option 1: Create .agentwire.yml first, then create session
echo "type: claude-bypass
roles:
  - leader" > ~/projects/myproject/.agentwire.yml

agentwire new -s myproject -p ~/projects/myproject

# Option 2: Specify roles on command line (saves to .agentwire.yml)
agentwire new -s myproject -p ~/projects/myproject --roles leader
```

### Role System

Roles define agent behavior and are composable. Mix and match roles in `.agentwire.yml` to configure orchestrators, workers, or specialized agents.

**Role types:**
- **Leader roles** - Orchestrators that spawn workers, use voice, coordinate work
- **Worker roles** - Focused execution, write exit summaries, auto-kill when idle
- **Delegation roles** - Agent-specific worker management (Claude vs GLM patterns)
- **Specialty roles** - Chatbot personality, voice handling, etc.

Use `agentwire roles list` to see available roles. Roles are bundled in `agentwire/roles/` and can reference each other for complementary behavior.

## Agent Parity

**The system works identically for Claude Code and OpenCode.** Both agents can be used for any role (orchestrator, worker) with identical behavior.

### Supported Features

| Feature | Claude Code | OpenCode |
|---------|-------------|----------|
| Idle detection | ✓ | ✓ |
| Output capture (last 20 lines) | ✓ | ✓ |
| Auto-kill worker panes | ✓ | ✓ |
| Queue-based notifications | ✓ | ✓ |
| Session resume | ✓ (`--resume`) | ✓ (`--session`) |

### Hook/Plugin Installation

Both agents need idle notification hooks installed to work with the agentwire system.

**Claude Code** - Install the idle hook:

```bash
# Create hooks directory
mkdir -p ~/.claude/hooks

# Install the hook (copies from agentwire source)
agentwire hooks install

# Verify installation
agentwire doctor
```

The hook lives at `~/.claude/hooks/suppress-bg-notifications.sh` and fires on `idle_prompt` notifications.

**OpenCode** - Install the plugin:

```bash
# Create plugin directory
mkdir -p ~/.config/opencode/plugin

# Copy the plugin from agentwire source
cp ~/projects/agentwire-dev/opencode-plugin/agentwire-notify.ts ~/.config/opencode/plugin/

# Restart OpenCode to load the plugin
```

The plugin lives at `~/.config/opencode/plugin/agentwire-notify.ts` and fires on `session.idle` events.

### Queue Processor

Both hooks use a shared queue processor for notifications:

```bash
# Install the queue processor
mkdir -p ~/.agentwire
cp ~/projects/agentwire-dev/scripts/queue-processor.sh ~/.agentwire/
chmod +x ~/.agentwire/queue-processor.sh
```

The processor sends queued alerts with 15-second gaps to prevent overwhelming orchestrators.

### Diagnosing Issues

```bash
# Check all components are installed
agentwire doctor

# View hook debug logs
tail -f /tmp/claude-hook-debug.log      # Claude Code
tail -f /tmp/opencode-plugin-debug.log  # OpenCode

# View queue processor logs
tail -f /tmp/queue-processor-debug.log
```

## Key Patterns

- **agentwire sessions** coordinate via voice, delegate to workers
- **worker panes** spawn within the orchestrator's session (visible dashboard)
- **Pane 0** = orchestrator, **panes 1+** = workers
- **Damage-control hooks** block dangerous ops (`rm -rf`, `git push --force`, etc.)
- **Smart TTS routing** - audio goes to browser if connected, local speakers if not

### Worker Pane Lifecycle

**Workers auto-kill after sending idle notification.** The OpenCode plugin captures output, sends alert to pane 0, then kills itself.

Manual kill (if needed):
```bash
agentwire kill --pane 1
```

## Desktop UI Patterns

### Session Window Modes

| Mode | Element | Use Case |
|------|---------|----------|
| **Monitor** | `<pre>` with ANSI-to-HTML | Read-only output viewing, polls `tmux capture-pane` |
| **Terminal** | xterm.js | Interactive terminal, attaches via `tmux attach` |

**Important:** Monitor mode must use a simple `<pre>` element, NOT xterm.js. xterm.js requires precise container dimensions for its fit addon to work correctly. Since monitor mode just displays captured text output, a `<pre>` element with `white-space: pre-wrap` and ANSI-to-HTML conversion is simpler and more reliable.

## Docs

- CLI: `agentwire --help` or `agentwire <cmd> --help`
- `docs/PORTAL.md` - Portal modes and API reference
- `docs/security/damage-control.md` - Safety hooks documentation
- `docs/TROUBLESHOOTING.md` - Common issues and solutions
- `docs/SHELL_ESCAPING.md` - Shell escaping guide
- `docs/runpod-tts.md` - RunPod TTS setup
- `docs/tts-self-hosted.md` - Self-hosted TTS
- `docs/remote-machines.md` - Multi-machine orchestration
