# Mission: Pane-Based Workers

> Spawn workers as tmux panes within the parent session by default.

## Problem

Current model uses separate tmux sessions per agent. User can only see one at a time, must use `agentwire output` to check on workers. No visual dashboard. Role instructions tell agents to use `agentwire new -s name` which creates new sessions.

## Solution

Spawn workers as panes within the orchestrator's session **by default**:
- Main orchestrator in pane 0
- Workers in panes 1, 2, 3...
- All visible simultaneously (tiled layout)
- Jump between panes with keyboard shortcuts
- `agentwire output` still works but visual is primary
- Role instructions updated to use pane commands

## Key tmux Commands

```bash
# Spawn worker pane (detached, don't steal focus)
tmux split-window -t session -h -d -c /path/to/cwd

# Target pane for commands
tmux send-keys -t session:0.1 "command" Enter

# List panes in session
tmux list-panes -t session -F '#{pane_index}:#{pane_pid}:#{pane_current_command}'

# Kill specific pane
tmux kill-pane -t session:0.1

# Focus pane (jump to it)
tmux select-pane -t session:0.1

# Get pane info
tmux display -t %42 -p '#{pane_index}'
```

## Wave 1: Human Actions (RUNTIME BLOCKING)

- [x] None required

## Wave 2: Core Pane Management Module

Create `agentwire/pane_manager.py` with:

- [x] `spawn_worker_pane(session: str, cwd: str, cmd: str) -> int` - returns pane index
- [x] `list_panes(session: str) -> List[PaneInfo]` - pane index, pid, command
- [x] `send_to_pane(session: str, pane_index: int, text: str)`
- [x] `capture_pane(session: str, pane_index: int) -> str`
- [x] `kill_pane(session: str, pane_index: int)`
- [x] `focus_pane(session: str, pane_index: int)`
- [x] `get_pane_info(tmux_pane_id: str) -> PaneInfo`

## Wave 3: CLI Command Updates

Update `__main__.py` commands:

- [x] `agentwire spawn` - NEW command for worker panes
  - Auto-detects session from `$TMUX_PANE` env var
  - `--roles` - worker roles (default: worker)
  - `--cwd` - working directory (default: current)
  - `-s` - optional explicit session (for cross-session spawning)
  - Returns pane index on success

- [x] `agentwire send --pane N` - add pane targeting
  - `--pane N` targets specific pane in current session
  - Auto-detects session from `$TMUX_PANE`
  - `-s` still works for session-level sends

- [x] `agentwire output --pane N` - add pane targeting
  - `--pane N` captures specific pane output
  - Auto-detects session from `$TMUX_PANE`

- [x] `agentwire kill --pane N` - add pane targeting
  - `--pane N` kills specific pane (not whole session)
  - `-s` without `--pane` kills entire session (existing behavior)

- [x] `agentwire jump --pane N` - NEW command to focus pane
  - Switches focus to specified pane
  - Auto-detects session from `$TMUX_PANE`
  - `-s` for cross-session jumping

- [x] `agentwire list` - show panes when inside session
  - Auto-detect: if `$TMUX_PANE` set, show panes in current session
  - `--sessions` flag to show sessions instead
  - Outside tmux: show sessions (existing behavior)

## Wave 4: Update Role Instructions

Update `agentwire/roles/agentwire.md` so session agents spawn panes by default:

- [x] Replace `agentwire new -s name --roles worker` examples with `agentwire spawn`
- [x] Update "Spawning Workers" section with pane commands
- [x] Add note about visual dashboard (can see workers while orchestrating)
- [x] Update "Monitoring and Reporting" section for pane-based workflow
- [x] Keep `agentwire new -s name --roles worker` as alternative for separate sessions

## Wave 5: Integration with Existing Patterns

- [x] Keep `agentwire new` for creating main sessions (unchanged)
- [x] Ensure `agentwire output` auto-detects if targeting session or pane
- [x] `agentwire list` without flags shows panes in current session

## Wave 6: Documentation

- [x] Update CLI help text for new flags
- [x] Update CLAUDE.md with pane-based worker patterns

## Completion Criteria

- [x] Can spawn worker as pane: `agentwire spawn --roles worker`
- [x] Session auto-detected from `$TMUX_PANE` (no `-s` needed)
- [x] Can list panes: `agentwire list` (auto-detects context)
- [x] Can send to pane: `agentwire send --pane 1 "do something"`
- [x] Can capture pane output: `agentwire output --pane 1`
- [x] Can kill worker pane: `agentwire kill --pane 1`
- [x] Can jump to pane: `agentwire jump --pane 1`
- [x] Visual dashboard works: multiple agents visible in tiled panes
- [x] Role instructions updated: agents use pane commands by default
- [x] Fallback works: `agentwire new -s name --roles worker` still creates separate session

## Notes

- Pane index 0 is always main orchestrator
- Workers are panes 1+
- `$TMUX_PANE` env var used for auto-detection (e.g., `%37`)
- Get session from pane: `tmux display -t "$TMUX_PANE" -p '#{session_name}'`
- Use `-d` flag on split-window to avoid stealing focus
- Sleep 0.4s after creating pane before send-keys (race condition)
- `TMUX_PANE` also available in hooks to identify which pane triggered

## References

- Research: `docs/research/tmux-programmatic-management.md`
- Notification hooks: `~/.claude/docs/notification-hooks.md`
