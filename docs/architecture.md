# Architecture

> Living document. Update this, don't create new versions.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Device (phone/tablet/laptop)                               │
│  └── Browser → https://localhost:8765                       │
└─────────────────────────────────────────────────────────────┘
                              │
                         WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│  AgentWire Portal (agentwire-portal tmux session)           │
│  ├── HTTP routes (dashboard, session pages)                 │
│  ├── WebSocket /ws/{session} (ambient/monitor modes)           │
│  ├── WebSocket /ws/terminal/{session} (terminal mode attach)   │
│  ├── /transcribe (STT)                                      │
│  ├── /send/{session} (prompt forwarding)                       │
│  └── /api/say/{session} (TTS broadcast)                        │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
    Local tmux sessions            Remote via SSH
    (send-keys, capture-pane,      (session@machine)
     tmux attach subprocess)
```

---

## Three-Mode Architecture

The portal provides three distinct modes for interacting with Claude Code sessions. All modes can work simultaneously.

### Ambient Mode

Voice-first, minimal UI focused on conversational interaction.

- **Input:** Voice (push-to-talk) → STT → text → tmux send-keys
- **Output:** WebSocket streaming → orb state updates
- **Interaction:** Modals for AskUserQuestion, permissions

### Monitor Mode

Read-only terminal output with text input for sending prompts.

- **Input:** Text area → `/send/{session}` HTTP → tmux send-keys
- **Output:** Polling (`tmux capture-pane` every 500ms) → WebSocket → display
- **Interaction:** Same modals as Ambient mode

### Terminal Mode

Full interactive terminal via xterm.js attached to tmux session.

- **Input:** xterm.js → WebSocket (`/ws/terminal/{session}`) → tmux attach stdin
- **Output:** tmux attach stdout → WebSocket → xterm.js
- **Bidirectional:** Full duplex communication over single WebSocket
- **Resize:** Browser resize → WebSocket message → `tmux resize-window`

---

## WebSocket Flow for Terminal Mode

```
Browser (xterm.js)              Portal (server.py)              tmux session
─────────────────              ──────────────────              ────────────

1. User clicks "Activate Terminal"
   │
   ├─[WebSocket connect]──────>│
   │                            ├─[spawn subprocess]──────────>│
   │                            │  tmux attach -t session      │
   │                            │                               │
2. Send terminal input          │                               │
   │                            │                               │
   ├─[WS: {type:'input'}]──────>│                               │
   │                            ├─[write to stdin]────────────>│
   │                            │                               │
3. Receive terminal output      │                               │
   │                            │<──[read from stdout]──────────┤
   │<──[WS: binary data]────────┤                               │
   │                            │                               │
4. Resize terminal              │                               │
   │                            │                               │
   ├─[WS: {type:'resize'}]─────>│                               │
   │                            ├─[tmux resize-window]────────>│
   │                            │                               │
5. Close terminal               │                               │
   │                            │                               │
   ├─[WS disconnect]──────────>│                               │
   │                            ├─[kill subprocess]────────────>│
   │                            │  (detaches from tmux)         │
