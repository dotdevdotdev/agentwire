# Mission: Connection-Aware TTS Routing

> Living document. Update this, don't create new versions.

**Status:** Complete (tested January 9, 2026)
**Branch:** `mission/connection-aware-tts-routing`
**PR:** https://github.com/dotdevdotdev/agentwire/pull/17
**Created:** 2026-01-07

## Goal

Make the MCP `speak()` tool intelligently route TTS based on portal connection status:
- If portal has active WebSocket connections for the session → Route to portal (browser playback)
- Otherwise → Route to daemon (local speaker playback via afplay/aplay)

This ensures audio always goes somewhere useful - browser when you're watching, speakers when you're not.

## Current Behavior

MCP `speak()` tries portal first, falls back to chatterbox backend if portal unavailable. This means:
- Audio plays in browser even if no one is listening
- No local speaker fallback when portal is up but unwatched

## Desired Behavior

MCP `speak()` checks portal connection status before routing:
- Session detected + portal connections active → Browser playback
- Session detected + no portal connections → Local speaker playback
- No session detected → Local speaker playback (always works)

---

## Wave 1: Foundation (API + Routing Logic)

**No human actions required** - All code changes.

### Architecture Decisions

- **MCP → Portal for everything**: MCP server calls portal endpoints for both connection checking and playback (browser or local)
- **Portal endpoints**:
  - GET `/api/rooms/{room}/connections` → check browser connections
  - POST `/api/say/{room}` → browser playback (existing)
  - POST `/api/local-tts/{room}` → local speaker playback (new)
- **Timeouts**:
  - Connection check: 3 seconds
  - TTS generation + playback: 30 seconds (existing behavior)
- **Error handling**: Local playback failure → return error, don't retry portal

### Tasks

- [x] **1.1: Add portal API endpoints**
  - File: `agentwire/server.py`
  - Add `GET /api/rooms/{room}/connections` endpoint
    - Returns: `{"has_connections": bool, "connection_count": int}`
    - Check if room exists in `active_websockets` dict
    - Add to API routes alongside existing `/api/say/{room}`
  - Add `POST /api/local-tts/{room}` endpoint
    - Takes: `{"text": str, "voice": Optional[str]}`
    - Generates TTS via chatterbox backend (use network context for URL)
    - Plays locally via `afplay` (macOS) or `aplay` (Linux)
    - Returns: `{"success": bool, "error": Optional[str]}`
    - Reuse logic from `agentwire/__main__.py:_local_say()`

- [x] **1.2: Update TTSRouter with connection-aware logic**
  - File: `agentwire/tts_router.py`
  - Add `_check_portal_connections(session: str) -> bool` method
    - Calls `GET /api/rooms/{session}/connections` with 3 second timeout
    - Returns True if has_connections, False if no connections or timeout
    - Handle errors gracefully (timeout/connection refused → assume no connections)
  - Update `speak()` method routing logic:
    ```python
    if session and await self._check_portal_connections(session):
        # Route to portal browser playback
        await self.portal_client.speak(text, voice, session)  # POST /api/say/{room}
    else:
        # Route to local speaker playback
        await self.portal_client.speak_local(text, voice, session)  # POST /api/local-tts/{room}
    ```
  - Update `TTSResult` to distinguish between "portal" and "local" methods

- [x] **1.3: Update PortalClient for local playback**
  - File: `agentwire/tts_router.py`
  - Add `speak_local()` method to `PortalClient`
  - POSTs to `/api/local-tts/{room}` endpoint
  - 30 second timeout for TTS generation + playback
  - Returns success/error status

---

## Wave 2: Integration + Testing

### Tasks

- [x] **2.1: Update MCP server integration**
  - File: `agentwire/mcp/server.py`
  - Verify integration works with updated TTSRouter
  - Test session detection + routing logic
  - Ensure error handling for all paths

- [x] **2.2: Test routing paths** (Tested January 9, 2026)
  - Test 1: Portal with active connections → browser playback ✓
    - Tablet connected to tts-test@local room
    - `say "Hello from tts-test"` played on tablet browser
  - Test 2: Portal with no connections → local speaker playback ✓
    - agentwire room had no browser connections
    - `say "Hello from agentwire"` played on Mac speakers
  - Test 3: Portal running, connections check works ✓
    - Smart routing correctly detected connections per room
  - Test 4: Path inference for room detection ✓
    - `cd ~/projects/tts-test && say "test"` correctly inferred room

- [x] **2.3: Local machine testing** (Tested January 9, 2026)
  - Portal running locally (--dev mode) with RunPod TTS backend
  - Local playback via `/api/local-tts` uses `self.tts.generate()` (RunPod)
  - Audio plays via `afplay` on macOS

---

## Completion Criteria

