# Presence-Aware Sessions

> Sessions adapt behavior based on whether you're actively present or away.

## Problem

AgentWire sessions don't know if you're actually there:

```
# You step away for coffee
Workers: *complete tasks, send voice notifications to empty room*
Workers: *ask questions, wait indefinitely for responses*
Workers: *pile up 15 notifications, overwhelming when you return*

# You come back
[System]: *immediately starts talking mid-notification*
[You]: *have no idea what happened while away*
```

The system treats "at desk, actively listening" the same as "phone in pocket, in a meeting, asleep."

## Why This Matters

1. **Wasted voice output** - TTS plays to empty rooms, wastes resources
2. **Blocked workers** - Workers wait for input from absent user
3. **Notification overload** - Everything piles up, no prioritization
4. **Context loss** - Return to chaos, no summary of what happened
5. **Battery/bandwidth** - Mobile portal streams audio nobody hears

Sessions should be smart about your presence.

## Proposed Solution: Presence States

### 1. Three Presence States

| State | Meaning | Behavior |
|-------|---------|----------|
| **Active** | At desk, engaged | Normal voice, immediate notifications |
| **Monitoring** | Device connected, not engaged | Queue voice, show visual alerts |
| **Away** | Device disconnected/idle | Batch everything, prepare summary |

### 2. Automatic Detection

Presence inferred from signals:

```yaml
presence_signals:
  # Portal connection
  portal_connected: true → at least Monitoring
  portal_disconnected: true → Away

  # Activity recency
  last_voice_input: <5min → Active
  last_voice_input: >15min → Monitoring or Away

  # Browser tab focus
  portal_tab_focused: true → Active
  portal_tab_background: true → Monitoring

  # Push-to-talk usage
  ptt_pressed_recently: true → Active

  # Explicit control
  user_said_away: true → Away
  user_said_back: true → Active
```

### 3. State-Specific Behavior

**Active Mode (default when engaged)**
```
- Voice notifications: Immediate
- Worker questions: Immediate voice
- Progress updates: Voice announcements
- Idle alerts: Normal delivery
```

**Monitoring Mode (connected but not engaged)**
```
- Voice notifications: Queue, show visual toast
- Worker questions: Queue, show notification badge
- Progress updates: Silent, update dashboard
- Idle alerts: Batch into summary
```

**Away Mode (disconnected or explicit)**
```
- Voice notifications: Suppress entirely
- Worker questions: Workers proceed with defaults
- Progress updates: Log only
- Idle alerts: Aggregate for return briefing
- Workers: Continue autonomous work, don't block on input
```

### 4. Return Briefing

When transitioning Away → Active:

```
[You reconnect]
[System]: "Welcome back. While you were away:
          Three workers completed their tasks.
          One worker hit a blocker and needs your input.
          Two new files were created in the auth module.
          Would you like details on any of these?"
```

The briefing is:
- Concise (30 seconds max)
- Prioritized (blockers first, completions, then FYI)
- Actionable (what needs your attention)

### 5. Away Autonomy

Workers behave differently when you're away:

```yaml
away_mode:
  # Don't block on non-critical decisions
  decision_strategy: "use_defaults"

  # Continue work that doesn't need input
  autonomous_continuation: true

  # Skip confirmation prompts
  skip_confirmations: true

  # But still stop on destructive operations
  safety_overrides:
    - "git push"
    - "rm -rf"
    - "deploy"
```

Workers know to keep going, not wait.

### 6. Manual Override

Voice controls:

```
[User]: "I'm stepping away"
[System]: "Got it. I'll queue notifications until you're back."

[User]: "I'm back"
[System]: *Delivers return briefing*

[User]: "Going quiet for an hour"
[System]: "Silent mode for one hour. I'll batch everything."
```

## Implementation Details

### Presence State Machine

