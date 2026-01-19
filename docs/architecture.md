# Architecture

> Living document. Update this, don't create new versions.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser → https://localhost:8765                           │
│  └── Desktop Control Center (WinBox windows)                │
└─────────────────────────────────────────────────────────────┘
                              │
                         WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│  AgentWire Portal (tmux session, default: agentwire-portal) │
│  ├── HTTP routes (desktop UI, static assets)                │
│  ├── WebSocket /ws/{session} (monitor mode output)          │
│  ├── WebSocket /ws/terminal/{session} (terminal attach)     │
│  ├── /transcribe (STT)                                      │
│  ├── /send/{session} (prompt forwarding)                    │
│  └── /api/say/{session} (TTS broadcast)                     │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
    Local tmux sessions            Remote via SSH
    (send-keys, capture-pane,      (session@machine)
     tmux attach subprocess)
```

---

## Desktop Control Center

The portal provides an OS-like desktop interface using WinBox.js for window management. Sessions are opened as draggable, resizable windows.

### Window Types

| Window | Purpose | Source |
|--------|---------|--------|
| Projects | List discovered projects, click to see details/create session | Menu bar |
| Sessions | List all sessions with Monitor/Connect/Chat buttons | Menu bar |
| Machines | List configured machines with status | Cog menu dropdown |
| Config | Display current configuration | Cog menu dropdown |
| Session Window | Monitor or Terminal view of a session | Click from Sessions list |
| Chat | Voice input with orb visualization | Chat button in Sessions window (voice-enabled sessions only) |

### Session Window Modes

Each session can be opened in one of two modes:

| Mode | Element | Use Case |
|------|---------|----------|
| **Monitor** | `<pre>` with ANSI-to-HTML | Read-only output viewing, polls `tmux capture-pane` |
| **Terminal** | xterm.js | Interactive terminal, attaches via `tmux attach` |

**Monitor mode** uses a simple `<pre>` element (not xterm.js) because it just displays captured text output. ANSI escape codes are converted to HTML for color support.

**Terminal mode** uses xterm.js with the fit addon for proper terminal emulation. Requires precise container dimensions for the fit addon to calculate rows/columns correctly.

### Multiple Windows

- Multiple session windows can be open simultaneously
- Each window has independent WebSocket connection
- Windows can be minimized to taskbar, dragged, resized
- Monitor and Terminal windows for the same session work together (both see same output)

---

## Terminal Resize Handling

Terminal mode has sophisticated resize handling to ensure xterm.js fits correctly in all scenarios:

| Event | Handler | Strategy |
|-------|---------|----------|
| WinBox drag resize | ResizeObserver + `onresize` | Direct `fit()` call |
| WinBox maximize/restore | `_handleResizeAfterAnimation()` | Wait for CSS `transitionend` event, fallback timeout |
| Browser fullscreen | `_handleFullscreenResize()` | Wait for `fullscreenchange` event, multiple delayed fits |

**Why multiple strategies:**
- WinBox animates maximize/restore with CSS transitions
- Browser fullscreen has its own event lifecycle
- The fit addon needs final container dimensions, not mid-animation values

**Resize message flow:**
```
Browser resize → fit addon calculates cols/rows → WebSocket {type:'resize'} → tmux resize-window
```

---

## WebSocket Flow for Terminal Mode

```
Browser (xterm.js)              Portal (server.py)              tmux session
─────────────────              ──────────────────              ────────────

1. User clicks "Terminal" button
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
5. Close window                 │                               │
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
5. **Multiple attachments:** tmux allows simultaneous attachments - local terminal, Terminal window, and Monitor window all work together

---

## Known Limitations

### Terminal Mode

- **Desktop-only:** Terminal mode requires a desktop browser with keyboard input.
- **WebGL fallback:** WebGL acceleration may not be available on older browsers. Terminal automatically falls back to canvas rendering.
- **Very rapid output:** Extremely rapid output (10,000+ lines/second) may cause temporary slowdown while xterm.js processes the data.
- **Remote latency:** Remote sessions via SSH may experience higher latency in Terminal mode.

### Monitor Mode

- **Read-only:** Monitor mode displays output via polling (`tmux capture-pane`). It shows a snapshot updated every 500ms, not true real-time scrolling like Terminal mode.
- **No terminal features:** Tab completion, readline editing, and TUI applications (like vim) won't work in Monitor mode. Use Terminal mode for these.

### General

- **Local tmux conflicts:** If you manually resize the tmux window via local `tmux attach`, it may temporarily conflict with Terminal mode's auto-resize. Refreshing the connection resolves this.

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
