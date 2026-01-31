# Voice Interrupts: Stop Workers Mid-Task

> Interrupt running workers with voice commands instead of waiting for completion or manual kills.

## Problem

Workers run to completion. Once a task is sent, you must:
1. Wait for the worker to finish (minutes)
2. Manually kill via `agentwire kill --pane N`
3. Re-spawn and re-instruct

This breaks flow in common scenarios:

```
[User]: "Add authentication to the API"
[Worker starts, reads wrong files, heads down wrong path]
[User realizes the mistake 30 seconds in]
[User]: ...waits 3 more minutes for worker to finish wrong approach
        OR
        Opens terminal, runs kill command, respawns, re-instructs
```

Voice should be the primary interface. You shouldn't need to touch the keyboard to course-correct a worker.

## Why This Matters

1. **Wasted time** - Wrong-path workers burn minutes before completing
2. **Wasted tokens** - Every turn on the wrong path costs money
3. **Broken flow** - Switching to keyboard interrupts voice workflow
4. **Frustration** - Watching a worker do the wrong thing, unable to stop it

The voice interface should support the full control loop: start, monitor, adjust, stop.

## Proposed Solution

**Voice-triggered interrupts** that workers respond to immediately.

### Interrupt Types

| Voice Command | Effect |
|--------------|--------|
| "Stop" / "Stop worker" | Graceful stop, worker saves state and exits |
| "Pause" | Worker pauses, waits for "continue" or new instruction |
| "Cancel" | Immediate kill, no state saved |
| "Actually..." | Pause + listen for correction |
| "Wrong file" | Worker backs out of current file, asks for direction |
| "Focus on {X}" | Redirect attention without stopping |

### Basic Interrupt Flow

```
[Worker is running in pane 1, editing auth.ts]

[User]: "Stop"

[System]:
1. Detects interrupt keyword
2. Sends interrupt signal to pane 1
3. Worker receives signal, stops current action
4. Worker: "Stopped. I was adding JWT validation to auth.ts.
           Want me to continue, try a different approach, or abandon?"

[User]: "Try using the existing session middleware instead"

[Worker]: "Got it, using session middleware..." [continues with new direction]
```

### Mid-Sentence Correction

The powerful case: interrupt with a correction in one utterance.

```
[Worker is editing LoginForm.tsx]

[User]: "Actually use the AuthContext not local state"

[System]:
1. Detects "actually" as interrupt trigger
2. Captures the correction: "use the AuthContext not local state"
3. Sends interrupt + correction to worker
4. Worker adjusts approach without full restart

[Worker]: "Switching to AuthContext..." [modifies approach]
```

### Pane Targeting

When multiple workers are running:

```
# Implicit targeting (most recent/active pane)
[User]: "Stop"
→ Stops the most recently active worker

# Explicit targeting
[User]: "Stop worker two"
[User]: "Pane one, pause"
[User]: "All workers stop"
```

### Graceful vs Immediate

