# Mission: Connection-Aware TTS Routing

> Living document. Update this, don't create new versions.

**Status:** Complete (tested January 9, 2026)
**Branch:** `mission/connection-aware-tts-routing`
**PR:** https://github.com/dotdevdotdev/agentwire/pull/17
**Created:** 2026-01-07

## Goal

Make the `say` command intelligently route TTS based on portal connection status:
- If portal has active WebSocket connections for the room → Route to portal (browser playback)
- Otherwise → Route to local speakers (via afplay/aplay)

This ensures audio always goes somewhere useful - browser when you're watching, speakers when you're not.

## Implementation

The `say` command (via portal HTTP APIs) checks connection status before routing:
- Room detected + portal connections active → Browser playback
- Room detected + no portal connections → Local speaker playback
- No room detected → Local speaker playback (always works)

---

## Architecture

```
say "Hello" (bash command)
    ↓
Room Detection (priority order):
  1. --room argument
  2. AGENTWIRE_ROOM env var
  3. .agentwire.yml config
  4. Path inference (~/projects/{room})
  5. tmux session name
    ↓
Portal HTTP API: GET /api/rooms/{room}/connections
    ↓
┌──────────────────────────────┬─────────────────────────────────┐
│ has_connections = true       │ has_connections = false/timeout │
│ → POST /api/say/{room}       │ → POST /api/local-tts/{room}    │
│ → Portal broadcasts to       │ → Portal generates TTS and      │
│    browser via WebSocket     │    plays via afplay/aplay       │
└──────────────────────────────┴─────────────────────────────────┘
```

## Portal Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/rooms/{room}/connections` | Check if browser connected to room |
| `POST /api/say/{room}` | Generate TTS, broadcast to browser via WebSocket |
| `POST /api/local-tts/{room}` | Generate TTS, play on server speakers |

## Testing Results (January 9, 2026)

- [x] Test 1: Portal with active connections → browser playback ✓
  - Tablet connected to tts-test@local room
  - `say "Hello from tts-test"` played on tablet browser
- [x] Test 2: Portal with no connections → local speaker playback ✓
  - agentwire room had no browser connections
  - `say "Hello from agentwire"` played on Mac speakers
- [x] Test 3: Smart routing correctly detected connections per room ✓
- [x] Test 4: Path inference for room detection ✓
  - `cd ~/projects/tts-test && say "test"` correctly inferred room

## Key Files

| File | Purpose |
|------|---------|
| `agentwire/server.py` | Portal endpoints: `/api/rooms/{room}/connections`, `/api/say/{room}`, `/api/local-tts/{room}` |
| `agentwire/__main__.py` | `say` CLI command implementation |

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Portal down | Falls back to local speakers |
| Connection check times out (>3s) | Falls back to local speakers |
| Multiple connections to same room | Uses browser playback |
| Local playback fails | Return error |
| Room not detected | Uses local playback |

---

## Historical Note

This mission was originally planned around an MCP server architecture (`agentwire/mcp/`, `tts_router.py`, `session_detector.py`). That approach was never fully wired to the CLI and was removed in Wave 8 cleanup. The actual implementation uses the bash `say` command with portal HTTP APIs, which provides the same smart routing functionality.