- [x] Portal API endpoints added:
  - [x] GET `/api/rooms/{room}/connections` returns connection status
  - [x] POST `/api/local-tts/{room}` plays audio on server speakers (uses configured TTS backend)
- [x] Smart routing checks connections before routing
- [x] `say` command routes intelligently based on connection status
- [x] All test scenarios pass (local testing complete)
- [x] No regressions in existing TTS functionality
- [x] Local playback works via RunPod backend (no local GPU needed)

---

## Implementation Notes

### Key Files

| File | Changes |
|------|---------|
| `agentwire/server.py` | Add 2 endpoints: `/api/rooms/{room}/connections` + `/api/local-tts/{room}` |
| `agentwire/tts_router.py` | Add connection checking + `speak_local()` to PortalClient |
| `agentwire/mcp/server.py` | Integration verification |

### Architecture

```
MCP speak() call
    ↓
SessionDetector (auto-detect tmux session)
    ↓
TTSRouter.speak()
    ↓
PortalClient.check_connections() → GET /api/rooms/{room}/connections (3s timeout)
    ↓
┌──────────────────────────────┬─────────────────────────────────┐
│ has_connections = true       │ has_connections = false/timeout │
│ → POST /api/say/{room}       │ → POST /api/local-tts/{room}    │
│ → Portal broadcasts to       │ → Portal generates TTS via      │
│    browser via WebSocket     │    chatterbox and plays via     │
│                              │    afplay/aplay on server       │
└──────────────────────────────┴─────────────────────────────────┘

Remote machines (dotdev-pc):
- MCP server runs on remote machine
- Portal endpoints called via local machine (where user is)
- /api/local-tts plays on remote machine speakers
- TTS backend accessed via tunnel (localhost:8100 → dotdev-pc:8100)
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Portal down (connection refused) | Falls back to local speakers (safe default) |
| Connection check times out (>3s) | Falls back to local speakers (safe default) |
| Multiple connections to same room | Uses browser playback (expected) |
| Local playback fails (no audio device) | Return error, don't retry portal (fail explicitly) |
| Remote machine with no portal URL | Uses localhost portal, which would fail → local playback |
| Session not detected | Uses local playback (no connection to check) |

---

## Related Issues

- Closes: (none - proactive feature)
- Related to: MCP server setup (completed 2026-01-07)
- Depends on: TTS service running on dotdev-pc (already set up)

---

## Testing Plan

### Manual Testing

**Prerequisites:**
- Portal running: `agentwire portal start`
- TTS service on dotdev-pc running
- Tunnel active: `agentwire tunnels status`

**Test 1: Browser playback (has connections)**
```bash
# 1. Open portal in browser: https://localhost:8765
# 2. Navigate to room for this session (agentwire-mcp-server)
# 3. In Claude session, call:
speak("Testing browser playback with active connection")
# Expected: Audio plays in browser
# Check portal logs: "method: portal" or check /api/say/{room} was called
```

**Test 2: Local playback (no connections)**
```bash
# 1. Close portal browser tab (or navigate away from room)
# 2. In Claude session, call:
speak("Testing local speaker playback with no connection")
# Expected: Audio plays on local machine speakers (afplay)
# Check portal logs: "method: local" or check /api/local-tts/{room} was called
```

**Test 3: Portal unreachable (connection refused)**
```bash
# 1. Stop portal: agentwire portal stop
# 2. In Claude session, call:
speak("Testing fallback when portal is down")
# Expected: Audio plays on local speakers after connection check fails
# MCP server should log connection error, then fallback to local
```

**Test 4: Connection timeout (slow portal)**
```bash
# 1. Simulate slow portal by adding artificial delay to connection check endpoint
# 2. In Claude session, call:
speak("Testing timeout fallback after 3 seconds")
# Expected: Audio plays on local speakers after 3 second timeout
# MCP logs should show timeout, then fallback
```

**Test 5: Remote machine (dotdev-pc)**
```bash
# 1. SSH to dotdev-pc
# 2. Start Claude session in tmux
# 3. Ensure MCP server registered
# 4. With no portal connection to that room, call:
speak("Testing remote machine local playback")
# Expected: Audio plays on dotdev-pc speakers (not local machine)
# Verify TTS backend accessed via tunnel
```

### Success Criteria

- All 5 tests play audio at expected location
- Routing decisions logged correctly (portal vs local)
- No errors or crashes
- Connection check completes within 3 seconds (or times out appropriately)

---

## Migration Notes

**No breaking changes:**
- Existing MCP tool signature unchanged
- Portal API backward compatible (new endpoint only)
- Falls back gracefully if connection check fails

**User impact:**
- Improved UX: audio goes where user is paying attention
- No configuration changes required
- Works transparently after upgrade
