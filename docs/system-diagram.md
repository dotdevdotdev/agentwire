# AgentWire System Diagram

## Current Architecture

```
┌─────────────────────┐
│   TABLET/BROWSER    │
│                     │
│  Push-to-talk UI    │
│  Audio playback     │
└──────────┬──────────┘
           │
           │ WebSocket: wss://localhost:8765/ws/room/{room}
           │   ↓ Binary audio chunks (recording)
           │   ↓ { "type": "join", "room": "anna@Jordans-Mini" }
           │   ↑ Binary audio (TTS playback)
           │   ↑ { "type": "status", ... }
           │
┌──────────▼──────────┐         ┌─────────────────────┐
│  PORTAL CONTAINER   │         │   STT CONTAINER     │
│  (agentwire-portal) │         │   (agentwire-stt)   │
│                     │         │                     │
│  FastAPI server     │  HTTP   │  Whisper model      │
│  WebSocket manager  ├────────►│  (base, CPU)        │
│  TTS orchestration  │         │                     │
│  Session routing    │ POST http://stt:8100/transcribe
│                     │ Body: multipart audio file    │
│  Port 8765 (web)    │ Response: { "text": "..." }  │
│  Port 2222 (SSH)    │         │                     │
└──────────┬──────────┘         └─────────────────────┘
           │
           ├─────────────────────────────────────────────┐
           │                                             │
           │ SSH: host.docker.internal:22                │ HTTPS: RunPod endpoint
           │   user: dotdev                              │
           │                                             │   POST /runsync
           │   tmux send-keys -t {session}               │   Body: {
           │     "[Voice] transcribed text\n"            │     "input": {
           │                                             │       "text": "...",
           │   tmux capture-pane -t {session}            │       "voice_path": "..."
           │     → session output                        │     }
           │                                             │   }
           │                                             │   Response: { "output": base64_audio }
           │                                             │
┌──────────▼──────────┐                      ┌───────────────────────────────┐
│   HOST MACHINE      │                      │       RUNPOD SERVERLESS       │
│   (Jordans-Mini)    │                      │                               │
│                     │                      │  ┌───────────────────────┐    │
│  tmux sessions:     │                      │  │ agentwire-tts container│   │
│  ┌────────────────┐ │                      │  │                       │    │
│  │ anna           │ │                      │  │  Chatterbox TTS       │    │
│  │ Claude Code    │ │                      │  │  Voice cloning        │    │
│  │ + chatbot role │ │                      │  │  GPU inference        │    │
│  └───────┬────────┘ │                      │  └───────────────────────┘    │
│          │          │                      │                               │
│          │          │                      └───────────────────────────────┘
│          │ Bash: say "response text"
│          │   → checks portal for browser connections
│          │   → routes to portal or local playback
│          │          │
│          │          │
│  ┌───────▼────────┐ │
│  │ say script     │ │
│  │ ~/.local/bin/  │ │
│  └───────┬────────┘ │
│          │          │
└──────────┼──────────┘
           │
           │ HTTPS: localhost:8765/api/say/{room}
           │   Body: { "text": "response" }
           │   → Portal generates TTS via RunPod
           │   → Streams audio to browser via WebSocket
           │
           └──────────► (back to Portal)
```

## Connection Summary

| From | To | Protocol | Endpoint | Payload |
|------|----|----------|----------|---------|
| Browser | Portal | WebSocket | `wss://:8765/ws/room/{room}` | Binary audio, JSON messages |
| Portal | STT | HTTP | `POST http://stt:8100/transcribe` | Multipart audio file → `{"text": "..."}` |
| Portal | Host | SSH | `host.docker.internal:22` | tmux commands |
| Portal | RunPod | HTTPS | `POST /runsync` | `{"input": {"text", "voice_path"}}` → base64 audio |
| Host (say) | Portal | HTTPS | `POST :8765/api/say/{room}` | `{"text": "..."}` |

## Voice Input Flow

```
1. User presses push-to-talk on tablet
2. Browser captures audio, sends chunks via WebSocket to Portal
3. User releases button
4. Portal forwards audio to STT container
5. STT returns transcription: { "text": "what's the status" }
6. Portal SSHs to host, runs: tmux send-keys -t anna "[Voice] what's the status"
7. Claude Code in anna session sees [Voice] prefix, responds with say command
```

## Voice Output Flow

```
1. Claude Code runs: say "everything looks good"
2. say script checks Portal API for browser connections to room
3. If browser connected:
   a. POST to Portal /api/say/{room} with text
   b. Portal calls RunPod TTS, gets audio
   c. Portal streams audio to browser via WebSocket
   d. Browser plays audio
4. If no browser:
   a. POST to Portal /api/local-tts/{room}
   b. Portal calls RunPod TTS, plays on server speakers
```

## Room Matching

The `say` script tries these room variants when checking for browser connections:

```
Room: anna
Tries: anna → anna@Jordans-Mini → anna@local

First match with has_connections: true wins
```

## Config Files (Host)

```
~/.agentwire/
├── config.yaml      # TTS/STT backend settings, RunPod credentials
├── machines.json    # SSH targets (host.docker.internal, dotdev-pc)
├── rooms.json       # Per-room voice settings
├── roles/           # Role instructions (orchestrator.md, chatbot.md)
└── hooks/           # PreToolUse security hooks
```
