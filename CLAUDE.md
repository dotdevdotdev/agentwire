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

## Use CLI, Not Raw tmux

```bash
agentwire new -s name           # not: tmux new-session
agentwire send -s name "prompt" # not: tmux send-keys
agentwire output -s name        # not: tmux capture-pane
agentwire kill -s name          # not: tmux kill-session
agentwire list                  # not: tmux list-sessions
```

Session formats: `name`, `project/branch` (worktree), `name@machine` (remote)

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
| worker | `agentwire new -s name --roles worker` | No voice, no AskUserQuestion |

## Key Patterns

- **agentwire sessions** coordinate via voice, delegate to workers for multi-file work
- **worker sessions** execute autonomously, report factual results
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
