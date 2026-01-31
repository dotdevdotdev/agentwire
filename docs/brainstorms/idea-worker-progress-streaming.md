# Worker Progress Streaming

> Real-time visibility into worker progress without polling or waiting for completion.

## Problem

Currently, orchestrators spawn workers and wait blindly for idle notifications. This creates several issues:

1. **No visibility** - Orchestrators don't know if a worker is making progress, stuck, or going off track until completion
2. **Late intervention** - By the time a worker reports "BLOCKED", it may have wasted significant time/tokens
3. **Poor UX** - Humans watching the orchestrator just see "Workers spawned, waiting" with no feedback
4. **Suboptimal parallelism** - Can't make informed decisions about spawning additional workers

## Proposed Solution

Workers emit structured progress events that stream to the orchestrator in real-time. Events follow a simple schema:

```typescript
interface ProgressEvent {
  worker: number;           // Pane index
  type: 'start' | 'step' | 'file' | 'test' | 'error' | 'complete';
  message: string;          // Human-readable description
  metadata?: {
    file?: string;          // Current file being worked on
    progress?: number;      // 0-100 percentage if known
    blockers?: string[];    // Emerging issues
  };
}
```

### Emission Mechanism

Workers emit events via a simple file-based protocol (works with both Claude Code and OpenCode):

```bash
# Worker writes events to a JSONL file
echo '{"type":"step","message":"Creating auth middleware"}' >> .agentwire/progress-1.jsonl
```

The agentwire system watches these files and:
1. Streams events to pane 0 (orchestrator) via `agentwire alert`
2. Aggregates into a live dashboard view in the portal
3. Makes events available via MCP tool: `agentwire_worker_progress(pane=1)`

### Orchestrator Integration

Orchestrators can subscribe to progress events:

```python
# In orchestrator role instructions
agentwire_watch_progress()  # Start receiving progress alerts

# Or poll explicitly
events = agentwire_worker_progress(pane=1, since="2m")
```

Progress alerts arrive as:
```
[PROGRESS pane 1] step: Creating auth middleware (3/5 steps)
[PROGRESS pane 1] file: src/middleware/auth.ts (created)
[PROGRESS pane 1] error: Test failure in auth.test.ts
```

### Worker Role Updates

Add progress emission guidance to worker roles:

```markdown
## Progress Reporting

Emit progress events at key milestones:

1. **Task start** - What you're about to do
2. **File changes** - Each file created/modified
3. **Test results** - Pass/fail status
4. **Blockers** - Issues that might need orchestrator input
5. **Completion** - Final status

Use: `echo '{"type":"step","message":"..."}' >> .agentwire/progress-$PANE.jsonl`
```

### Portal Dashboard

The web portal shows a live worker dashboard:

```
┌─────────────────────────────────────────────────────┐
│ Workers                                              │
├─────────────────────────────────────────────────────┤
│ [1] auth-endpoints     ████████░░ 80%  auth.ts      │
│ [2] database-schema    ██████████ done              │
│ [3] frontend-forms     ███░░░░░░░ 30%  blocked!     │
└─────────────────────────────────────────────────────┘
```

## Implementation Considerations

### File Watching

Use `fswatch` or Python's `watchdog` to monitor `.agentwire/progress-*.jsonl` files. On macOS, FSEvents provides efficient native watching.

### Event Batching

Batch events over 500ms windows to avoid flooding the orchestrator with micro-updates. Aggregate into summaries:
- "Worker 1: 3 files created, tests passing"
- "Worker 3: blocked on missing dependency"

### Backward Compatibility

Workers that don't emit progress events continue working as before. Progress streaming is opt-in via worker role configuration.

### Cleanup

Progress files are ephemeral - deleted when worker pane exits. The orchestrator's `.agentwire/` directory gets cleaned up regularly.

## Potential Challenges

1. **Agent compliance** - Workers (especially GLM) may not consistently emit events. Need explicit, copy-paste instructions in role definitions.

2. **Event noise** - Too many events could overwhelm orchestrators. Need smart filtering/aggregation.

3. **Cross-agent protocol** - Claude Code and OpenCode have different tool access. File-based protocol is the common denominator but feels clunky.

4. **Latency** - File watching adds latency vs direct IPC. Acceptable for progress updates (not for commands).

5. **Portal complexity** - Real-time dashboard requires WebSocket streaming from file watcher → portal → browser.

## Future Extensions

- **Progress-based decisions** - Orchestrators could automatically intervene when blockers appear
- **ETA estimation** - Track historical completion times to estimate remaining work
- **Voice progress** - Periodic TTS summaries: "Two workers running, one almost done"
- **Mobile notifications** - Push progress to phone when away from desktop
