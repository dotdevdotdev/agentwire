# Mission: Session Activity Status

> Show which sessions are actively processing vs idle on the dashboard.

## Objective

Let users see at a glance which sessions are actively outputting vs idle/waiting. Dashboard shows activity status per session. Optional sound notification when a session goes idle.

## Concept

**Detection**: Track output timestamps per session. If no output for N seconds after activity, session is "idle".

**Display**: Dashboard session cards show activity status:
- 🟢 Active - output received in last N seconds
- ⚪ Idle - no recent output, waiting for input

**Notification** (optional): Sound/visual when session transitions active → idle.

## Wave 1: Human Actions (BLOCKING)

- [ ] Decide on idle threshold (5s? 10s? configurable?)

## Wave 2: Server-Side Tracking

### 2.1 Activity tracking per session
- Track `last_output_timestamp` per session in server
- Update on each output chunk received
- Calculate "active" vs "idle" based on threshold

### 2.2 Broadcast activity status
- Include activity status in session list API response
- WebSocket event when session transitions active ↔ idle
- `{"type": "session_activity", "session": "foo", "active": false}`

## Wave 3: Dashboard Display

### 3.1 Session card activity indicator
- Show 🟢 dot for active sessions (output in last N seconds)
- Show ⚪ dot for idle sessions
- Animate dot or pulse when transitioning

### 3.2 Real-time updates
- WebSocket listener updates session cards live
- No polling needed - push updates

## Wave 4: Optional Sound Notification

### 4.1 Sound on idle transition
- Play subtle sound when session goes active → idle
- Only if user has sound enabled (toggle in UI)
- Store preference in localStorage

## Completion Criteria

- [ ] Dashboard shows active/idle status per session
- [ ] Status updates in real-time via WebSocket
- [ ] Optional sound when session goes idle
- [ ] Threshold is configurable (default 10s)

## Technical Notes

We already stream output via WebSocket. Just need to:
1. Track timestamps server-side
2. Add status to session list response
3. Emit events on transitions
4. Update dashboard UI to show status
