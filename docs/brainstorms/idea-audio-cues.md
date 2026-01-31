# Audio Cues: Ears-Free Session Awareness

> Distinct audio cues for session events so you don't need to watch the screen.

## Problem

The voice interface frees you from the keyboard, but you're still tethered to the screen:

- **Worker completion**: You watch and wait for workers to finish
- **Errors**: Nothing alerts you when a worker hits an error
- **Idle state**: Did the session go idle? Check the screen.
- **Long operations**: Is it still running or stuck? Have to look.

Current workaround: Stare at the terminal or constantly ask "status check" via voice.

This defeats the purpose of voice-first interaction. You should be able to:
- Step away from the desk
- Work on something else
- Glance at your phone/tablet occasionally
- Know what's happening by sound alone

## Why Voice Alone Isn't Enough

Voice responses (via `agentwire_say`) work for detailed communication, but:

1. **Interruptive** - Voice grabs full attention, breaks flow
2. **Sequential** - Only one message at a time
3. **Verbose** - "Worker 2 has completed" takes 2 seconds to say
4. **Late** - TTS queue adds delay between event and notification

Audio cues are:
- **Glanceable** - Hear, understand, continue what you're doing
- **Instant** - No TTS latency
- **Parallel** - Multiple cues don't conflict
- **Ambient** - Background awareness, not foreground interruption

## Proposed Solution: Semantic Audio Cues

### Event → Sound Mapping

| Event | Sound | Duration | Why This Sound |
|-------|-------|----------|----------------|
| Worker spawned | Rising ping | 200ms | Something new starting |
| Worker completed (success) | Soft chime | 300ms | Pleasant, resolved |
| Worker completed (blocked) | Double knock | 400ms | Needs attention |
| Worker completed (error) | Low thunk | 300ms | Something went wrong |
| Session went idle | Gentle fade-out tone | 500ms | Winding down |
| Session resumed | Subtle whoosh | 200ms | Activity starting |
| Task received | Short click | 100ms | Acknowledgment |
| Interrupt acknowledged | Quick boop | 150ms | Command received |
| All workers done | Victory chord | 600ms | Collective completion |
| Stuck detection | Subtle pulse (repeating) | 800ms loop | Persistent issue |

### Sound Design Principles

1. **Distinct but not jarring** - Each event sounds different but fits a family
2. **Low cognitive load** - After a few sessions, recognition is automatic
3. **Volume-appropriate** - Quieter than voice, audible in background
4. **Aesthetic** - Pleasant enough to hear 50+ times a day
5. **Meaningful defaults** - Work out of the box, customization optional

### Example Session (Audio Only)

```
[User]: "Spawn two workers, one for auth, one for docs"

*ping* (worker 1 spawned)
*ping* (worker 2 spawned)

[User walks away, makes coffee]

*soft chime* (worker 2 finished - docs done)

[User keeps making coffee, knows docs are done]

*double knock* (worker 1 blocked)

[User returns, checks what worker 1 needs]
```

Without audio cues, user would either:
- Stay at desk watching
- Miss the blocked state until manually checking
- Get full voice notifications that interrupt concentration

### Integration with Voice

Audio cues complement, not replace, voice:

```
*double knock* (worker blocked)
[System TTS after 2s if user hasn't responded]:
"Worker 1 blocked. It needs the database schema."
```

Cue provides instant awareness; voice provides detail if needed.

Configure escalation:
```yaml
audio_cues:
  escalate_to_voice:
    worker_blocked: 5s   # If no action in 5s, speak details
    worker_error: 3s     # Errors escalate faster
    stuck_detected: 10s  # Stuck gets more time before nagging
```

## Implementation

### Sound Assets

Store as small audio files (< 50KB each):

```
agentwire/
└── sounds/
    ├── spawn.mp3
    ├── complete-success.mp3
    ├── complete-blocked.mp3
    ├── complete-error.mp3
    ├── idle.mp3
    ├── resumed.mp3
    ├── task-received.mp3
    ├── interrupt-ack.mp3
    ├── all-done.mp3
    └── stuck-pulse.mp3
```

### Playback

**Local playback** (macOS):
```python
import subprocess

def play_cue(event: str):
    sound_path = get_sound_path(event)
    subprocess.Popen(
        ["afplay", "-v", str(VOLUME), sound_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
```

**Browser playback** (portal connected):
```javascript
const audioContext = new AudioContext();
const soundBuffers = {};  // Preloaded

async function playCue(event) {
    const buffer = soundBuffers[event];
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);
    source.start();
}
```

**Routing logic**:
```python
def play_cue(event: str, session: str):
    """Play audio cue, routing to browser if connected."""
    portal = get_portal_connection(session)

    if portal and portal.audio_enabled:
        # Send to browser via WebSocket
        portal.send({"type": "audio_cue", "event": event})
    else:
        # Play locally
        play_local(event)
```

### Event Hooks

Wire into existing event system:

```python
@on_pane_spawn
def cue_spawn(pane: int):
    play_cue("spawn")

@on_worker_idle
def cue_worker_done(pane: int, status: str):
    cue_map = {
        "DONE": "complete-success",
        "BLOCKED": "complete-blocked",
        "ERROR": "complete-error"
    }
    play_cue(cue_map.get(status, "complete-success"))

    # Check if all workers are done
    if not get_active_workers():
        play_cue("all-done")

@on_session_idle
def cue_session_idle():
    play_cue("idle")

@on_stuck_detected
def cue_stuck(pane: int):
    play_cue_loop("stuck-pulse", until="worker_resumed")
```