```python
class PresenceState(Enum):
    ACTIVE = "active"
    MONITORING = "monitoring"
    AWAY = "away"

class PresenceTracker:
    def __init__(self):
        self.state = PresenceState.ACTIVE
        self.last_activity = datetime.now()
        self.portal_connected = False
        self.tab_focused = False

    def update_signals(self, signals: dict):
        """Update presence based on incoming signals."""
        if signals.get("portal_disconnected"):
            self._transition_to(PresenceState.AWAY)
            return

        if signals.get("voice_input") or signals.get("ptt_pressed"):
            self.last_activity = datetime.now()
            self._transition_to(PresenceState.ACTIVE)
            return

        if signals.get("tab_backgrounded"):
            self._transition_to(PresenceState.MONITORING)
            return

        # Timeout-based transitions
        idle_time = datetime.now() - self.last_activity
        if idle_time > timedelta(minutes=15):
            self._transition_to(PresenceState.MONITORING)
        if idle_time > timedelta(hours=1):
            self._transition_to(PresenceState.AWAY)

    def _transition_to(self, new_state: PresenceState):
        if new_state == self.state:
            return

        old_state = self.state
        self.state = new_state

        if old_state == PresenceState.AWAY and new_state == PresenceState.ACTIVE:
            self._deliver_return_briefing()
```

### Portal WebSocket Messages

```typescript
// Portal → Server: Presence signals
ws.send(JSON.stringify({
  type: "presence_signal",
  signals: {
    tab_focused: document.hasFocus(),
    last_interaction: lastInteractionTimestamp,
    audio_active: isAudioActive
  }
}));

// Server → Portal: Presence state updates
{
  type: "presence_state",
  state: "monitoring",
  queued_count: 3
}
```

### Notification Routing

```python
def route_notification(notification: Notification, presence: PresenceState):
    if presence == PresenceState.ACTIVE:
        # Immediate voice
        tts_speak(notification.message)
        portal_show_toast(notification)

    elif presence == PresenceState.MONITORING:
        # Queue for later, show visual
        queue_notification(notification)
        portal_show_badge(notification.priority)

    elif presence == PresenceState.AWAY:
        # Log only, aggregate for briefing
        log_notification(notification)
        add_to_briefing(notification)
```

### Return Briefing Generator

```python
def generate_briefing(notifications: list[Notification]) -> str:
    """Generate concise return briefing."""

    # Group by type
    completions = [n for n in notifications if n.type == "worker_complete"]
    blockers = [n for n in notifications if n.type == "worker_blocked"]
    file_changes = [n for n in notifications if n.type == "file_created"]

    parts = []

    # Prioritized order
    if blockers:
        parts.append(f"{len(blockers)} worker{'s' if len(blockers) > 1 else ''} "
                    f"hit blockers and need your input.")

    if completions:
        parts.append(f"{len(completions)} worker{'s' if len(completions) > 1 else ''} "
                    f"completed their tasks.")

    if file_changes:
        parts.append(f"{len(file_changes)} new file{'s' if len(file_changes) > 1 else ''} "
                    f"created.")

    return " ".join(parts) + " Would you like details on any of these?"
```

## CLI Commands

```bash
# Check current presence state
agentwire presence status

# Manual override
agentwire presence away
agentwire presence active
agentwire presence quiet 1h  # Silent for duration

# View queued notifications
agentwire presence queue

# Get briefing now (without changing state)
agentwire presence briefing
```

## MCP Tools

```python
@mcp.tool()
def presence_status() -> str:
    """Get current presence state and queued notification count."""

@mcp.tool()
def presence_set(state: str, duration: str | None = None) -> str:
    """Manually set presence state.

    Args:
        state: 'active', 'monitoring', or 'away'
        duration: Optional duration like '1h', '30m' (for away/quiet)
    """

@mcp.tool()
def presence_briefing() -> str:
    """Get summary of notifications since last active period."""
```

## Configuration

```yaml
# In ~/.agentwire/config.yaml
presence:
  # Timeouts for auto-transitions
  active_to_monitoring_timeout: 15m
  monitoring_to_away_timeout: 1h

  # Briefing preferences
  briefing:
    max_duration: 30s  # Keep briefings short
    include_file_details: false  # Just counts, not filenames
    voice_on_return: true  # Speak briefing automatically

  # Away mode behavior
  away_mode:
    workers_continue: true
    skip_confirmations: true
    safety_overrides:
      - git push
      - deploy
      - rm -rf

  # Detection signals to use
  signals:
    portal_connection: true
    tab_focus: true
    voice_activity: true
    timeout_based: true
```

