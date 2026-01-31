# Voice Handoff: Seamless Device Continuity

> Automatically route voice I/O to whichever device you're actively using.

## Problem

You start a coding session at your desk, talking to an orchestrator through your desktop browser. You step away to grab coffee, pull out your phone to check progress, and now you're awkwardly managing two browser tabs - one on desktop (still connected), one on mobile (where you actually are).

Current behavior:
- Each device connects independently to the portal
- Audio routes to wherever it was last configured
- No awareness of which device you're actually using
- Manual reconnection required when switching contexts

This friction discourages the mobile-first, ambient computing style AgentWire enables.

## Proposed Solution

**Voice presence detection** - the system tracks which device most recently captured voice input and routes TTS output there automatically.

### Core Mechanics

1. **Presence signal**: When a device captures push-to-talk audio, it sends a presence heartbeat
2. **Active device tracking**: Portal maintains `active_device_id` per session
3. **Smart routing**: `agentwire_say()` routes to the active device, falling back to all connected devices if none recently active
4. **Graceful handoff**: 30-second presence timeout before falling back

### API Changes

```python
# WebSocket message from client after PTT capture
{
    "type": "voice_presence",
    "device_id": "iphone-14-pro",
    "device_name": "iPhone (Kitchen)",  # User-friendly name
    "timestamp": 1706745600
}

# Server tracks per session
session.active_device = {
    "id": "iphone-14-pro",
    "name": "iPhone (Kitchen)",
    "last_seen": datetime.now()
}

# TTS routing logic
def route_tts(session, audio):
    if session.active_device and not expired(session.active_device):
        send_to_device(session.active_device.id, audio)
    else:
        broadcast_to_all(session, audio)
```

### UI Indicators

- Small device icon in portal header showing active device
- "Listening on: iPhone (Kitchen)" status line
- Optional notification when handoff occurs: "Voice moved to desktop"

### Explicit Handoff Command

For cases where automatic detection isn't enough:

```
[User on phone]: "Move to desktop"
[System]: Routes future audio to last-seen desktop device
```

Or in the portal UI: "Take over voice" button that claims active device status.

## Implementation Considerations

### Device Identification

Options for generating stable device IDs:
1. **Browser fingerprint** - localStorage UUID, persists across sessions
2. **User-provided names** - "Name this device" prompt on first connect
3. **Hybrid** - auto-generate ID, let users set friendly names

Recommend: Auto UUID + optional user naming. Show device type icon (phone/tablet/desktop) based on user agent.

### Network Latency

Different devices have different network characteristics:
- Desktop on ethernet: low latency
- Phone on WiFi: medium latency
- Phone on cellular: high latency

Consider adding latency estimation and adjusting TTS streaming accordingly (buffer more on high-latency connections).

### Multi-User Scenarios

If multiple people access the same session:
- Each user gets their own `user_id` + `device_id` pair
- Voice presence is per-user, not per-session
- TTS can optionally broadcast to all users or route per-speaker

Initial implementation: Single-user focus. Multi-user is a later enhancement.

### Privacy

Voice presence signals contain:
- Device ID (random UUID)
- Device type (from user agent)
- Timestamp

No location data, no audio fingerprinting. Users can disable presence tracking in settings.

## Potential Challenges

1. **Presence race conditions**: Two devices with push-to-talk pressed simultaneously. Solution: Last-write-wins with timestamp comparison.

2. **Stale presence**: User leaves phone in another room, it stays "active". Solution: 30-second timeout, configurable per-user.

3. **Audio continuation**: Mid-sentence TTS when handoff occurs. Solution: Don't interrupt active audio, apply handoff to next utterance.

4. **Bluetooth complications**: User on phone but audio routed to desktop bluetooth speaker. This is actually fine - presence follows input device, user controls output routing at OS level.

5. **Testing complexity**: Need to simulate multi-device scenarios in development. Consider adding `--simulate-device` flag for testing handoff logic.

## Success Metrics

- Reduced manual reconnection events
- Increased mobile portal usage
- User feedback on "seamlessness" of multi-device workflows

## Related Work

- Apple's Handoff between Mac/iPhone
- Spotify Connect (audio follows you)
- Chrome's tab sync (different problem, similar UX expectation)