### WebSocket Messages

Portal broadcasts cue events:

```json
{
    "type": "audio_cue",
    "event": "complete-blocked",
    "pane": 1,
    "timestamp": "2024-01-15T10:30:00Z"
}
```

Browser plays the sound; optionally shows a toast notification too.

### CLI Command

```bash
# Test sounds
agentwire cue test spawn
agentwire cue test complete-success
agentwire cue test all

# List available cues
agentwire cue list

# Adjust volume
agentwire cue volume 0.5  # 50%

# Enable/disable
agentwire cue enable
agentwire cue disable
```

### MCP Tool

```python
@mcp.tool()
def audio_cue(event: str, session: str | None = None) -> str:
    """Play an audio cue.

    Useful for custom workflow signals or testing.

    Args:
        event: Cue name (spawn, complete-success, etc.)
        session: Target session (optional, uses current if in session)
    """
```

## Configuration

```yaml
# In ~/.agentwire/config.yaml
audio_cues:
  enabled: true
  volume: 0.7  # 0.0 - 1.0

  # Route to browser when connected
  prefer_browser: true

  # Escalation to voice
  escalate_to_voice:
    worker_blocked: 5s
    worker_error: 3s
    stuck_detected: 10s

  # Per-event overrides
  events:
    spawn:
      enabled: true
      sound: "spawn.mp3"  # or custom path
    complete-success:
      enabled: true
    complete-blocked:
      enabled: true
    stuck-pulse:
      enabled: false  # Disable stuck pulsing

  # Custom sounds directory
  custom_sounds_dir: "~/.agentwire/sounds/"

  # Quiet hours (no local playback)
  quiet_hours:
    enabled: false
    start: "22:00"
    end: "08:00"
```

## Custom Sound Packs

Users can create themed sound packs:

```
~/.agentwire/sounds/
├── minimal/
│   ├── spawn.mp3
│   ├── complete-success.mp3
│   └── ...
├── retro/
│   ├── spawn.mp3  # 8-bit sounds
│   └── ...
└── zen/
    ├── spawn.mp3  # Soft, meditative
    └── ...
```

Select pack in config:
```yaml
audio_cues:
  pack: "zen"
```

## Visual + Audio Sync

Portal can sync visual indicators with audio:

```javascript
// When audio cue received
function handleAudioCue(event) {
    playCue(event);

    // Sync visual feedback
    switch(event) {
        case "spawn":
            flashPaneIndicator("new");
            break;
        case "complete-blocked":
            flashPaneIndicator("warning");
            showToast("Worker blocked");
            break;
        case "complete-error":
            flashPaneIndicator("error");
            showToast("Worker error");
            break;
    }
}
```

Reinforces audio with visual for users who have sound off.

## Mobile Considerations

When using portal from phone/tablet:

1. **Haptics option** - Vibration patterns instead of or with audio
2. **Notification integration** - System notifications when portal is backgrounded
3. **Bluetooth/AirPods** - Audio routes to connected devices automatically

```yaml
audio_cues:
  mobile:
    haptics: true  # Vibrate on events
    background_notifications: true  # System notifs when backgrounded
```

## Potential Challenges

1. **Audio fatigue**: Too many sounds become noise.
   - Solution: Intelligent debouncing (don't play 5 spawns in 2 seconds), minimal cue set

2. **Sound conflicts**: Multiple events at once sound chaotic.
   - Solution: Priority queue, some events override others, max 2 overlapping

3. **Volume calibration**: Too quiet = miss it, too loud = startling.
   - Solution: Onboarding calibration, easy volume adjust

4. **Browser autoplay policies**: Browsers block audio until user interaction.
   - Solution: Request interaction on portal load, use Web Audio API properly

5. **Remote sessions**: Audio should play where user is, not where session runs.
   - Solution: Already handled - audio routes to connected portal/browser

6. **Accessibility**: Users with hearing differences need alternatives.
   - Solution: Visual indicators as fallback, screen reader announcements

## Success Criteria

1. Users can walk away from screen and still know session state
2. "Status check" voice queries drop (ambient awareness replaces polling)
3. Blocked workers get addressed faster (immediate audio alert)
4. Users report feeling "connected" to sessions without watching
5. Distinct sounds become recognizable within 1-2 sessions

## Non-Goals

- **Full sonification**: Not every keystroke or output line gets a sound
- **Music/ambiance**: Background music while working (different feature)
- **Voice replacement**: Cues supplement voice, don't replace it
- **Recording/history**: No audio logs of what happened

## Future Extensions

### Spatial Audio

With stereo/surround sound:
- Worker 1 sounds slightly left
- Worker 2 sounds center
- Worker 3 sounds slightly right

Position maps to pane position, providing spatial awareness.

### Personalized Cues

Train on user preferences:
- "I always miss the blocked sound" → make it louder/more distinct
- "Spawn sounds are annoying" → make them subtler

### Cue Sequences

Combine cues for complex states:
- Worker blocked → pause → another worker starts = "handed off"
- All workers done + tests pass = "victory fanfare"

### Integration with Focus Apps

Respect system focus modes:
- macOS Focus: Reduce cue volume or defer non-critical
- Do Not Disturb: Queue cues for when focus ends