```

### Key Implementation Details

1. **Subprocess management:** Portal spawns `tmux attach` as asyncio subprocess with stdin/stdout pipes
2. **Bidirectional forwarding:** Two concurrent tasks:
   - `tmux stdout → WebSocket` (reads output, sends to browser)
   - `WebSocket → tmux stdin` (receives input, writes to tmux)
3. **Graceful cleanup:** On WebSocket close, subprocess is terminated, tmux session detaches cleanly
4. **No interference:** Monitor mode's `capture-pane` polling runs independently, doesn't affect Terminal WebSocket
5. **Multiple attachments:** tmux allows simultaneous attachments - local terminal, Terminal mode, and Monitor mode all work together

---

## Known Limitations

### Terminal Mode

- **Desktop-only:** Terminal mode requires a desktop browser with keyboard input. Mobile/tablet devices show a message indicating desktop is required.
- **WebGL fallback:** WebGL acceleration may not be available on older browsers or certain configurations. Terminal automatically falls back to canvas rendering.
- **Copy/paste on mobile:** While Terminal is disabled on mobile, copy/paste behavior may vary across browsers even on desktop.
- **Very rapid output:** Extremely rapid output (10,000+ lines/second) may cause temporary slowdown while xterm.js processes the data.
- **Remote latency:** Remote sessions via SSH may experience higher latency in Terminal mode compared to local sessions.

### Monitor Mode

- **Read-only:** Monitor mode displays output via polling (`tmux capture-pane`). It shows a snapshot updated every 500ms, not true real-time scrolling like Terminal mode.
- **No terminal features:** Tab completion, readline editing, and TUI applications (like vim) won't work in Monitor mode. Use Terminal mode for these.

### Ambient Mode

- **Voice accuracy:** STT accuracy depends on the backend (WhisperKit, remote, etc.) and audio quality. Background noise may affect transcription.
- **Browser audio:** Push-to-talk requires browser microphone permissions and may not work in all environments (e.g., WSL2 without audio passthrough).

### General

- **Session state sync:** When switching modes, there may be a brief delay (< 1 second) before the new mode shows current output.
- **Local tmux conflicts:** If you manually resize the tmux window via local `tmux attach`, it may temporarily conflict with Terminal mode's auto-resize. Refreshing the Terminal mode connection resolves this.

---

## Extending with New Capabilities

The pattern for adding new agent-to-client communication:

1. **Create a CLI command** (e.g., `agentwire notify "title" "body"`)
2. **Command POSTs to API** (e.g., `/api/notify/{session}`)
3. **Server broadcasts via WebSocket** to connected clients
4. **Browser handles message type** and renders UI

This command-based approach is more reliable than pattern-matching terminal output because:
- Terminal output is noisy (typing echoes, ANSI codes, mixed I/O)
- Commands are explicit and unambiguous
- Works consistently across local and remote sessions

**Current capabilities using this pattern:**
- `agentwire say` → TTS audio playback (smart routing to browser or local)
- `agentwire send` → Send prompts to sessions
- Image uploads → `@/path` references in messages

---

## Network Architecture

AgentWire services can run on different machines. The **service topology** concept lets you specify where each service runs (portal, TTS), with SSH tunnels providing connectivity between them.

### Service Topology

| Service | Purpose | Typical Location |
|---------|---------|------------------|
| Portal | Web UI, WebSocket server, session management | Local machine (laptop/desktop) |
| TTS | Voice synthesis (Chatterbox) | GPU machine (requires CUDA) |
| STT | Voice transcription | Local machine |
| Sessions | Claude Code instances | Local or remote machines |

**Single-machine setup:** Portal and TTS run locally. No tunnels needed.

**Multi-machine setup:** TTS runs on GPU server, portal runs locally. Tunnel forwards localhost:8100 to gpu-server:8100.

### Configuration: services Section

Add `services` to `~/.agentwire/config.yaml` to define where services run:

```yaml
services:
  # Portal runs locally (default)
  portal:
    machine: null    # null = local
    port: 8765
    health_endpoint: "/health"

  # TTS runs on GPU server
  tts:
    machine: "gpu-server"  # Must exist in machines.json
    port: 8100
    health_endpoint: "/health"
```

**machine field:**
- `null` = service runs on this machine
- `"machine-id"` = service runs on a machine from machines.json

### SSH Tunnels

When a service is configured to run on a remote machine, you need an SSH tunnel to reach it from your local machine.

```bash
# Tunnel management
agentwire tunnels up       # Create all required tunnels
agentwire tunnels down     # Tear down all tunnels
agentwire tunnels status   # Show tunnel health
agentwire tunnels check    # Verify with health checks
```

**How tunnels work:**

1. Config says `services.tts.machine: "gpu-server"`
2. AgentWire calculates: need tunnel from localhost:8100 to gpu-server:8100
3. `agentwire tunnels up` creates: `ssh -L 8100:localhost:8100 -N -f user@gpu-server`
4. Local code can now use `http://localhost:8100` to reach TTS on gpu-server

**Tunnel state** is stored in `~/.agentwire/tunnels/` (PID files for process tracking).

### Network Commands

```bash
# Show complete network health at a glance
agentwire network status

# Auto-diagnose and fix common issues
agentwire doctor              # Interactive - asks before fixing
agentwire doctor --yes        # Auto-fix everything
agentwire doctor --dry-run    # Show what would be fixed
```

---

## Troubleshooting Guide

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| TTS not responding | Tunnel not running | `agentwire tunnels up` |
| Tunnel fails to create | SSH key not configured | Check `ssh gpu-server` works |
| Port already in use | Stale tunnel or other process | `lsof -i :8100` to find process |
| Machine not found | Not in machines.json | `agentwire machine add gpu-server --host <ip>` |
| Service responding on wrong port | Port mismatch in config | Check `services.tts.port` matches TTS server |

### Quick Diagnostics

```bash
# Full diagnostic with auto-fix
agentwire doctor

# Check specific components
agentwire tunnels status    # Are tunnels up?
agentwire network status    # Overall health
agentwire config validate   # Config file issues
```

### Common Issues

**1. "Connection refused" to TTS:**

```bash
# Check if tunnel exists
agentwire tunnels status

# Create missing tunnels
agentwire tunnels up

# Verify TTS is running on remote
ssh gpu-server "curl http://localhost:8100/health"
```

**2. Tunnel created but service still unreachable:**

```bash
# Check if port is actually listening locally
lsof -i :8100

# Test health endpoint
curl -k https://localhost:8100/health
```

**3. SSH timeout when creating tunnel:**

```bash
# Verify SSH connectivity
ssh -o ConnectTimeout=5 gpu-server echo ok

# Check machine config
agentwire machine list
```