## Example Scenarios

### Coffee Break

```
[10:00] You: "I'm stepping away"
[System]: "Got it, queueing notifications."
[10:05] Worker 1 completes → logged
[10:10] Worker 2 completes → logged
[10:12] Worker 3 asks question → proceeds with default
[10:20] You reconnect
[System]: "Welcome back. Two workers completed.
          One proceeded with defaults on a question.
          All good?"
```

### Meeting

```
[14:00] Portal tab goes to background
[System]: *Auto-transitions to Monitoring*
[14:05] Worker alert → visual badge, no voice
[14:15] Worker complete → silent log
[14:30] Tab refocused
[System]: *Stays Monitoring until activity*
[14:31] You press PTT
[System]: *Transitions to Active*
"You had one worker alert while in monitoring mode."
```

### End of Day

```
[18:00] Portal disconnected, no activity
[System]: *Transitions to Away after timeout*
[18:30] Scheduled task runs → autonomous mode
[19:00] Task completes → logged for tomorrow

[Next morning]
[09:00] Portal connects
[System]: "Good morning. Overnight: scheduled task ran successfully,
          created 3 new documentation files.
          Would you like the summary?"
```

### Mobile Monitoring

```
[Phone portal connected, screen locked]
[System]: *Presence = Monitoring*
[Worker completes]
[System]: *Sends push notification, no voice*
[You unlock phone, look at portal]
[System]: *Still Monitoring (no PTT)*
[You press PTT]: "What's the status?"
[System]: *Transitions to Active, responds normally*
```

## Potential Challenges

1. **False positives**: System thinks you're away when you're watching. Solution: Err toward active/monitoring, use multiple signals.

2. **Delayed recognition**: Takes time to realize you're back. Solution: PTT instantly transitions to Active; other signals use shorter timeouts when recently Away.

3. **Split presence**: Phone says Active, desktop says Away. Solution: Aggregate across devices, any Active wins.

4. **Briefing timing**: Speak while you're still settling in. Solution: Brief pause after reconnect, or visual-first with voice on request.

5. **Privacy concerns**: "Is the system watching me?" Solution: Clear about signals used (connection, focus, activity), no camera/audio monitoring beyond PTT.

## Portal UI Changes

### Presence Indicator

```
┌─────────────────────────────────────┐
│ 🟢 Active           │ Session: api │
│ ⚪ 3 queued         │              │
└─────────────────────────────────────┘
```

Status pill in header:
- 🟢 Active (green)
- 🟡 Monitoring (yellow)
- ⚪ Away (gray)

Queued count badge when > 0.

### Presence Toggle

Quick toggle in UI:

```
[🟢 Active ▾]
├─ 🟢 Active
├─ 🟡 Monitoring
├─ ⚪ Away
└─ ⚪ Away for 1h...
```

### Queue Drawer

Swipe or click to see queued notifications:

```
┌─ Queued Notifications (3) ─────────┐
│ Worker 1: Completed auth task      │
│ Worker 2: Question about types     │
│ System: Session idle for 30min     │
└─ [Clear] [Deliver Now] ────────────┘
```

## Success Criteria

1. Voice doesn't play to empty rooms (wasted TTS calls → 0)
2. Workers don't block waiting for away users (blocked time reduced 80%)
3. Return experience is pleasant, not overwhelming (briefing <30s)
4. Battery life improves on mobile (no continuous audio streaming)
5. Users feel "in control" of notification timing

## Non-Goals

- **Activity tracking/analytics** - Not measuring productivity
- **Physical presence detection** - No camera/sensor integration
- **Forced status** - Always user-overridable
- **Perfect detection** - Erring toward responsive is fine

## Rollout Phases

1. **Phase 1**: Manual presence (`away`/`back` commands)
2. **Phase 2**: Portal connection detection
3. **Phase 3**: Activity timeout transitions
4. **Phase 4**: Tab focus detection
5. **Phase 5**: Return briefing generation
6. **Phase 6**: Worker away-mode autonomy
