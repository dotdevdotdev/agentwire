# Voice Input Setup

This guide explains how to set up voice input for AgentWire, allowing you to talk to Claude Code sessions via hotkeys.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Your Device                                                │
│  ├── Hotkey triggered (Hammerspoon, AutoHotkey, etc.)      │
│  ├── Recording starts                                       │
│  ├── Recording stops on release                             │
│  └── Audio sent to AgentWire for transcription             │
└─────────────────────────────────────────────────────────────┘
                              │
                        HTTP POST /transcribe
                              │
┌─────────────────────────────────────────────────────────────┐
│  AgentWire Portal                                           │
│  ├── Receives audio (webm/wav)                              │
│  ├── Transcribes via STT backend                            │
│  └── Sends text to target session                           │
└─────────────────────────────────────────────────────────────┘
                              │
                        agentwire send
                              │
┌─────────────────────────────────────────────────────────────┐
│  Claude Code Session                                        │
│  └── Receives transcribed prompt                            │
└─────────────────────────────────────────────────────────────┘
```

## Web Portal (Recommended)

The simplest approach is using the AgentWire web portal:

1. Start the portal: `agentwire portal start`
2. Open `https://localhost:8765` in your browser
3. Select a room/session
4. Hold the push-to-talk button to speak
5. Release to transcribe and send

This works from any device on your network - phone, tablet, laptop.

## Custom Hotkey Setup

For keyboard-triggered voice input from your desktop, you need:

1. A hotkey manager (Hammerspoon on macOS, AutoHotkey on Windows)
2. Audio recording tool
3. HTTP client to send to AgentWire

### Core Flow

```
1. User presses hotkey → Start recording
2. User releases hotkey → Stop recording
3. Convert audio to webm/wav
4. POST to https://localhost:8765/transcribe
5. Send transcribed text to target session via /send/{room}
```

### macOS with Hammerspoon

**Prerequisites:**
- Hammerspoon installed (`brew install hammerspoon`)
- `sox` for recording (`brew install sox`)
- `ffmpeg` for conversion (`brew install ffmpeg`)

**~/.hammerspoon/init.lua:**

```lua
-- AgentWire Voice Input
local agentwire = {}
agentwire.recording = false
agentwire.recordFile = os.getenv("HOME") .. "/.agentwire/recording.wav"
agentwire.targetRoom = "agentwire"  -- Default target session
agentwire.portalUrl = "https://localhost:8765"

-- Start recording
function agentwire.startRecording()
    if agentwire.recording then return end
    agentwire.recording = true
    
    -- Record using sox
    hs.task.new("/usr/local/bin/sox", nil, {
        "-d", "-r", "16000", "-c", "1", "-b", "16",
        agentwire.recordFile
    }):start()
    
    hs.alert("Recording...")
end

-- Stop recording and transcribe
function agentwire.stopRecording()
    if not agentwire.recording then return end
    agentwire.recording = false
    
    -- Kill sox
    os.execute("pkill -f 'sox -d'")
    
    hs.alert("Transcribing...")
    
    -- Convert and send to AgentWire
    hs.task.new("/bin/bash", function(exitCode, stdOut, stdErr)
        if exitCode == 0 then
            hs.alert("Sent!")
        else
            hs.alert("Error: " .. stdErr)
        end
    end, {"-c", [[
        # Convert to webm
        ffmpeg -y -i ~/.agentwire/recording.wav -c:a libopus ~/.agentwire/recording.webm 2>/dev/null
        
        # Send to transcribe endpoint
        TRANSCRIPT=$(curl -sk -X POST \
            -F "audio=@$HOME/.agentwire/recording.webm" \
            "]] .. agentwire.portalUrl .. [[/transcribe" | jq -r '.text')
        
        if [ -n "$TRANSCRIPT" ] && [ "$TRANSCRIPT" != "null" ]; then
            # Send to session
            curl -sk -X POST \
                -H "Content-Type: application/json" \
                -d "{\"text\": \"$TRANSCRIPT\"}" \
                "]] .. agentwire.portalUrl .. [[/send/]] .. agentwire.targetRoom .. [["
        fi
    ]]}):start()
end

-- Bind to F13 (or any key)
hs.hotkey.bind({}, "F13", agentwire.startRecording, agentwire.stopRecording)

-- Or use Cmd+Shift+V
hs.hotkey.bind({"cmd", "shift"}, "v", agentwire.startRecording, agentwire.stopRecording)
```

### Windows with AutoHotkey

**Prerequisites:**
- AutoHotkey v2 installed
- `ffmpeg` in PATH
- `curl` (included in Windows 10+)

**agentwire-voice.ahk:**

