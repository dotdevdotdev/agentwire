# Desktop Audio Layer

> Add push-to-talk (PTT) functionality to session windows in the desktop portal.

## Context

The desktop portal now has full terminal access to sessions via WinBox windows. Next step is adding voice input capabilities - a PTT button per session window that records → transcribes → sends to that specific session.

### Key Decisions

- **One PTT button per session window** (not global) - sends to that session
- **Floating in bottom-right corner** inside the window
- **Uses existing infrastructure** - whisperkit-cli for STT, `agentwire send` for delivery
- **Browser-based recording** - MediaRecorder API, POST to backend for transcription

### Architecture

```
User holds PTT button
    ↓
Browser: MediaRecorder captures audio (WebM/Opus)
    ↓
POST /api/transcribe with audio blob
    ↓
Backend: Save temp file, run whisperkit-cli
    ↓
Return transcription text
    ↓
Browser: Send to session via POST /api/session/{name}/send
    ↓
Backend: agentwire send -s {session} "{text}"
```

---

## Wave 1: Human Actions (RUNTIME BLOCKING)

- [ ] Ensure whisperkit-cli is installed and working
- [ ] Verify microphone permissions work in browser

---

## Wave 2: Backend Transcription Endpoint

Create `/api/transcribe` endpoint that accepts audio and returns transcription.

### 2.1 Add transcription API route

**Files:** `agentwire/server.py`

- Add `POST /api/transcribe` endpoint
- Accept multipart audio file upload
- Save to temp file, call whisperkit-cli (reuse logic from listen.py)
- Return JSON with transcription text
- Handle errors gracefully (no speech detected, timeout, etc.)

---

## Wave 3: PTT Button Component

Add the floating PTT button to session windows.

### 3.1 Create PTT button HTML/CSS

**Files:** `agentwire/static/js/session-window.js`, `agentwire/static/css/desktop.css`

- Add PTT button element in `_createContainer()` method
- Position: absolute, bottom-right corner, floating over terminal
- States: idle (mic icon), recording (red pulse), processing (spinner)
- Semi-transparent background so terminal is still visible beneath

### 3.2 Implement audio recording

**Files:** `agentwire/static/js/session-window.js`

- Use MediaRecorder API with getUserMedia
- Start recording on mousedown/touchstart
- Stop recording on mouseup/touchend/mouseleave
- Encode as WebM/Opus for efficient transfer
- Handle permission errors gracefully

---

## Wave 4: Integration

Wire up the PTT button to backend and session.

### 4.1 Connect PTT to transcription flow

**Files:** `agentwire/static/js/session-window.js`

- On recording stop, POST audio blob to `/api/transcribe`
- On success, POST transcription to `/api/session/{session}/send`
- Update button state throughout (recording → processing → idle)
- Show brief toast/status on success or error

---

## Wave 5: Polish

### 5.1 Add keyboard shortcut

**Files:** `agentwire/static/js/desktop.js` or `session-window.js`

- Global keyboard shortcut (configurable, default: hold space when window focused)
- Only active when a session window has focus
- Same behavior as button: hold to record, release to send

### 5.2 Visual feedback

**Files:** `agentwire/static/css/desktop.css`

- Smooth transitions between states
- Audio level visualization while recording (optional)
- Clear visual indication of recording state

---

## Completion Criteria

- [ ] PTT button appears in session windows (terminal mode only)
- [ ] Hold button records, release sends transcription to session
- [ ] Visual states: idle → recording (red) → processing (spinner) → idle
- [ ] Errors shown gracefully (no mic, transcription failed, etc.)
- [ ] Keyboard shortcut works when window focused
