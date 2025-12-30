# TTS Setup Guide

AgentWire uses Chatterbox for high-quality text-to-speech synthesis. This guide covers installation and configuration.

## Quick Start

```bash
# Start the TTS server
agentwire tts start

# Test it
agentwire say "Hello, this is a test"
```

## Installing Chatterbox

Chatterbox is a neural TTS system. Install it based on your platform:

### macOS / Linux (pip)

```bash
pip install chatterbox-tts

# Or with GPU support
pip install chatterbox-tts[cuda]
```

### From Source

```bash
git clone https://github.com/resemble-ai/chatterbox
cd chatterbox
pip install -e .
```

### Docker

```bash
docker run -p 8100:8100 resemble/chatterbox serve
```

## Configuration

Edit `~/.agentwire/config.yaml`:

```yaml
tts:
  backend: "chatterbox"
  url: "http://localhost:8100"
  default_voice: "default"
  
  # Voice settings
  exaggeration: 0.5    # 0-1, voice expressiveness
  cfg_weight: 0.5      # 0-1, adherence to voice profile
```

## CLI Commands

### Start TTS Server

```bash
# Start in tmux session
agentwire tts start

# With GPU
agentwire tts start --gpu

# Custom port
agentwire tts start --port 8200
```

### Stop TTS Server

```bash
agentwire tts stop
```

### Check Status

```bash
agentwire tts status
```

### Speak Text

```bash
# Local playback
agentwire say "Hello world"

# With custom voice
agentwire say --voice tiny-tina "Hello world"

# Send to room (for remote sessions)
agentwire say --room api "Task completed"
```

## Voices

List available voices:

```bash
curl http://localhost:8100/voices
```

### Adding Custom Voices

1. Record a 10-30 second audio sample
2. Place in `~/.agentwire/voices/`
3. Reference by filename (without extension)

```bash
agentwire say --voice my-voice "Testing custom voice"
```

## say vs remote-say

AgentWire provides two ways for Claude to speak:

### say (Local)

Used in local Claude sessions. Generates audio and plays on local speakers.

```bash
# In Claude session
say "Task completed"
```

### remote-say (Remote Sessions)

Used in remote Claude sessions. Sends audio back to the portal for playback on connected clients.

```bash
# In remote Claude session
remote-say "Task completed on remote server"
```

This is automatically handled - Claude sessions detect if they're local or remote.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Session                                             │
│  └── say "hello" or remote-say "hello"                     │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │ (local)           (remote)     │
              ▼                               ▼
┌─────────────────────┐         ┌─────────────────────────────┐
│  Chatterbox TTS     │         │  AgentWire Portal           │
│  localhost:8100     │         │  POST /api/say/{room}       │
│         │           │         │         │                   │
│         ▼           │         │         ▼                   │
│  Local speakers     │         │  WebSocket → Browser audio  │
└─────────────────────┘         └─────────────────────────────┘
```

## Troubleshooting

### "TTS server not reachable"

```bash
# Check if running
agentwire tts status

# Start it
agentwire tts start
```

### Poor audio quality

Adjust voice settings:

```bash
agentwire say --exaggeration 0.7 --cfg 0.6 "Testing quality"
```

### GPU not detected

```bash
# Check CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Start with explicit GPU flag
agentwire tts start --gpu
```

### Audio not playing (local say)

Check audio output:
- macOS: Uses `afplay`
- Linux: Uses `aplay`, `paplay`, or `play` (in order)

Install if missing:
```bash
# Linux
sudo apt install alsa-utils  # for aplay
```

## Performance

| Setup | Latency | Quality |
|-------|---------|---------|
| CPU | ~2-3s | Good |
| GPU (CUDA) | ~0.3-0.5s | Good |
| M1/M2 Mac | ~0.5-1s | Good |

For real-time conversation, GPU acceleration is recommended.
