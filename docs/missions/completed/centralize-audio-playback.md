> Living document. Update this, don't create new versions.

# Mission: Centralize Audio Playback

## Problem

When multiple windows (monitor + chat) are open for the same session, audio plays twice. Each window has its own WebSocket connection to `/ws/{session}`, and both receive the same audio broadcast.

## Mental Model: Device vs Window

**Device/Client** = one portal connection (one browser tab connected to portal)
**Window** = UI element within that device (chat, monitor, terminal, etc.)

The correct behavior:
- **1 device, N windows into same session** → audio plays ONCE on that device
- **M devices, each with windows into same session** → audio plays ONCE PER DEVICE

Each device has ONE audio output. Windows are just different views - they don't each have speakers.

## Current Architecture (BROKEN)

```
Server
  └─ _broadcast(session, {"type": "audio", ...})
       └─ Sends to ALL session.clients (treats each window as separate client)

Device (Browser)
  ├─ DesktopManager ──→ /ws (dashboard only, no audio)
  ├─ SessionWindow ───→ /ws/{session} ──→ receives audio ──→ PLAYS
  └─ ChatWindow ──────→ /ws/{session} ──→ receives audio ──→ PLAYS
                                              ↓
                                    DOUBLE PLAYBACK (same device!)
```

## Root Cause

1. Each window opens its own WebSocket to `/ws/{session}`
2. Server sees them as separate clients in `session.clients`
3. `_broadcast()` sends audio to ALL clients
4. Each window plays independently → same device plays audio N times

## Solution: Device-Level Audio Ownership

### Principle

**DesktopManager owns audio for its device.** Windows are UI - they receive audio messages but forward to their device's DesktopManager. DesktopManager dedupes to ensure one playback per device.

```
Device (Browser)
  └─ DesktopManager (OWNS AUDIO)
       ├─ _playAudio() with deduplication
       └─ One audio output per device

  Windows (just forward to DesktopManager):
  ├─ SessionWindow ──→ receives audio ──→ desktop._playAudio()
  └─ ChatWindow ────→ receives audio ──→ desktop._playAudio()
                              ↓
              DesktopManager dedupes → plays ONCE
```

Multi-device scenario (correct):
```
Device A (laptop)                    Device B (phone)
  └─ DesktopManager A                  └─ DesktopManager B
       └─ plays once                        └─ plays once
```

### Implementation

**1. Desktop Manager - Add Device-Level Deduplication**

```javascript
// desktop-manager.js
class DesktopManager {
    constructor() {
        // ...existing code...
        this._lastAudioHash = null;
        this._lastAudioTime = 0;
    }

    async _playAudio(base64Data, session) {
        if (!base64Data) return;

        // Device-level dedupe: hash first 100 chars + length (fast, sufficient)
        const audioHash = `${base64Data.substring(0, 100)}-${base64Data.length}`;
        const now = Date.now();

        // Skip if same audio within 2 seconds (same device, multiple windows)
        if (audioHash === this._lastAudioHash && (now - this._lastAudioTime) < 2000) {
            console.log('[DesktopManager] Skipping duplicate audio (already playing on this device)');
            return;
        }

        this._lastAudioHash = audioHash;
        this._lastAudioTime = now;

        // ...existing playback code...
    }
}
```

**2. Session Window - Forward to Device's DesktopManager**

```javascript
// session-window.js - Windows don't own audio, forward to device
// Before:
if (msg.type === 'audio' && msg.data) {
    this._playAudio(msg.data);  // WRONG: window playing audio
}

// After:
if (msg.type === 'audio' && msg.data) {
    desktop._playAudio(msg.data, this.sessionId);  // Forward to device
}
```

Remove the `_playAudio()` method from SessionWindow entirely - windows don't have speakers.

**3. Chat Window - Already Correct**

Chat window already forwards to `desktop._playAudio()` - no changes needed.

### Files to Modify

| File | Change |
|------|--------|
| `agentwire/static/js/desktop-manager.js` | Add `_lastAudioHash`, `_lastAudioTime`, dedupe logic in `_playAudio()` |
| `agentwire/static/js/session-window.js` | Change `this._playAudio()` → `desktop._playAudio()`, remove `_playAudio()` method |

### Testing

**Single device, multiple windows:**
1. Open monitor window for session "anna"
2. Open chat window for session "anna"
3. Trigger TTS
4. Verify audio plays ONCE
5. Console: "[DesktopManager] Skipping duplicate audio (already playing on this device)"

**Multiple devices (if available):**
1. Open portal on laptop, open chat for "anna"
2. Open portal on phone, open monitor for "anna"
3. Trigger TTS
4. Verify audio plays on BOTH devices (once each)

### Benefits

- **Correct behavior**: One audio output per device, regardless of window count
- **Performance**: Reduced audio decoding, single AudioContext per device
- **Clarity**: Windows are UI views, DesktopManager owns device resources

## Status

- [ ] Add dedupe logic to desktop-manager.js
- [ ] Change session-window.js to forward audio
- [ ] Remove session-window.js `_playAudio()` method
- [ ] Test single device with multiple windows
- [ ] Test multiple devices (if available)
- [ ] Commit and push
