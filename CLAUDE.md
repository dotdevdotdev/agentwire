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

**Always use `agentwire` CLI for session management.** The CLI is the authoritative interface - the web portal is just a frontend that calls the same underlying commands.

Never use raw tmux commands or create skills/commands that duplicate CLI functionality:

```bash
agentwire new -s name           # not: tmux new-session
agentwire send -s name "prompt" # not: tmux send-keys
agentwire output -s name        # not: tmux capture-pane
agentwire kill -s name          # not: tmux kill-session
agentwire list                  # not: tmux list-sessions

# Pane commands (for workers within same session)
agentwire spawn --roles worker  # spawn worker pane
agentwire send --pane 1 "task"  # send to pane
agentwire output --pane 1       # read pane output
agentwire kill --pane 1         # kill pane
agentwire jump --pane 1         # focus pane
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

## Docs

| Topic | Location |
|-------|----------|
| CLI | `agentwire --help`, `agentwire <cmd> --help` |
| Portal modes/API | `docs/PORTAL.md` |
| Architecture | `docs/architecture.md` |
| Installation | `docs/installation.md` |
| Security hooks | `docs/security/damage-control.md` |
