# Mission: Task Completion Notifications

> Sound and visual alerts when sessions complete long-running tasks.

## Objective

Notify the user when a Claude session finishes working on a task, so they don't have to constantly watch the terminal. Supports both sound and visual cues in the portal.

## Concept

When Claude goes from "working" to "idle":
- Play a notification sound in the browser
- Visual indicator on the room (badge, color change)
- Optional: Browser notification if tab is in background

Detection: Session output stops for N seconds after activity.

## Wave 1: Human Actions (BLOCKING)

- [ ] Decide on notification sound (chime, ding, custom?)
- [ ] Decide on idle threshold (5s? 10s? configurable?)

## Wave 2: Detection Logic

### 2.1 Activity tracking in server
- Track last output timestamp per session
- Detect transition from "active" to "idle"
- Configurable idle threshold (default 10s)

### 2.2 State machine for session activity
- States: IDLE, ACTIVE, AWAITING_INPUT
- Transitions trigger events
- Broadcast state changes via WebSocket

## Wave 3: Portal Notifications

### 3.1 Sound notification
- Play sound when session goes ACTIVE -> IDLE
- User preference to enable/disable
- Volume control or mute option

### 3.2 Visual notification
- Room card shows "Done" badge briefly
- Orb pulses or changes color
- Tab title updates (e.g., "✓ agentwire - Done")

### 3.3 Browser notification (optional)
- Request notification permission
- Show system notification if tab not focused
- Click notification to focus room

## Wave 4: Configuration

### 4.1 User preferences
- Enable/disable sound
- Enable/disable browser notifications
- Idle threshold adjustment
- Per-room notification settings

### 4.2 Persist preferences
- Store in localStorage
- Sync to rooms.json for per-room settings

## Completion Criteria

- [ ] Sound plays when task completes
- [ ] Visual indicator shows completion
- [ ] Works when portal tab is in background
- [ ] User can mute/adjust notifications
- [ ] Idle threshold is configurable

## Technical Notes

Current orb states:
- Ready (green) - idle
- Listening (yellow) - recording voice
- Processing (purple) - transcribing or working
- Speaking (green pulse) - TTS playing

New consideration:
- "Done" state = brief notification state after ACTIVE -> IDLE
- Could flash orb or show checkmark overlay
- Auto-returns to Ready after 3s
