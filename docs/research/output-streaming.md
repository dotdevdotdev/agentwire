# Real-Time Output Streaming Research

Research on alternatives to polling `capture-pane` for AgentWire output.

## Current Implementation

AgentWire uses `capture-pane` polling:

```python
# From agentwire/agents/tmux.py
def get_output(self, name: str, lines: int = 50) -> str:
    result = self._run_local([
        "tmux", "capture-pane",
        "-t", session_name,
        "-p",  # Print to stdout
        "-e",  # Include ANSI escape sequences
        "-S", f"-{lines}",  # Start from N lines back
    ])
    return result.stdout
```

This is called on-demand (not streaming).

## capture-pane Characteristics

| Aspect | Behavior |
|--------|----------|
| **Type** | Point-in-time snapshot |
| **History** | Limited by `history-limit` setting |
| **Performance** | Fast for single calls |
| **Streaming** | Not supported (must poll) |
| **Deduplication** | Caller must track what's "new" |

## Alternative: pipe-pane

tmux's `pipe-pane` streams new output to an external command in real-time.

```bash
# Start streaming to file
tmux pipe-pane -t session 'cat >> ~/session.log'

# Stop streaming
tmux pipe-pane -t session
```

### Key Characteristics

| Aspect | Behavior |
|--------|----------|
| **Type** | Real-time stream of new output |
| **Direction** | `-O` = pane→command (default), `-I` = command→pane |
| **Toggle** | `-o` flag toggles on/off |
| **Limit** | One pipe per pane |
| **Content** | Everything including typed commands, control chars |

### Gotchas

1. **Logs everything** - typed commands, backspaces, ANSI codes
2. **One pipe per pane** - can't have multiple consumers
3. **No history** - only streams new output, doesn't include existing
4. **Cleanup required** - must explicitly stop pipe

### Potential Use Cases for AgentWire

| Use Case | pipe-pane Fit |
|----------|--------------|
| Real-time portal updates | Possible - pipe to named pipe, portal reads |
| Wait for specific output | Possible - pipe through grep |
| Session logging | Good fit |
| On-demand output fetch | Bad fit - use capture-pane |

## Alternative: Control Mode

tmux control mode (`-CC`) provides structured, async output.

```bash
tmux -CC attach -t session
```

Outputs structured messages prefixed with `%`:
```
%begin 1234567890 1 0
%end 1234567890 1 0
%output %1 hello world
```

### Characteristics

| Aspect | Behavior |
|--------|----------|
| **Latency** | Higher (~850ms vs 220ms normal mode) |
| **Structure** | Machine-parseable protocol |
| **Async** | Notifications pushed, not polled |
| **Complexity** | Requires protocol parser |

### Verdict

Control mode latency penalty makes it unsuitable for interactive use. The structured protocol is nice but not worth 4x latency.

## Alternative: Named Pipe + pipe-pane

Hybrid approach for real-time streaming to portal:

```python
# Setup
os.mkfifo(f'/tmp/agentwire-{session}.pipe')
subprocess.run(['tmux', 'pipe-pane', '-t', session, f'cat >> /tmp/agentwire-{session}.pipe'])

# Portal reads from pipe (non-blocking)
async def stream_output():
    with open(f'/tmp/agentwire-{session}.pipe', 'r') as pipe:
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, pipe.readline)
            if line:
                yield line
```

### Challenges

1. **Cleanup** - must remove pipe and stop tmux pipe-pane on session end
2. **Cross-machine** - doesn't work for remote sessions
3. **ANSI filtering** - raw output needs processing
4. **Race conditions** - pipe must exist before tmux writes

## Recommendation for AgentWire

### Keep capture-pane for Core Functionality

The current polling approach is fine for:
- `agentwire output` CLI command
- Portal refresh on user action
- Status checks

### Consider pipe-pane for Optional Live Mode

For real-time portal updates (WebSocket streaming):

```
# User enables live mode
agentwire portal start --live-output

# Creates pipe-pane for each active session
# Portal streams via WebSocket
```

**Implementation complexity:** Medium
**User value:** Nice-to-have for watching long builds

### Don't Use Control Mode

Latency penalty outweighs structured output benefits.

## Performance Comparison

| Approach | Latency | CPU | Complexity | Remote Support |
|----------|---------|-----|------------|----------------|
| capture-pane (poll) | ~10ms/call | Low | Low | Yes |
| pipe-pane (stream) | Real-time | Medium | Medium | No* |
| Control mode | ~850ms | Low | High | Yes |

*Remote pipe-pane would require streaming over SSH, adding complexity.

## Open Questions

1. Is real-time streaming a user-requested feature?
2. Worth the complexity for remote sessions?
3. Should this be opt-in only?

## Sources

- [tmux pipe-pane docs](https://man7.org/linux/man-pages/man1/tmux.1.html)
- [tmux Advanced Use Wiki](https://github.com/tmux/tmux/wiki/Advanced-Use)
- [Baeldung tmux Logging](https://www.baeldung.com/linux/tmux-logging)
- [tmux Control Mode Wiki](https://github.com/tmux/tmux/wiki/Control-Mode)
