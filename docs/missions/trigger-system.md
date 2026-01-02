# Mission: Trigger System

> MUD-style text matching with configurable actions for tmux output streams.

**Branch:** `mission/trigger-system` (created on execution)

## Context

AgentWire monitors tmux output and reacts to patterns. Currently we have two hardcoded patterns:
- `SAY_PATTERN` - detects `say "text"` → fires TTS
- `ASK_PATTERN` - detects AskUserQuestion UI → fires popup + TTS

Both follow the same core loop: match pattern → extract variables → fire action. This should be generalized into a configurable trigger system like MUD clients (TinTin++, zMUD).

## Design Decisions

### Matching Semantics: "Once per what?"

Current implementations reveal two distinct trigger types:

| Type | Scans | Tracks | Fires | Use Case |
|------|-------|--------|-------|----------|
| **Transient** | New content only (delta) | Set of unique matches | Once per unique match text | `say` commands, errors, one-time messages |
| **Persistent** | Full output every poll | Current match state | On state change (appear/disappear) | AskUserQuestion, progress bars, prompts |

**Decision:** Support both types via `mode: transient | persistent` config option.

- `transient` (default): Only match new content, track unique matches in set, fire once per unique
- `persistent`: Match full output, track last match, fire on appear, optionally on disappear

### Match Deduplication

For transient triggers, what defines "unique"?

| Option | Example | Pros | Cons |
|--------|---------|------|------|
| Full match text | `say "Hello"` ≠ `say "Hello!"` | Precise | Same message won't repeat |
| Extracted variables | Both fire if text differs | More flexible | Need to hash variables |
| Match + timestamp bucket | 5-min buckets | Allows repeats over time | More complex |

**Decision:** Use extracted variables as the dedup key (what the action sees). This means `say "Hello"` fired twice is one trigger, but the same pattern with different text fires twice.

### Where Triggers Fire (Scope)

| Scope | Meaning | Use Case |
|-------|---------|----------|
| Room | Once per room, all clients see it | TTS (everyone hears), popups |
| Client | Each connected client gets it | Notifications (per-device) |
| Session | Once ever for this tmux session | Welcome messages |

**Decision:** Default to `room` scope. Add `scope: room | client | session` option for advanced cases.

### Configuration Format

```yaml
# ~/.agentwire/triggers.yaml (or inline in config.yaml)
triggers:
  # Built-in triggers (can be disabled, not removed)
  - name: say_command
    builtin: true
    pattern: '(?:remote-)?say\s+(?:"(?P<text>[^"]+)"|''(?P<text2>[^'']+)'')'
    mode: transient
    action: tts
    template: "{text}{text2}"  # Fallback through variables

  - name: ask_question
    builtin: true
    pattern: '\s*☐\s+(?P<header>.+?)\s*\n\s*\n(?P<question>.+?\?)\s*\n\s*\n(?P<options>(?:[❯\s]+\d+\.\s+.+\n(?:\s{3,}.+\n)?)+)'
    mode: persistent
    action: popup
    on_disappear: dismiss  # Special action when pattern leaves
    tts_template: "{question}. {options_formatted}"

  # User-defined triggers
  - name: build_failed
    pattern: 'npm ERR!|error:|BUILD FAILED|FAILED.*\d+ errors?'
    mode: transient
    action: notify
    title: "Build Failed"
    sound: error

  - name: tests_passed
    pattern: 'All (?P<count>\d+) tests? passed|✓ (?P<count>\d+) passing'
    mode: transient
    action: tts
    template: "{count} tests passed!"

  - name: deploy_complete
    pattern: 'Deployed to (?P<url>https://\S+)'
    mode: transient
    action: webhook
    url: "https://hooks.slack.com/..."
    body: '{"text": "Deployed: {url}"}'

  - name: waiting_input
    pattern: '(?P<prompt>.*\?)\s*\[y/N\]'
    mode: persistent
    action: popup
    type: confirm  # Special popup type
```

### Action Types

| Action | Description | Required Config |
|--------|-------------|-----------------|
| `tts` | Speak text via TTS | `template` or uses first capture group |
| `popup` | Show modal in browser | `type: alert | confirm | question` |
| `notify` | Browser notification | `title`, `body` template |
| `sound` | Play audio file | `file` path or `sound: error | success | ping` |
| `webhook` | HTTP POST | `url`, `body` template |
| `broadcast` | Custom WebSocket message | `type`, `data` template |
| `script` | Run shell command | `command` template |

### Variable Extraction

Use Python named capture groups:
```regex
(?P<varname>pattern)
```

Available in templates as `{varname}`. System variables also available:
- `{room}` - room/session name
- `{timestamp}` - ISO timestamp
- `{match}` - full match text
- `{session}` - tmux session name (may differ from room for remote)

### Built-in vs User Triggers

- **Built-in triggers** are always present, can be `enabled: false` but not deleted
- **User triggers** in config file, full control
- **Order matters**: first match wins (user triggers checked before built-in? Or configurable priority?)

