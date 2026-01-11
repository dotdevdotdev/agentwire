# AgentWire System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENTWIRE SYSTEM                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐     WebSocket      ┌──────────────────────────────────────┐
│  Tablet/Browser  │◄──────────────────►│         Portal (Docker :8765)        │
│                  │    Voice/Audio     │                                      │
│  • Push-to-talk  │                    │  • Web UI for session management     │
│  • Audio playback│                    │  • TTS generation (RunPod)           │
│  • Room selection│                    │  • STT transcription                 │
└──────────────────┘                    │  • Audio routing                     │
                                        │  • Runs in tmux: agentwire-portal    │
                                        └──────────────────────────────────────┘
                                                         │
                                                         │ SSH
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            HOST MACHINE (Jordans-Mini)                      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         tmux sessions                                │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │   │
│  │  │   agentwire     │    │      anna       │    │    <other>      │  │   │
│  │  │  (orchestrator) │    │  (orchestrator) │    │                 │  │   │
│  │  │                 │    │                 │    │                 │  │   │
│  │  │  Claude Code    │    │  Claude Code    │    │  Claude Code    │  │   │
│  │  │  + voice role   │    │  + voice role   │    │  + role         │  │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ~/.agentwire/                                                              │
│  ├── config.yaml        # TTS/STT backends, ports                          │
│  ├── machines.json      # Remote machines (dotdev-pc, portal)              │
│  ├── rooms.json         # Per-session settings (voice, permissions)        │
│  ├── roles/             # Role instructions (orchestrator, worker, etc)    │
│  └── hooks/             # Security hooks (damage-control)                  │
│                                                                             │
│  ~/projects/<name>/                                                         │
│  └── .agentwire.yml     # Room name for say command routing                │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ SSH (optional)
                                         ▼
                              ┌─────────────────────┐
                              │  Remote Machine     │
                              │  (dotdev-pc)        │
                              │                     │
                              │  tmux sessions...   │
                              └─────────────────────┘
```

## Voice Flow

```
Tablet → [push-to-talk] → Portal (STT) → "[Voice] text" → tmux session
tmux session → say "response" → Portal (TTS/RunPod) → audio → Tablet
```

## Room Detection

The `say` command determines the room in this order:

1. `--room` flag
2. `AGENTWIRE_ROOM` env var
3. `.agentwire.yml` in project dir
4. Path inference (`~/projects/anna` → `anna`)
5. tmux session name

## Connection Matching

When routing audio, `say` checks the portal for browser connections using these room name variants:

| Variant | Example |
|---------|---------|
| room | `anna` |
| room@hostname | `anna@Jordans-Mini` |
| room@local | `anna@local` |

The tablet typically connects to `room@hostname` format.
