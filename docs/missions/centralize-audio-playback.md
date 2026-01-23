> Living document. Update this, don't create new versions.

# Mission: Centralize Audio Playback

## Problem

When multiple windows (monitor + chat) are open for the same session, audio plays twice. Each window has its own WebSocket connection to `/ws/{session}`, and both receive the same audio broadcast.

## Current Architecture

```
Server
  └─ _broadcast(session, {"type": "audio", ...})
       └─ Sends to ALL session.clients

Client WebSocket Connections:
  /ws                    → DesktopManager (dashboard updates only, NO audio)
  /ws/{session}          → SessionWindow (monitor/terminal)
  /ws/{session}          → ChatWindow (same endpoint!)

Audio Flow (CURRENT - BROKEN):
  Server broadcasts audio to session.clients
       ↓
  SessionWindow receives → this._playAudio()     → PLAYS
  ChatWindow receives    → desktop._playAudio()  → PLAYS
       ↓
  DOUBLE PLAYBACK
```

## Root Cause

1. Both SessionWindow and ChatWindow connect to `/ws/{session}`
2. Both are added to `session.clients` on the server
3. `_broadcast()` sends audio to ALL clients
4. Each window plays the audio independently

## Solution: Centralized Audio with Deduplication

### Principle

Desktop manager owns ALL audio playback. Windows forward audio to desktop manager but never play directly. Desktop manager dedupes by audio hash to prevent double playback.

### Implementation

**1. Desktop Manager - Add Deduplication**

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

        // Dedupe: hash first 100 chars + length (fast, sufficient)
        const audioHash = `${base64Data.substring(0, 100)}-${base64Data.length}`;
        const now = Date.now();

        // Skip if same audio within 2 seconds
        if (audioHash === this._lastAudioHash && (now - this._lastAudioTime) < 2000) {
            console.log('[DesktopManager] Skipping duplicate audio');
            return;
        }

        this._lastAudioHash = audioHash;
        this._lastAudioTime = now;

        // ...existing playback code...
    }
}
```

**2. Session Window - Forward to Desktop Manager**

```javascript
// session-window.js - CHANGE
// Before:
if (msg.type === 'audio' && msg.data) {
    this._playAudio(msg.data);
}

// After:
if (msg.type === 'audio' && msg.data) {
    desktop._playAudio(msg.data, this.sessionId);
}
```

Also remove the `_playAudio()` method from SessionWindow entirely.

**3. Chat Window - Already Correct**

Chat window already calls `desktop._playAudio()` - no changes needed.

### Files to Modify

| File | Change |
|------|--------|
| `agentwire/static/js/desktop-manager.js` | Add `_lastAudioHash`, `_lastAudioTime`, dedupe logic in `_playAudio()` |
| `agentwire/static/js/session-window.js` | Change `this._playAudio()` → `desktop._playAudio()`, remove `_playAudio()` method |

### Testing

1. Open monitor window for session "anna"
2. Open chat window for session "anna"
3. Trigger TTS (e.g., send prompt that causes voice response)
4. Verify audio plays ONCE, not twice
5. Console should show "[DesktopManager] Skipping duplicate audio" for second receive

### Performance Benefit

- Reduced audio decoding (only decode once)
- Reduced AudioContext usage
- Cleaner separation of concerns

## Status

- [ ] Add dedupe logic to desktop-manager.js
- [ ] Change session-window.js to forward audio
- [ ] Remove session-window.js `_playAudio()` method
- [ ] Test with monitor + chat windows open
- [ ] Commit and push
