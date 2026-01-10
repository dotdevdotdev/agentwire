# Mission: Fix Local Say Command

> **COMPLETED** - January 9, 2026

## Problem (Resolved)

- `remote-say "hello"` → worked (streams to browser via portal)
- `agentwire say "hello"` → didn't play audio locally

## Solution

The issue was that `api_local_tts` was hardcoded to hit `localhost:8100` (expecting a local Chatterbox server) instead of using the configured TTS backend (RunPod).

### Changes Made

1. **`server.py` - `api_local_tts` endpoint**
   - Changed from hitting hardcoded URL to using `self.tts.generate()`
   - Now works with any configured TTS backend (RunPod, Chatterbox, etc.)
   - Plays audio server-side via `afplay` (macOS) or `aplay`/`paplay` (Linux)

2. **`~/.local/bin/say` script**
   - Updated to use portal's `/api/local-tts/{room}` endpoint
   - Removed hardcoded SSH tunnel to dotdev-pc
   - Added multi-source room detection:
     1. `AGENTWIRE_ROOM` env var
     2. `.agentwire.yml` config file
     3. Path inference from `~/projects/{room}`
     4. tmux session name fallback

3. **Smart routing flow:**
   - Check if portal has browser connections for room
   - If yes → send to portal for browser playback
   - If no → use `/api/local-tts` for local speaker playback

## Acceptance Criteria

- [x] `agentwire say "hello"` plays audio through system speakers
- [x] Works via portal's TTS backend (RunPod) - no local GPU needed
- [x] Uses smart routing - plays on browser if connected, local if not
