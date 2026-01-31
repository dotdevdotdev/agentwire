# Worker Health Dashboard: Real-Time Orchestration Visibility

> A live dashboard showing worker status, activity, and health across all panes.

## Problem

When orchestrating multiple workers, you're flying blind:

- **Status opacity**: Is worker 2 stuck or just thinking? Did worker 3 finish?
- **Output scrollback**: `agentwire_pane_output` gives you the last N lines, but you miss context
- **Manual polling**: You have to actively check each worker instead of getting notified
- **No aggregate view**: With 3+ workers, mental tracking becomes error-prone

Current workflow:
```
spawn worker 1 → spawn worker 2 → spawn worker 3 → wait
... time passes ...
"Did they finish? Let me check..."
pane_output(1) → still working
pane_output(2) → looks done?
pane_output(3) → error? hard to tell
```

This friction makes orchestrators hesitant to parallelize aggressively.

## Proposed Solution

**Worker Health Dashboard** - a real-time view embedded in the portal showing:

1. **Pane list** with status indicators (working/idle/error/stuck)
2. **Activity sparkline** - visual indicator of recent activity per pane
3. **Last meaningful output** - summarized, not raw terminal dump
4. **Time since last activity** - "2m ago" helps spot stuck workers
5. **One-click actions** - kill, send message, view full output

### Status Detection

Determine worker state from observable signals:

| Status | Detection Method |
|--------|------------------|
| **Working** | Output changing, cursor moving |
| **Idle** | No output change for N seconds, at prompt |
| **Error** | Error patterns in output (stack traces, "failed", exit codes) |
| **Stuck** | Working state for >5 minutes with repetitive output |
| **Complete** | Worker exited cleanly (pane closed) |

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│ Workers (3 active)                              [+ New] │
├─────────────────────────────────────────────────────────┤
│ ● Pane 1: Auth endpoints     ▁▂▃▅▇▅▃▁  Working  12s   │
│   "Adding JWT middleware to routes/auth.ts..."         │
│                                          [Kill] [View] │
├─────────────────────────────────────────────────────────┤
│ ○ Pane 2: Docs update        ▇▇▃▁▁▁▁▁  Idle     2m    │
│   "Documentation updated. Ready for review."           │
│                                          [Kill] [View] │
├─────────────────────────────────────────────────────────┤
│ ⚠ Pane 3: Test fixes         ▅▅▅▅▅▅▅▅  Stuck    5m    │
│   "Retrying test... Retrying test... Retrying..."      │
│                                          [Kill] [View] │
└─────────────────────────────────────────────────────────┘
```

### Activity Sparkline

8-character sparkline showing output velocity over the last 2 minutes:
- Each character = 15 seconds
- Height = lines of output in that window
- Visual pattern recognition: burst → taper = task completing

### Smart Summarization

Instead of showing raw terminal output, extract the "last meaningful line":

1. Skip ANSI escape codes
2. Skip empty lines and spinner frames
3. Prefer lines with file paths, "done", "error", "created"
4. Truncate to ~60 chars with ellipsis

### Voice Integration

Dashboard state feeds into voice updates:

```
[Orchestrator]: "Status check"
[System]: "Three workers. Auth endpoints working for 12 seconds.
          Docs update idle for 2 minutes. Test fixes appears stuck,
          retrying for 5 minutes."
```

Or proactive alerts:
```
[System]: "Worker 3 may be stuck. Same output repeating for 5 minutes."
```

## Implementation Considerations

### Data Collection

Portal already has `capture-pane` access. Add:

```python
class WorkerHealth:
    pane_id: int
    task_description: str  # From initial send
    status: Literal["working", "idle", "error", "stuck", "complete"]
    last_output: str  # Summarized
    last_activity: datetime
    output_history: list[int]  # Lines per 15s window, last 8

# Polling interval
HEALTH_CHECK_INTERVAL = 5  # seconds
```

### Stuck Detection

Heuristics for "stuck":
1. Same 3 lines repeating for >3 minutes
2. "retry" or "attempting" in output + >5 minutes elapsed
3. High output velocity but no file changes (spinning)

Configurable thresholds in `config.yaml`:

```yaml
worker_health:
  stuck_threshold_minutes: 5
  idle_threshold_seconds: 30
  check_interval_seconds: 5
```

### UI Placement

Options:
1. **Sidebar panel** - Always visible, collapsible
2. **Floating overlay** - Toggle with keyboard shortcut
3. **Separate route** - `/dashboard` page

Recommend: Collapsible sidebar. Orchestrators want it visible while working.

### WebSocket Updates

Stream health updates to connected clients:

```json
{
    "type": "worker_health",
    "panes": [
        {
            "id": 1,
            "status": "working",
            "task": "Auth endpoints",
            "last_output": "Adding JWT middleware...",
            "activity": [1, 2, 3, 5, 7, 5, 3, 1],
            "seconds_since_activity": 12
        }
    ]
}
```

### Performance

With 5+ workers and 5-second polling:
- 1 `tmux capture-pane` per worker per interval
- Minimal CPU impact
- Consider adaptive polling: faster when workers active, slower when all idle

## Potential Challenges

1. **Task description tracking**: Workers don't formally register their task. Solution: Parse first message sent to pane, or require explicit task name in spawn.

2. **False "stuck" positives**: Some tasks legitimately take long without output (big file generation). Solution: Allow workers to send heartbeat signals, or let orchestrator mark as "expected long-running".

3. **Terminal parsing complexity**: ANSI codes, multi-line outputs, progress bars. Solution: Strip aggressively, prefer simple heuristics over perfect parsing.

4. **Screen real estate**: Dashboard competes with session output. Solution: Make it collapsible, remember user preference.

5. **Multi-session scope**: Should dashboard show workers across all sessions or just current? Solution: Default to current session, optional "all sessions" toggle.

## Future Extensions

- **Worker cost estimation**: If we can detect model (Claude vs GLM), estimate token spend
- **Historical view**: "What did worker 2 do?" replay after completion
- **Dependency visualization**: Show which workers block others
- **Alert rules**: "Notify me if any worker stuck >10 minutes"

## Success Metrics

- Faster stuck worker detection (currently manual)
- Increased parallelization (confidence to spawn more workers)
- Reduced "what's happening?" polling via voice
