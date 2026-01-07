# Mission: Connection-Aware TTS Routing

> Living document. Update this, don't create new versions.

**Status:** Active
**Branch:** `mission/connection-aware-tts-routing`
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

### Tasks

- [ ] **1.1: Add portal API endpoint for connection checking**
  - File: `agentwire/server.py`
  - Add `GET /api/rooms/{room}/connections` endpoint
  - Returns: `{"has_connections": bool, "connection_count": int}`
  - Check if room exists in `active_websockets` dict
  - Add to API routes alongside existing `/api/say/{room}`

- [ ] **1.2: Update TTSRouter with connection-aware logic**
  - File: `agentwire/tts_router.py`
  - Add `_has_portal_connections(session: str) -> bool` method
  - Calls portal API endpoint to check connections
  - Update `speak()` method routing logic:
    ```python
    if session and await self._has_portal_connections(session):
        # Route to portal (browser)
    else:
        # Route to daemon (local speakers)
    ```
  - Handle connection check failures gracefully (assume no connections)

- [ ] **1.3: Implement DaemonClient for local playback**
  - File: `agentwire/tts_router.py` (new class)
  - Create `DaemonClient` class similar to `PortalClient`
  - Generates TTS via chatterbox backend
  - Plays locally via `afplay` (macOS) or `aplay` (Linux)
  - Reuse logic from `agentwire/__main__.py:_local_say()`
  - Returns success/failure status

---

## Wave 2: Integration + Testing

### Tasks

- [ ] **2.1: Wire up DaemonClient in TTSRouter**
  - File: `agentwire/tts_router.py`
  - Initialize `DaemonClient` in `TTSRouter.__init__`
  - Update `speak()` to use daemon when no portal connections
  - Update `TTSResult` to include `"daemon"` as a method option

- [ ] **2.2: Update MCP server integration**
  - File: `agentwire/mcp/server.py`
  - Verify integration works with updated TTSRouter
  - Test session detection + routing logic
  - Ensure error handling for all paths

- [ ] **2.3: Test both routing paths**
  - Test 1: Portal with active connections → browser playback
  - Test 2: Portal with no connections → local speaker playback
  - Test 3: Portal unreachable → local speaker playback
  - Test 4: No session detected → local speaker playback
  - Document test results in this mission file

---

## Completion Criteria

- [x] Portal API endpoint returns connection status per room
- [x] TTSRouter checks connections before routing
- [x] DaemonClient plays audio locally when no portal connections
- [x] MCP `speak()` tool routes intelligently based on connection status
- [x] All four test scenarios pass
- [x] No regressions in existing TTS functionality

---

## Implementation Notes

### Key Files

| File | Changes |
|------|---------|
| `agentwire/server.py` | Add `/api/rooms/{room}/connections` endpoint |
| `agentwire/tts_router.py` | Add connection checking + DaemonClient |
| `agentwire/mcp/server.py` | Integration verification |
| `agentwire/mcp/tools.py` | Update TOOL_SPEAK description (optional) |

### Architecture

```
MCP speak() call
    ↓
SessionDetector (get tmux session)
    ↓
TTSRouter.speak()
    ↓
Check portal connections
    ↓
┌─────────────────────┬──────────────────────┐
│ Has connections?    │ No connections?      │
│ → PortalClient      │ → DaemonClient       │
│ → POST /api/say/    │ → Generate TTS       │
│ → Browser playback  │ → Play via afplay    │
└─────────────────────┴──────────────────────┘
```

### Edge Cases

- Portal down but would have connections → Falls back to daemon (expected)
- Multiple connections to same room → Uses portal (expected)
- Connection check times out → Falls back to daemon (safe default)
- Daemon fails (no audio device) → Return error, don't retry portal

---

## Related Issues

- Closes: (none - proactive feature)
- Related to: MCP server setup (completed 2026-01-07)
- Depends on: TTS service running on dotdev-pc (already set up)

---

## Testing Plan

### Manual Testing

1. **Browser playback test:**
   ```
   # In portal, open room for this session
   speak("Testing browser playback")
   # Should hear in browser
   ```

2. **Local speaker test:**
   ```
   # Close portal browser tab
   speak("Testing local playback")
   # Should hear on local speakers
   ```

3. **Fallback test:**
   ```
   # Stop portal: agentwire portal stop
   speak("Testing fallback")
   # Should hear on local speakers
   ```

4. **No session test:**
   ```
   # Start Claude Code outside tmux (or mock no session)
   speak("Testing non-tmux")
   # Should hear on local speakers
   ```

### Success Criteria

All four tests play audio successfully with correct routing method logged.

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