```autohotkey
#Requires AutoHotkey v2.0

; Configuration
global PortalUrl := "https://localhost:8765"
global TargetRoom := "agentwire"
global RecordFile := A_Temp "\agentwire_recording.wav"
global Recording := false

; F13 for push-to-talk (or change to any key)
F13:: {
    global Recording
    if !Recording {
        StartRecording()
    }
}

F13 up:: {
    global Recording
    if Recording {
        StopRecording()
    }
}

StartRecording() {
    global Recording, RecordFile
    Recording := true
    
    ; Start recording using ffmpeg (captures default mic)
    Run('ffmpeg -y -f dshow -i audio="Microphone" -ar 16000 -ac 1 "' RecordFile '"', , "Hide")
    ToolTip("Recording...")
}

StopRecording() {
    global Recording, RecordFile, PortalUrl, TargetRoom
    Recording := false
    
    ; Stop ffmpeg
    Run("taskkill /IM ffmpeg.exe /F", , "Hide")
    Sleep(500)
    
    ToolTip("Transcribing...")
    
    ; Send to AgentWire
    shell := ComObject("WScript.Shell")
    cmd := 'powershell -Command "' 
        . '$audio = [System.IO.File]::ReadAllBytes(\"' RecordFile '\"); '
        . '$boundary = [System.Guid]::NewGuid().ToString(); '
        . 'Invoke-RestMethod -Uri \"' PortalUrl '/transcribe\" -Method Post -ContentType \"multipart/form-data; boundary=$boundary\" -Body $audio'
        . '"'
    
    ; (Simplified - real implementation would parse response and send to /send/{room})
    ToolTip("")
}
```

### Linux with xdotool + shell

**Prerequisites:**
- `arecord` (ALSA utils)
- `ffmpeg`
- `curl`
- `xbindkeys` for hotkeys

**~/.agentwire/voice-input.sh:**

```bash
#!/bin/bash
set -e

PORTAL_URL="https://localhost:8765"
TARGET_ROOM="${1:-agentwire}"
RECORD_FILE="$HOME/.agentwire/recording.wav"
LOCK_FILE="$HOME/.agentwire/recording.lock"

start_recording() {
    touch "$LOCK_FILE"
    arecord -f cd -r 16000 -c 1 "$RECORD_FILE" &
    echo $! > "$LOCK_FILE"
    notify-send "AgentWire" "Recording..."
}

stop_recording() {
    if [ -f "$LOCK_FILE" ]; then
        kill $(cat "$LOCK_FILE") 2>/dev/null || true
        rm "$LOCK_FILE"
        
        notify-send "AgentWire" "Transcribing..."
        
        # Convert to webm
        ffmpeg -y -i "$RECORD_FILE" -c:a libopus "${RECORD_FILE%.wav}.webm" 2>/dev/null
        
        # Transcribe
        TRANSCRIPT=$(curl -sk -X POST \
            -F "audio=@${RECORD_FILE%.wav}.webm" \
            "$PORTAL_URL/transcribe" | jq -r '.text')
        
        if [ -n "$TRANSCRIPT" ] && [ "$TRANSCRIPT" != "null" ]; then
            # Send to session
            curl -sk -X POST \
                -H "Content-Type: application/json" \
                -d "{\"text\": \"$TRANSCRIPT\"}" \
                "$PORTAL_URL/send/$TARGET_ROOM"
            notify-send "AgentWire" "Sent: ${TRANSCRIPT:0:50}..."
        else
            notify-send "AgentWire" "No speech detected"
        fi
    fi
}

case "$1" in
    start) start_recording ;;
    stop) stop_recording ;;
    *) echo "Usage: $0 start|stop [room]" ;;
esac
```

**~/.xbindkeysrc:**
```
# F13 down
"~/.agentwire/voice-input.sh start"
    m:0x0 + c:191

# F13 up (requires xkbevd or similar for key release)
```

## API Reference

### POST /transcribe

Transcribe audio to text.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `audio` file (webm, wav, mp3, etc.)

**Response:**
```json
{
  "text": "transcribed text here"
}
```

### POST /send/{room}

Send text to a session.

**Request:**
```json
{
  "text": "prompt to send"
}
```

**Response:**
```json
{
  "success": true
}
```

## Audio Device Configuration

### Server-side (CLI voice commands)

Configure the audio input device for CLI commands like `agentwire listen` and `agentwire voiceclone`:

```yaml
# ~/.agentwire/config.yaml
audio:
  input_device: 1  # Device index (run `agentwire init` to select)
```

List available devices on macOS:
```bash
ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep -A20 "audio devices"
```

### Browser-side (Portal)

The portal UI includes mic and speaker selectors in the room header. These use browser APIs and are saved per-device in localStorage:

- **Mic selector** - Choose which microphone to use for push-to-talk
- **Speaker selector** - Choose which output device for TTS (Chrome/Edge only)

## Tips

1. **Low latency:** Use 16kHz mono audio to minimize transcription time
2. **Push-to-talk:** Hold key while speaking, release to send - feels natural
3. **Target room:** Configure your hotkey script to send to your most-used session
4. **SSL certs:** Use `-k` with curl to accept self-signed certificates
5. **Multiple rooms:** Create multiple hotkeys targeting different rooms
6. **Silence padding:** TTS audio includes 300ms silence at start to prevent first-syllable cutoff

## Troubleshooting

### "Connection refused"

Portal not running. Start it with:
```bash
agentwire portal start
```

### "Transcription failed"

Check STT backend is configured and working:
```bash
agentwire portal status
```

### Audio not recording

- macOS: Grant microphone access to Hammerspoon in System Preferences
- Windows: Check microphone is set as default recording device
- Linux: Verify `arecord` can access your mic: `arecord -l`
