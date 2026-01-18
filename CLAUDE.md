# AgentWire

Voice interface for AI coding agents. Push-to-talk from any device to tmux sessions running Claude Code.

**No Backwards Compatibility** - Pre-launch, no customers. Change things completely, no legacy fallbacks.

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

All session/machine/template logic lives in CLI commands (`__main__.py`). The portal (`server.py`) is a thin wrapper that:
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

# Pane commands (for workers within same session)
agentwire spawn --roles worker  # spawn worker pane
agentwire send --pane 1 "task"  # send to pane
agentwire output --pane 1       # read pane output
agentwire kill --pane 1         # kill pane
agentwire jump --pane 1         # focus pane

# Portal management
agentwire portal start          # start in tmux
agentwire portal stop           # stop portal
agentwire portal restart        # stop + start
agentwire portal status         # check health

# Machine management
agentwire machine list
agentwire machine add <id> <host>
agentwire machine remove <id>

# Template management
agentwire template list
agentwire template show <name>
agentwire template create <name>
agentwire template delete <name>

# Project discovery
agentwire projects list          # discover projects from projects_dir
agentwire projects list --json   # JSON output for scripting
```

Session formats: `name`, `project/branch` (worktree), `name@machine` (remote)
Pane targeting: `--pane N` auto-detects session from `$TMUX_PANE`

For CLI details: `agentwire --help` or `agentwire <cmd> --help`

## Config

All in `~/.agentwire/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Main config (TTS/STT backends, ports) |
| `roles/*.md` | Role instructions appended to sessions |
| `hooks/` | PreToolUse hooks (damage-control, session-type) |
| `templates/*.yaml` | Session templates |

Per-session config (type, roles, voice) lives in `.agentwire.yml` in each project directory.

## Session Roles

| Role | Created With | Restrictions |
|------|--------------|--------------|
| agentwire | `agentwire new -s name` or `--roles agentwire` | None (guided by role instructions) |
| worker | `agentwire spawn` or `--roles worker` | No voice, no AskUserQuestion |

## Key Patterns

- **agentwire sessions** coordinate via voice, delegate to workers
- **worker panes** spawn within the orchestrator's session (visible dashboard)
- **Pane 0** = orchestrator, **panes 1+** = workers
- **Damage-control hooks** block dangerous ops (`rm -rf`, `git push --force`, etc.)
- **Smart TTS routing** - audio goes to browser if connected, local speakers if not

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
| Installation | `docs/installation.md` |
| Security hooks | `docs/security/damage-control.md` |
