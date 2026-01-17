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
POST /transcribe with audio blob
    ↓
Backend: Save temp file, convert to wav, transcribe via STT backend
    ↓
Return transcription text
    ↓
Browser: Send to session via POST /send/{session}
    ↓
Backend: agentwire send -s {session} "{text}"
```

---

## Wave 1: Human Actions (RUNTIME BLOCKING)

- [x] Ensure whisperkit-cli is installed and working
- [x] Verify microphone permissions work in browser

---

## Wave 2: Backend Transcription Endpoint

Create `/api/transcribe` endpoint that accepts audio and returns transcription.

### 2.1 Add transcription API route ✅

**Files:** `agentwire/server.py`

- Already exists at `POST /transcribe`
- Accepts multipart audio file upload (webm)
- Converts to wav, transcribes via configured STT backend
- Returns JSON with transcription text
- Handles errors gracefully

---

## Wave 3: PTT Button Component

Add the floating PTT button to session windows.

### 3.1 Create PTT button HTML/CSS ✅

**Files:** `agentwire/static/js/session-window.js`, `agentwire/static/css/desktop.css`

- Added PTT button element in `_createContainer()` method
- Position: absolute, bottom-right corner, floating over terminal
- States: idle (🎤), recording (🔴 with red pulse), processing (⏳)
- Semi-transparent background with backdrop blur

### 3.2 Implement audio recording ✅

**Files:** `agentwire/static/js/session-window.js`

- Uses MediaRecorder API with getUserMedia
- Starts recording on mousedown/touchstart
- Stops recording on mouseup/touchend/mouseleave
- Encodes as WebM/Opus for efficient transfer
- Handles permission errors gracefully

---

## Wave 4: Integration

Wire up the PTT button to backend and session.

### 4.1 Connect PTT to transcription flow ✅

**Files:** `agentwire/static/js/session-window.js`

- On recording stop, POST audio blob to `/transcribe`
- On success, POST transcription to `/send/{session}` with voice prompt hint
- Updates button state throughout (recording → processing → idle)
- Shows status in window status bar

---

## Wave 5: Polish

### 5.1 Add keyboard shortcut ✅

**Files:** `agentwire/static/js/session-window.js`

- Ctrl+Space (or Cmd+Space on Mac) to toggle recording
- Only active when session window is focused
- Same behavior as button: hold to record, release to send

### 5.2 Visual feedback ✅

**Files:** `agentwire/static/css/desktop.css`

- Smooth transitions between states
- Pulsing red animation while recording
- Clear visual indication of recording state

---

## Completion Criteria

- [x] PTT button appears in session windows (terminal mode only)
- [x] Hold button records, release sends transcription to session
- [x] Visual states: idle → recording (red) → processing (spinner) → idle
- [x] Errors shown gracefully (no mic, transcription failed, etc.)
- [x] Keyboard shortcut works when window focused (Ctrl/Cmd+Space)
