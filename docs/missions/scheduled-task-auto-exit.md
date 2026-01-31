# Mission: Scheduled Task Auto-Exit

> Living document. Update this, don't create new versions.

## Status: Complete

## Summary

Add configurable auto-exit behavior for scheduled tasks run via `agentwire ensure`. After task completion, the session can optionally exit automatically for a clean slate on the next run.

## Problem

Currently, scheduled task sessions stay open after completion:
- Context accumulates between runs (potentially polluting future tasks)
- Resources tied up by idle sessions
- Manual cleanup required

## Solution

Add `exit_on_complete` option to task configuration, defaulting to `true`.

### Task Configuration

```yaml
tasks:
  brainstorm:
    exit_on_complete: true  # default - session exits after completion
    prompt: |
      Generate a brainstorm idea...

  daily-standup:
    exit_on_complete: false  # keep session for manual follow-up
    prompt: |
      Summarize today's work...
```

### Behavior

| `exit_on_complete` | After completion |
|--------------------|------------------|
| `true` (default)   | Session sends `/exit` and terminates |
| `false`            | Session stays open, idle |

## Implementation

### 1. Update Task Schema

In `agentwire/tasks.py`:

```python
@dataclass
class Task:
    name: str
    prompt: str
    # ... existing fields ...
    exit_on_complete: bool = True  # New field
```

### 2. Update Hook Logic

In `~/.claude/hooks/suppress-bg-notifications.sh`, after writing completion signal on second idle:

```bash
# Read exit_on_complete from task context
exit_on_complete=$(jq -r '.exit_on_complete // true' "$task_context_file" 2>/dev/null)

if [[ "$exit_on_complete" == "true" ]]; then
  echo "[$(date -Iseconds)] TASK: exit_on_complete=true, sending /exit" >> "$dlog"
  sleep 1
  /Users/dotdev/.local/bin/agentwire send -s "$tmux_session" "/exit" >/dev/null 2>&1 &
fi
```

### 3. Update Ensure Command

In `cmd_ensure()`, write `exit_on_complete` to task context file:

```python
task_context = {
    "task": task_name,
    "summary_file": summary_filename,
    "idle_count": 0,
    "exit_on_complete": task.exit_on_complete,  # Add this
}
```

### 4. Update OpenCode Plugin

Same logic in `~/.config/opencode/plugin/agentwire-notify.ts` for OpenCode sessions.

## CLI Override (Optional)

Add `--keep-session` flag to override task config:

```bash
# Task has exit_on_complete: true, but keep session anyway
agentwire ensure -s brainstorm -p ~/projects/foo --task brainstorm --keep-session
```

## Testing

1. Task with `exit_on_complete: true` (default):
   - Run ensure
   - Verify task completes
   - Verify session exits automatically
   - Verify next ensure run creates fresh session

2. Task with `exit_on_complete: false`:
   - Run ensure
   - Verify task completes
   - Verify session stays open
   - Verify can attach and interact

3. Override with `--keep-session`:
   - Task has `exit_on_complete: true`
   - Run with `--keep-session`
   - Verify session stays open

## Acceptance Criteria

- [ ] `exit_on_complete` field added to task schema (default: true)
- [ ] Hook sends `/exit` when `exit_on_complete: true`
- [ ] Task context file includes `exit_on_complete` value
- [ ] OpenCode plugin updated with same logic
- [ ] `--keep-session` CLI flag overrides task config
- [ ] CLAUDE.md updated with new task option
- [ ] Brainstorm task updated to use default (auto-exit)
