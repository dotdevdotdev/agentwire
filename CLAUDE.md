# AgentWire

Voice interface for AI coding agents. Push-to-talk from any device to tmux sessions running Claude Code or OpenCode.

**No Backwards Compatibility** - Pre-launch, no customers. Change things completely, no legacy fallbacks.

**Hierarchical Delegation** - Before editing files in OTHER projects (e.g., `~/projects/agentwire-website/`), check `agentwire list`. If a session exists for that project, send instructions there instead of editing directly. See `~/.claude/rules/delegation.md`.

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

# Machine management
agentwire machine list
agentwire machine add <id> --host <host> --user <user>
agentwire machine remove <id>

# SSH tunnels (for remote services)
agentwire tunnels up            # create all required tunnels
agentwire tunnels down          # tear down all tunnels
agentwire tunnels status        # show tunnel health

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
```

### .agentwire.yml (Project Config)

Each project can have a `.agentwire.yml` in its root directory. This configures session type, roles, voice, and parent for that project.

**Format is FLAT (no nesting):**

```yaml
# Voice-orchestrator session (project level)
type: claude-bypass
roles:
  - voice-orchestrator
  - glm-orchestration
voice: worker3
parent: agentwire  # Notify main orchestrator when idle
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

### Hierarchical Idle Notifications

When a session goes idle, it notifies up the hierarchy via `agentwire alert` (text-only, no audio):

```
agentwire (main orchestrator) ← receives "[ALERT from project] ..."
    ↑ alert --to agentwire
voice-orch (project session)  ← receives "[ALERT from session pane N] ..."
    ↑ auto-notify pane 0
worker panes
```

**Auto-notification (queued to prevent collision):**
- Worker panes (index > 0) automatically notify pane 0 (orchestrator) with last 20 lines of output
- Notifications are queued and sent with 15-second gaps to prevent overwhelming orchestrator
- Worker panes auto-kill after queuing notification
- Use `parent: agentwire` in `.agentwire.yml` for voice-orch → main notifications

**Queue system files:**
- `~/.agentwire/queue-processor.sh` - Processes queue with 15s delays between alerts
- `~/.agentwire/queues/{session}.jsonl` - Per-session notification queues

**Worker idle sequence:**
1. `session.idle` fires → wait 2s (let OpenCode settle)
2. Capture last 20 lines of output
3. Queue notification to `{session}.jsonl`
4. Start queue processor if not running
5. Wait 1s → call `agentwire kill --pane N` (3s internal wait before kill)

**Both Claude Code and OpenCode** support idle notifications:
- Claude Code: via `~/.claude/hooks/suppress-bg-notifications.sh`
- OpenCode: via `~/.config/opencode/plugin/agentwire-notify.ts`

**Creating a project with roles:**

```bash
# Option 1: Create .agentwire.yml first, then create session
echo "type: claude-bypass
roles:
  - voice-orchestrator
  - glm-orchestration" > ~/projects/myproject/.agentwire.yml

agentwire new -s myproject -p ~/projects/myproject

# Option 2: Specify roles on command line (saves to .agentwire.yml)
agentwire new -s myproject -p ~/projects/myproject --roles voice-orchestrator,glm-orchestration
```

### Built-in Roles

Roles are bundled in the `agentwire/roles/` package directory:
- `agentwire.md` - Main orchestrator role (coordinates projects, uses dotdev voice)
- `voice-orchestrator.md` - Project orchestrator (delegates to workers, waits for notifications)
- `glm-orchestration.md` - Comprehensive GLM worker management guide (task templates, failure patterns)
- `glm-worker.md` - GLM task executor (focused execution, system detects idle)
- `voice-worker.md` - Worker that uses voice for status updates
- `worker.md` - Basic worker pane role
- `chatbot.md` - Chatbot personality
- `voice.md` - Voice input handling

## Session Roles

| Role | Use Case | Key Behavior |
|------|----------|--------------|
| `agentwire` | Main orchestrator | Uses `dotdev` voice, coordinates multiple projects |
| `voice-orchestrator` | Project orchestrator | Spawns workers via `agentwire spawn`, waits for notifications |
| `glm-worker` | Worker pane | Execute task, stop when done, system notifies orchestrator |
| `worker` | Basic worker | No voice, no AskUserQuestion |

**For detailed GLM task templates:** Add `glm-orchestration` role to voice-orchestrator sessions.

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

| Topic | Location |
|-------|----------|
| CLI | `agentwire --help`, `agentwire <cmd> --help` |
| Portal modes/API | `docs/PORTAL.md` |
| Architecture | `docs/architecture.md` |
| Security hooks | `docs/security/damage-control.md` |
| Troubleshooting | `docs/TROUBLESHOOTING.md` |
| Shell escaping | `docs/SHELL_ESCAPING.md` |
| TTS (RunPod) | `docs/runpod-tts.md` |
| TTS (self-hosted) | `docs/tts-self-hosted.md` |
| Remote machines | `docs/remote-machines.md` |
