# Mission: Fix Local Say Command

> `agentwire say` (local audio playback) doesn't work, only `remote-say` works.

## Problem

- `remote-say "hello"` → works (streams to browser via portal)
- `agentwire say "hello"` → doesn't play audio locally

## Investigation Needed

1. Check how local say is supposed to work
2. Is it trying to play via system audio?
3. Does it need the TTS tunnel to generate audio first?
4. Audio device configuration issue?

## Likely Causes

- TTS generates audio but playback fails
- Wrong audio output device
- Missing audio playback dependency
- macOS permission issue

## Acceptance Criteria

- [ ] `agentwire say "hello"` plays audio through system speakers
- [ ] Works without portal running (direct TTS → local playback)
- [ ] Uses configured audio output device if specified
