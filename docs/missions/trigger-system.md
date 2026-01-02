# Mission: Trigger System

> Real-time MUD-style text matching with configurable actions for tmux output streams.

**Branch:** `mission/trigger-system` (created on execution)

## Context

AgentWire monitors tmux output and reacts to patterns. Currently we poll with `tmux capture-pane` every 0.5s and have two hardcoded patterns (SAY_PATTERN, ASK_PATTERN). This should be:

1. **Real-time** via `tmux pipe-pane` instead of polling
2. **Configurable** triggers instead of hardcoded patterns
3. **Proper abstraction** with SessionWatcher owning the stream

## Design Decisions (Confirmed)

### Output Streaming: `tmux pipe-pane`

Instead of polling `capture-pane`, use `pipe-pane` for real-time output:

```bash
# Create FIFO for session
mkfifo /tmp/agentwire-{session}.pipe

# Pipe tmux output to FIFO
tmux pipe-pane -t {session} 'cat >> /tmp/agentwire-{session}.pipe'

# Watcher reads FIFO (blocks until data arrives)
async for chunk in read_fifo(pipe_path):
    process_triggers(chunk)
```

**Benefits:**
- Zero latency (instant trigger response)
- No CPU waste from constant polling
- Event-driven architecture
- Natural "once per appearance" - each byte flows through once

### Matching Semantics: Once Per Stream Appearance