**Graceful stop** (default): Worker gets a chance to clean up
- Finish current write (don't leave partial edits)
- Save progress summary
- Exit cleanly

**Immediate cancel**: Hard kill
- When worker is stuck in a loop
- When it's doing something destructive
- When graceful stop doesn't respond

```
[User]: "Stop"
[Worker doesn't respond in 5 seconds]
[System]: "Worker not responding. Say 'cancel' for hard kill."
[User]: "Cancel"
[System]: Kills pane immediately
```

## Implementation

### Interrupt Detection

Add interrupt detection to the STT pipeline:

```python
INTERRUPT_PATTERNS = {
    r"^stop\b": "stop",
    r"^pause\b": "pause",
    r"^cancel\b": "cancel",
    r"^actually\b": "redirect",
    r"^wrong\s+file\b": "wrong_file",
    r"^focus\s+on\b": "focus",
    r"^all\s+workers?\s+stop\b": "stop_all",
    r"^(worker|pane)\s+(\d+)\b": "targeted",
}

def detect_interrupt(text: str) -> InterruptType | None:
    """Check if utterance is an interrupt command."""
    text = text.lower().strip()
    for pattern, interrupt_type in INTERRUPT_PATTERNS.items():
        if re.match(pattern, text):
            return InterruptType(
                type=interrupt_type,
                text=text,
                remainder=re.sub(pattern, "", text).strip()
            )
    return None
```

### Interrupt Signal Delivery

Workers need to be interruptible. Two approaches:

**Option A: File-based signal (simple)**
```
.agentwire/interrupt-{pane}.signal
```

Workers poll for this file. When present:
1. Read interrupt type and message
2. Handle appropriately
3. Delete signal file

**Option B: tmux send-keys (immediate)**
```bash
# Send Ctrl+C equivalent followed by message
tmux send-keys -t session:pane C-c
sleep 0.1
tmux send-keys -t session:pane "INTERRUPT: stop" Enter
```

This is more immediate but may corrupt partial output.

**Recommended: Hybrid**
- File signal for graceful stops
- tmux send-keys for cancel/emergency

### Worker Interrupt Handler

Workers need interrupt awareness in their role instructions:

```markdown
## Interrupt Handling

You may receive interrupt signals via `.agentwire/interrupt.signal`.
Check this file periodically (every few operations).

Signal types:
- `stop`: Finish current write, summarize progress, exit
- `pause`: Stop work, acknowledge, wait for further instruction
- `redirect:{message}`: Adjust your approach per the message
- `cancel`: Stop immediately

When interrupted, always:
1. Acknowledge the interrupt
2. Summarize what you've done
3. Note what remains
4. Follow the interrupt type's behavior
```

### CLI Commands

```bash
# Send interrupt to specific pane
agentwire interrupt --pane 1 stop
agentwire interrupt --pane 1 pause
agentwire interrupt --pane 1 redirect "use AuthContext instead"

# Send to all workers
agentwire interrupt --all stop

# Cancel (hard kill) if worker doesn't respond
agentwire interrupt --pane 1 cancel
```

### MCP Tools

```python
@mcp.tool()
def worker_interrupt(
    pane: int,
    interrupt_type: Literal["stop", "pause", "cancel", "redirect"],
    message: str | None = None,
    timeout: int = 5
) -> str:
    """Send interrupt signal to a worker.

    Args:
        pane: Worker pane number
        interrupt_type: Type of interrupt
        message: Additional context (for redirect type)
        timeout: Seconds to wait for graceful stop before reporting
    """

@mcp.tool()
def workers_interrupt_all(interrupt_type: str) -> str:
    """Send interrupt to all worker panes."""
```

### Voice Command Integration

The portal's voice processing needs interrupt detection:

```python
async def handle_voice_input(text: str, session: str):
    """Process voice input, checking for interrupts first."""

    interrupt = detect_interrupt(text)

    if interrupt:
        # Handle interrupt instead of normal processing
        await handle_interrupt(interrupt, session)
        return

    # Normal voice command handling
    await send_to_agent(text, session)

async def handle_interrupt(interrupt: InterruptType, session: str):
    """Process an interrupt command."""

    workers = get_active_workers(session)

    if interrupt.type == "stop_all":
        for pane in workers:
            await send_interrupt(pane, "stop")
        say("Stopping all workers")
        return

    if interrupt.targeted_pane:
        pane = interrupt.targeted_pane
    else:
        # Default to most active worker
        pane = get_most_active_worker(session)

    if interrupt.type == "redirect":
        await send_interrupt(pane, "redirect", interrupt.remainder)
        say(f"Redirecting worker {pane}")
    else:
        await send_interrupt(pane, interrupt.type)
        say(f"Worker {pane} {interrupt.type}ped")
```

### Interrupt Feedback

Users need confirmation that interrupts worked:

```
[User]: "Stop"
[System TTS]: "Stopping worker one"

[After worker acknowledges]
[System TTS]: "Worker stopped. It was halfway through adding JWT validation."
```

Configuration for verbosity:
```yaml
interrupts:
  feedback: brief  # brief | detailed | none
```

## Edge Cases

### Worker Doesn't Respond

Workers may be stuck or not checking for interrupts:

```
[User]: "Stop"
[5 seconds pass, no response]
[System]: "Worker not responding to stop. Say 'cancel' for hard kill,
          or 'wait' to give it more time."
```

### Mid-Tool Execution

Worker is in the middle of a tool call (e.g., writing a file):

- **File writes**: Complete the current write, then stop (avoid partial files)
- **Bash commands**: Let current command finish if quick, otherwise interrupt
- **Reads**: Safe to stop anytime

Workers should track "safe to interrupt" state:
```python
interruptible = True

# About to write file
interruptible = False
write_file(path, content)
interruptible = True

# Check for interrupt
if interruptible and check_interrupt():
    handle_interrupt()
```

### Multiple Rapid Interrupts

User says "stop" then immediately "cancel":

- Queue interrupts, process in order
- Or: let "cancel" override pending "stop"

Probably: immediate types (cancel) override graceful types (stop, pause).

### Interrupt During Task Handoff

Worker is writing its exit summary when interrupted:

- Let the summary complete
- Interrupt is acknowledged but deferred by a few seconds

## Configuration

```yaml
# In ~/.agentwire/config.yaml
interrupts:
  enabled: true

  # How workers receive interrupts
  delivery: hybrid  # file | tmux | hybrid

  # Graceful stop timeout before offering cancel
  graceful_timeout: 5

  # Feedback verbosity
  feedback: brief

  # Keywords (user can customize)
  keywords:
    stop: ["stop", "halt", "hold on"]
    pause: ["pause", "wait"]
    cancel: ["cancel", "kill it", "abort"]
    redirect: ["actually", "instead", "change that"]
```

## Potential Challenges

1. **STT accuracy for short commands**: "Stop" is one syllable, easy to miss or mishear.
   - Solution: Require slightly longer phrases ("stop worker"), or train on common mishearings

2. **False positives**: User says "don't stop the server" → "stop" detected.
   - Solution: Basic sentence parsing, "don't X" is not a command for X

3. **Worker compliance**: Workers may not check for interrupts often enough.
   - Solution: Strong guidance in worker role, periodic interrupt checks built into agent behavior

4. **Partial work state**: Interrupted workers leave work in unknown state.
   - Solution: Require workers to summarize state on any stop, use graceful stops by default

5. **Race conditions**: Interrupt arrives as worker is naturally finishing.
   - Solution: Idempotent interrupt handling, check if already stopped

6. **Multi-pane ambiguity**: "Stop" with 3 workers running, which one?
   - Solution: Default to most active, require explicit targeting when ambiguous

## Success Criteria

1. Voice-only session control is fully possible (no keyboard for interrupts)
2. Wrong-path workers can be redirected within 10 seconds of recognition
3. "Actually" corrections work without full restart
4. Token waste from wrong-path execution drops measurably
5. Users report feeling "in control" of workers

## Non-Goals

- **Undo support**: Interrupts stop forward progress, don't revert changes
- **Time travel**: Can't interrupt retroactively
- **Predictive interrupts**: System doesn't guess when to interrupt

## Future Extensions

### Voice Priority Levels

Different interrupt urgency:

```
"Stop when you can" → graceful, low priority
"Stop" → normal priority
"Stop now" → immediate, high priority
```

### Interrupt Macros (integrates with voice-macros idea)

```yaml
macros:
  nope:
    interrupt: cancel
    expand: "never mind, let me try something else"

  pivot:
    pattern: "pivot to {approach}"
    interrupt: redirect
    expand: "try {approach} instead of current approach"
```

### Worker-Initiated Interrupts

Workers can request human attention:

```
[Worker]: "I'm stuck on authentication. Interrupt acknowledged,
          but I need clarification: OAuth or session-based?"

[System plays distinct attention tone]

[User]: "Session based"
[Worker continues]
```

This creates a bidirectional interrupt channel.