**Decision:** Triggers have `priority: int` (default 100). Lower = checked first. Built-ins default to 1000. This lets users override or preempt built-ins.

### Performance

1. **ANSI stripping**: Always strip before matching (already doing this)
2. **Polling**: Current 0.5s poll interval is fine
3. **Regex compilation**: Compile patterns once at config load, not per-poll
4. **Short-circuit**: Stop after first match? Or allow multiple triggers per poll?

**Decision:** Allow multiple triggers per poll (a `say` command inside an `ask` block should fire both). But same trigger can't fire twice per poll.

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - purely code changes.

## Wave 2: Core Trigger Engine

Refactor polling loop to use a trigger engine that handles both existing patterns.

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Create `Trigger` dataclass and `TriggerEngine` class | `agentwire/triggers.py` |
| 2.2 | Implement transient trigger logic (new content, dedup set) | `agentwire/triggers.py` |
| 2.3 | Implement persistent trigger logic (full scan, state tracking) | `agentwire/triggers.py` |
| 2.4 | Create action handlers (tts, popup, broadcast) | `agentwire/triggers.py` |

## Wave 3: Config and Migration

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 3.1 | Add triggers config section to `config.py` | None - starts immediately |
| 3.2 | Migrate SAY_PATTERN to built-in trigger config | 2.1, 2.2 |
| 3.3 | Migrate ASK_PATTERN to built-in trigger config | 2.1, 2.3 |
| 3.4 | Integrate TriggerEngine into `_poll_output` | 2.1-2.4, 3.2, 3.3 |

## Wave 4: Extended Actions

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 4.1 | Add `notify` action (browser notifications via WebSocket) | 3.4 |
| 4.2 | Add `sound` action (play audio files) | 3.4 |
| 4.3 | Add `webhook` action (HTTP POST) | 3.4 |
| 4.4 | Add `script` action (shell command) | 3.4 |

## Wave 5: Documentation and Examples

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 5.1 | Add example triggers to `examples/config.yaml` | 3.1 |
| 5.2 | Document trigger system in CLAUDE.md | 4.1-4.4 |
| 5.3 | Add useful default triggers (build errors, test results) | 3.4 |

## API Design

### TriggerEngine

```python
@dataclass
class Trigger:
    name: str
    pattern: re.Pattern
    mode: Literal["transient", "persistent"]
    action: str
    priority: int = 100
    enabled: bool = True
    builtin: bool = False
    config: dict = field(default_factory=dict)  # Action-specific config

@dataclass
class TriggerState:
    """Per-room state for a trigger."""
    fired_matches: set[str] = field(default_factory=set)  # For transient
    last_match: str | None = None  # For persistent

class TriggerEngine:
    def __init__(self, triggers: list[Trigger], actions: dict[str, ActionHandler]):
        self.triggers = sorted(triggers, key=lambda t: t.priority)
        self.actions = actions
        self.room_state: dict[str, dict[str, TriggerState]] = {}  # room -> trigger_name -> state

    async def process(self, room: str, output: str, old_output: str) -> list[TriggerResult]:
        """Process output through all triggers, return results."""
        clean = strip_ansi(output)
        clean_old = strip_ansi(old_output) if old_output else ""
        new_content = get_new_content(clean, clean_old)

        results = []
        for trigger in self.triggers:
            if not trigger.enabled:
                continue

            state = self._get_state(room, trigger.name)

            if trigger.mode == "transient":
                results.extend(self._process_transient(trigger, state, new_content))
            else:
                results.extend(self._process_persistent(trigger, state, clean))

        return results
```

### Room Integration

```python
class Room:
    trigger_engine: TriggerEngine  # Shared engine
    trigger_state: dict[str, TriggerState]  # Per-room state
```

## Completion Criteria

- [ ] SAY_PATTERN behavior preserved exactly (no regression)
- [ ] ASK_PATTERN behavior preserved exactly (no regression)
- [ ] User can add custom triggers via config
- [ ] Built-in triggers can be disabled
- [ ] At least one new action type working (notify or webhook)
- [ ] Example triggers documented

## Open Questions

1. **Trigger reload**: Hot-reload triggers on config change? Or require portal restart?
2. **Per-room triggers**: Should triggers be configurable per-room? (e.g., different sounds for different projects)
3. **Trigger testing**: Add `/trigger test <pattern>` command to test regex against current output?
4. **Regex safety**: Limit regex complexity to prevent ReDoS? Timeout on pattern match?

## Notes

The MUD analogy is apt. Classic MUD clients have:
- **Triggers**: Pattern → Action (what we're building)
- **Aliases**: User input → Expanded command (could be future feature for input rewriting)
- **Variables**: Named storage (we have system vars, could add user vars)
- **Timers**: Delayed/repeated actions (could be useful for reminders)

Start with triggers, expand based on usage patterns.