No deduplication tracking. Each line/match flows through the stream once:
- `say "Hello"` appears → fires
- Same command run again later → fires again (it's a new appearance)
- No cooldowns, no `played_says` sets, no complexity

The stream itself is the dedup mechanism.

### Trigger Modes

| Mode | Matches Against | Use Case |
|------|-----------------|----------|
| **Transient** | Stream chunks as they arrive | `say` commands, errors, one-time messages |
| **Persistent** | Accumulated buffer (last N lines) | AskUserQuestion UI, prompts that stay visible |

For persistent triggers, maintain a rolling buffer of recent output to detect patterns that span multiple chunks or persist on screen.

### Configuration: Inline in config.yaml

```yaml
# ~/.agentwire/config.yaml
triggers:
  # Built-in triggers (can disable, can't remove)
  say_command:
    enabled: true
    # pattern, action defined in code

  ask_question:
    enabled: true

  # User-defined triggers
  build_failed:
    pattern: 'npm ERR!|error:|BUILD FAILED'
    mode: transient
    action: notify
    title: "Build Failed"
    sound: error

  tests_passed:
    pattern: 'All (?P<count>\d+) tests? passed'
    mode: transient
    action: tts
    template: "{count} tests passed!"
```

### Per-Room Overrides

Global triggers in `config.yaml`, room-specific overrides in `rooms.json`:

```json
{
  "my-project": {
    "triggers": {
      "build_failed": { "enabled": false },
      "deploy_alert": {
        "pattern": "Deployed to (?P<url>\\S+)",
        "action": "tts",
        "template": "Deployed!"
      }
    }
  }
}
```

### Multi-Match Behavior

All matching triggers fire. A `say` command inside an AskUserQuestion block triggers both. Composable, no priority complexity.

### Client Scope

When a trigger fires, it broadcasts to **all connected clients** in that room. Everyone sees the popup, everyone hears the TTS. This is the right behavior for:
- Solo use (one client, no issue)
- Presentations (audience sees/hears what's happening)

Per-client triggers or selective broadcasting is a future enhancement if needed.

### Hot Reload

Portal restart required to apply trigger changes. Simple, predictable.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  AgentWireServer                                        │
│  └── rooms: dict[str, Room]                             │
│       └── watcher: SessionWatcher                       │
│            ├── pipe_path: /tmp/agentwire-{session}.pipe │
│            ├── buffer: RollingBuffer (for persistent)   │
│            ├── triggers: list[Trigger]                  │
│            └── actions: dict[str, ActionHandler]        │
└─────────────────────────────────────────────────────────┘

Flow:
1. Room created → SessionWatcher.start()
2. Watcher runs: tmux pipe-pane -t {session} 'cat >> {pipe}'
3. Watcher reads FIFO in async loop
4. Each chunk → run transient triggers
5. Chunk added to buffer → run persistent triggers
6. Matches → fire action handlers
7. Room destroyed → SessionWatcher.stop() → cleanup pipe
```

### Core Classes

```python
# agentwire/watcher.py

@dataclass
class Trigger:
    name: str
    pattern: re.Pattern
    mode: Literal["transient", "persistent"]
    action: str  # "tts", "popup", "notify", "sound", "send_keys", "broadcast"
    config: dict = field(default_factory=dict)
    enabled: bool = True
    builtin: bool = False

class SessionWatcher:
    """Watches a tmux session via pipe-pane, fires triggers."""

    def __init__(self, session: str, triggers: list[Trigger], actions: ActionRegistry):
        self.session = session
        self.triggers = triggers
        self.actions = actions
        self.pipe_path = Path(f"/tmp/agentwire-{session}.pipe")
        self.buffer = RollingBuffer(max_lines=100)
        self._task: asyncio.Task | None = None

    async def start(self):
        """Create FIFO, start pipe-pane, begin watching."""
        self._create_pipe()
        self._start_pipe_pane()
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self):
        """Stop watching, cleanup pipe."""
        if self._task:
            self._task.cancel()
        self._stop_pipe_pane()
        self._cleanup_pipe()

    async def _watch_loop(self):
        """Read from FIFO, process triggers."""
        async with aiofiles.open(self.pipe_path, 'r') as f:
            async for chunk in f:
                await self._process_chunk(chunk)

    async def _process_chunk(self, chunk: str):
        """Run triggers against new content."""
        clean = strip_ansi(chunk)
        self.buffer.append(clean)

        # Transient triggers: match against chunk
        for trigger in self.triggers:
            if trigger.mode == "transient":
                for match in trigger.pattern.finditer(clean):
                    await self._fire(trigger, match)

        # Persistent triggers: match against buffer
        buffer_text = self.buffer.get_text()
        for trigger in self.triggers:
            if trigger.mode == "persistent":
                match = trigger.pattern.search(buffer_text)
                # Track state for appear/disappear
                await self._handle_persistent(trigger, match)

class ActionRegistry:
    """Registry of action handlers."""

    handlers: dict[str, Callable]

    async def fire(self, action: str, trigger: Trigger, match: re.Match, room: Room):
        handler = self.handlers.get(action)
        if handler:
            await handler(trigger, match, room)
```

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - purely code changes.

## Wave 2: Core Watcher Infrastructure

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Create `SessionWatcher` class with pipe-pane lifecycle | `agentwire/watcher.py` |
| 2.2 | Implement FIFO creation/cleanup utilities | `agentwire/watcher.py` |
| 2.3 | Implement async FIFO reading loop | `agentwire/watcher.py` |
| 2.4 | Create `RollingBuffer` for persistent trigger matching | `agentwire/watcher.py` |

## Wave 3: Trigger Engine

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 3.1 | Create `Trigger` dataclass and loading from config | 2.1 |
| 3.2 | Implement transient trigger matching (chunk-based) | 2.1, 2.3 |
| 3.3 | Implement persistent trigger matching (buffer-based, state tracking) | 2.1, 2.4 |
| 3.4 | Create `ActionRegistry` with handler registration | None - starts immediately |

## Wave 4: Action Handlers

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 4.1 | Migrate TTS action from current code | 3.4 |
| 4.2 | Migrate popup action (AskUserQuestion) from current code | 3.4 |
| 4.3 | Add `notify` action (browser notification via WebSocket) | 3.4 |
| 4.4 | Add `send_keys` action (send input back to tmux) | 3.4 |
| 4.5 | Add `broadcast` action (custom WebSocket message) | 3.4 |

## Wave 5: Integration

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 5.1 | Add triggers config section to `config.py` | 3.1 |
| 5.2 | Integrate SessionWatcher into Room lifecycle | 2.1-2.4, 3.1-3.4 |
| 5.3 | Replace `_poll_output` with watcher-based flow | 5.2, 4.1, 4.2 |
| 5.4 | Add per-room trigger overrides via rooms.json | 5.1 |

## Wave 6: Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 6.1 | Add example triggers to config.yaml | 5.1 |
| 6.2 | Document trigger system in CLAUDE.md | 5.3 |
| 6.3 | Handle edge cases (session not found, pipe errors) | 5.3 |
| 6.4 | Add sound action with bundled sounds | 4.3 |

## Completion Criteria

- [ ] SAY_PATTERN behavior preserved (no regression)
- [ ] ASK_PATTERN behavior preserved (no regression)
- [ ] Real-time response (< 50ms latency vs 500ms polling)
- [ ] User can add custom triggers via config.yaml
- [ ] Built-in triggers can be disabled
- [ ] Per-room trigger overrides work
- [ ] At least notify and send_keys actions working

## Edge Cases to Handle

1. **Session doesn't exist**: Watcher should fail gracefully, not crash server
2. **Session ends while watching**: Detect EOF on FIFO, cleanup
3. **Pipe buffer fills**: Shouldn't happen with async reading, but handle backpressure
4. **Multiple watchers same session**: Prevent duplicate pipe-pane commands
5. **ANSI codes in patterns**: Always strip before matching
6. **Regex errors in user patterns**: Catch at config load, log warning, skip trigger

## Future Enhancements (Not in v1)

- **Aliases**: Input rewriting (MUD-style)
- **Variables**: User-defined variables for templates
- **Timers**: Delayed/scheduled actions
- **Webhook action**: HTTP POST for external integrations
- **Script action**: Run shell commands on match
- **Trigger testing**: `/trigger test <pattern>` command
