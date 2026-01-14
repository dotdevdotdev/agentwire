# Mission: Real-Time Output Streaming

**Status:** CANCELLED - Not viable

**Reason:** Complexity outweighs benefits. Local-only limitation (doesn't work for remote sessions), requires named pipe cleanup, raw output includes noise (typed commands, ANSI codes). Current `capture-pane` polling works fine for actual use cases.

---

> Add optional live output streaming via pipe-pane for portal WebSocket updates.

**Branch:** `mission/realtime-output-streaming` (created on execution)
**Priority:** Low - nice-to-have enhancement

## Context

Current implementation uses polling with `capture-pane`:
- Portal refreshes output on user action or timer
- Works well for most use cases
- No real-time streaming

**Goal:** Optional live mode that streams output to connected portal clients via WebSocket.

**Research:** See `docs/research/output-streaming.md`

---

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - all code changes.

---

## Wave 2: pipe-pane Infrastructure

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Create named pipe directory (`/tmp/agentwire-pipes/`) | `agents/tmux.py` |
| 2.2 | Add `start_streaming(session)` method using pipe-pane | `agents/tmux.py` |
| 2.3 | Add `stop_streaming(session)` method | `agents/tmux.py` |
| 2.4 | Add cleanup on session kill | `agents/tmux.py` |

**Implementation:**
```python
def start_streaming(self, name: str) -> Path | None:
    """Start streaming session output to named pipe. Returns pipe path."""
    session_name, machine = self._parse_session_name(name)

    # Only works for local sessions
    if machine:
        return None

    pipe_path = Path(f"/tmp/agentwire-pipes/{session_name}.pipe")
    pipe_path.parent.mkdir(parents=True, exist_ok=True)

    # Create named pipe if doesn't exist
    if not pipe_path.exists():
        os.mkfifo(pipe_path)

    # Start tmux pipe-pane
    self._run_local([
        "tmux", "pipe-pane", "-t", session_name,
        f"cat >> {pipe_path}"
    ])

    return pipe_path

def stop_streaming(self, name: str) -> bool:
    """Stop streaming and cleanup pipe."""
    session_name, machine = self._parse_session_name(name)

    if machine:
        return False

    # Stop pipe-pane (empty command)
    self._run_local(["tmux", "pipe-pane", "-t", session_name])

    # Remove named pipe
    pipe_path = Path(f"/tmp/agentwire-pipes/{session_name}.pipe")
    if pipe_path.exists():
        pipe_path.unlink()

    return True
```

---

## Wave 3: Portal WebSocket Integration

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Add `/api/sessions/{name}/stream` WebSocket endpoint | `server.py` |
| 3.2 | Create async pipe reader that yields lines | `server.py` |
| 3.3 | Add stream toggle button to portal UI | `portal/` |
| 3.4 | Handle WebSocket disconnect → stop streaming | `server.py` |

**WebSocket endpoint:**
```python
@app.websocket("/api/sessions/{name}/stream")
async def stream_session_output(websocket: WebSocket, name: str):
    await websocket.accept()

    pipe_path = agent.start_streaming(name)
    if not pipe_path:
        await websocket.close(code=4001, reason="Streaming not supported for remote sessions")
        return

    try:
        async with aiofiles.open(pipe_path, 'r') as pipe:
            while True:
                line = await pipe.readline()
                if line:
                    await websocket.send_text(line)
                else:
                    await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        agent.stop_streaming(name)
```

---

## Wave 4: ANSI Filtering & Polish

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Add option to filter ANSI codes from stream | `agents/tmux.py` |
| 4.2 | Handle portal reconnection (resume or restart stream) | `server.py` |
| 4.3 | Add `--live` flag to CLI `agentwire output` for terminal streaming | `__main__.py` |

---

## Completion Criteria

- [ ] `start_streaming()` / `stop_streaming()` methods work for local sessions
- [ ] Portal can toggle live streaming via WebSocket
- [ ] Streams cleanup properly on disconnect
- [ ] `agentwire output --live` streams to terminal
- [ ] Clear messaging that streaming only works for local sessions

---

## Technical Notes

### Limitations

1. **Local only** - pipe-pane doesn't work over SSH
2. **One consumer** - can't have multiple WebSocket clients streaming same session
3. **Raw output** - includes typed commands, ANSI codes, everything

### Why pipe-pane vs Control Mode

| | pipe-pane | Control Mode |
|-|-----------|--------------|
| Latency | Real-time | ~850ms |
| Complexity | Low | High (protocol parsing) |
| Remote | No | Yes |

pipe-pane chosen for simplicity and low latency. Control mode latency is unacceptable for real-time streaming.

### Future Enhancement

Could add server-side filtering:
```python
# Filter ANSI and echo typed commands
pipe_cmd = f"cat >> {pipe_path} | ansifilter"
```

### User Value Assessment

**Who benefits:**
- Users watching long builds/tests in portal
- Debugging sessions in real-time

**Who doesn't need this:**
- Users primarily using CLI
- Users with remote sessions (unsupported)

This is a nice-to-have, not critical functionality.
