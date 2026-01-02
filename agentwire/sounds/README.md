# Bundled Sounds

Sound files for the `sound` action trigger.

## Planned Sounds

| Name | Purpose |
|------|---------|
| `success` | Build/test passed |
| `error` | Build/test failed |
| `notification` | General alert |
| `done` | Task completed |

## Implementation

Currently, sound playback is handled client-side via browser Audio API.
Sound files will be added here as `.mp3` or `.wav` assets and served
via the portal's static routes.

For now, the client can use Web Audio API beeps or browser-native sounds.
