# Mission: xterm.js Terminal Mode

> Add real interactive terminal to portal using xterm.js, alongside existing Monitor and Ambient modes.

## Objective

Enable full terminal interaction in the browser while preserving all existing functionality (voice, permissions, monitoring). This solves the limitation where sessions don't start in the correct directory and provides real terminal features (vim, interactive prompts, proper shell).

## Background

**Current Issue:**
- Portal creates sessions with correct path via `tmux new-session -c /path`
- But Claude may not be in that directory when it starts
- Can't detect worktrees because `~` isn't a git repo
- No real terminal features (vim, readline, tab completion)

**Current "Terminal Mode" is actually Monitor Mode:**
- Read-only polling via `tmux capture-pane`
- One-way text input via `tmux send-keys`
- Shows AskUserQuestion popups and permission modals
- Works great for monitoring, not for real terminal work

## Concept

**Three distinct modes, all work simultaneously:**

1. **Ambient Mode** (existing) - Orb, voice-first UI
2. **Monitor Mode** (existing "Terminal Mode" renamed) - Read-only monitoring with text input
3. **Terminal Mode** (new) - Real interactive terminal via xterm.js

**Key insight:** tmux allows multiple attachments simultaneously:
- Monitor mode keeps polling `tmux capture-pane` (doesn't interfere)
- Terminal mode connects via `tmux attach` when activated
- User's local terminal can also be attached (common workflow)
- All three see the same session, all can send input

## Wave 1: Human Actions (BLOCKING)

- [ ] Review xterm.js license (MIT - should be fine)
- [ ] Decide on default mode when opening a room (Monitor or stay on last used?)
- [ ] Confirm terminal should be opt-in per tab (not always on)

## Wave 2: Fix Directory Issue (Quick Win)

### 2.1 Ensure Claude starts in correct directory

**Files:** `agentwire/__main__.py` (cmd_new function)

**Problem:** Session created with `-c /path` but Claude doesn't cd there

**Fix for all session creation locations:**

```python
# After tmux new-session, before starting Claude:
f"tmux send-keys -t {session_name} 'cd {session_path}' Enter && "
f"sleep 0.1 && "
f"tmux send-keys -t {session_name} 'export AGENTWIRE_ROOM={room_name}' Enter && "
f"sleep 0.1 && "
f"tmux send-keys -t {session_name} 'claude{bypass_flag}' Enter"
```

**Locations to fix:**
- Local session creation (cmd_new, line ~1100)
- Remote session creation (cmd_new with machine, line ~1249)
- Recreate session (cmd_recreate, line ~1894)
- Fork session (cmd_fork, line ~2140)
- Portal API `/api/create` endpoint

**Testing:**
- Create session with path: `agentwire new -s test -p ~/projects/agentwire`
- Verify: `agentwire send -s test "pwd"` returns correct path
- Create worktree session: `agentwire new -s agentwire/test-branch`
- Verify: Session detects git repo and can create commits

## Wave 3: Rename "Terminal Mode" to "Monitor Mode"

### 3.1 Update frontend labels and UI

**Files:**
- `agentwire/templates/room.html`
- `agentwire/static/js/room.js`
- `agentwire/static/css/room.css`

**Changes:**
- Mode selector: `[Ambient] [Monitor] [Terminal]` (Terminal tab disabled/grayed out for now)
- CSS class renames: `.terminal-mode` → `.monitor-mode`
- JavaScript: `terminalMode` → `monitorMode`
- Keep all existing functionality, just rename

### 3.2 Update documentation

**Files:** `CLAUDE.md`, `README.md`

Update all references:
- "Terminal mode" → "Monitor mode"
- Explain the three modes and their purposes
- Document that Monitor is read-only polling, Terminal is interactive

## Wave 4: Add xterm.js Library

### 4.1 Install xterm.js and addons

**Files:** `agentwire/static/js/` (new), `agentwire/templates/base.html`

**Dependencies to add:**
- `xterm.js` (core library)
- `xterm-addon-fit` (auto-resize terminal)
- `xterm-addon-web-links` (clickable URLs)
- `xterm-addon-webgl` (hardware acceleration, optional)

**Options:**
1. CDN: Load from unpkg.com (simpler, no build step)
2. NPM: Install and bundle (better for offline)

**Recommendation:** CDN for now (simpler, faster to implement)

```html
<!-- In base.html -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
<script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-web-links@0.9.0/lib/xterm-addon-web-links.js"></script>
```

### 4.2 Create terminal container in room.html

**Files:** `agentwire/templates/room.html`

Add terminal container (hidden by default):

```html
<div class="mode-content terminal-mode-content" style="display: none;">
  <div class="terminal-activation" id="terminalActivation">
    <button class="activate-terminal-btn" id="activateTerminal">
      🖥️ Activate Interactive Terminal
    </button>
    <p class="terminal-info">
      Connect to tmux session for full terminal control (vim, interactive commands, etc.)
    </p>
  </div>
  <div id="terminal" class="terminal-container" style="display: none;"></div>
  <div class="terminal-status" id="terminalStatus"></div>
</div>
```

## Wave 5: WebSocket Terminal Endpoint

### 5.1 Add /ws/terminal/{room} endpoint

**Files:** `agentwire/server.py`

**New WebSocket endpoint:**

```python
async def handle_terminal_ws(self, request: web.Request) -> web.WebSocketResponse:
    """WebSocket endpoint for terminal attachment via tmux."""
    room_name = request.match_info["name"]

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Spawn tmux attach process
    # Read from tmux stdout → send to WebSocket
    # Read from WebSocket → write to tmux stdin

    proc = await asyncio.create_subprocess_exec(
        "tmux", "attach", "-t", room_name,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Bidirectional forwarding loop
    # ... (implementation details)

    return ws
```

**Key challenges:**
1. tmux attach is blocking - need to run in subprocess
2. Bidirectional data flow: tmux ↔ WebSocket
3. Handle tmux control sequences (resize, etc.)
4. Graceful disconnect when user closes terminal tab

**Implementation approach:**
- Use asyncio subprocess for tmux
- Two concurrent tasks: tmux→ws and ws→tmux
- Handle SIGWINCH for terminal resize
- Clean up subprocess on disconnect

### 5.2 Terminal resize handling

**Files:** `agentwire/server.py`

When browser terminal resizes, send tmux control command:

```python
# WebSocket receives resize message from client
{"type": "resize", "cols": 120, "rows": 40}

# Send to tmux
tmux_stdin.write(f"tmux resize-window -t {room_name} -x {cols} -y {rows}\n".encode())
```

## Wave 6: Frontend Terminal Integration

### 6.1 Initialize xterm.js on activation

**Files:** `agentwire/static/js/terminal.js` (new)

```javascript
class TerminalMode {
  constructor(roomName) {
    this.roomName = roomName;
    this.term = null;
    this.socket = null;
    this.fitAddon = null;
  }

  async activate() {
    // Create xterm instance
    this.term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
      },
    });

    // Add fit addon for auto-resize
    this.fitAddon = new FitAddon.FitAddon();
    this.term.loadAddon(this.fitAddon);

    // Add web links addon (clickable URLs)
    this.term.loadAddon(new WebLinksAddon.WebLinksAddon());

    // Attach to DOM
    this.term.open(document.getElementById('terminal'));
    this.fitAddon.fit();

    // Connect WebSocket
    await this.connect();
  }

  async connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws/terminal/${this.roomName}`;

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      console.log('[Terminal] Connected');
      // Send initial size
      this.sendResize();
    };

    this.socket.onmessage = (event) => {
      // Write tmux output to terminal
      this.term.write(event.data);
    };

    this.socket.onclose = () => {
      console.log('[Terminal] Disconnected');
      this.term.writeln('\r\n[Terminal disconnected]');
    };

    // Send terminal input to WebSocket
    this.term.onData((data) => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // Handle resize
    window.addEventListener('resize', () => {
      this.fitAddon.fit();
      this.sendResize();
    });
  }

  sendResize() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'resize',
        cols: this.term.cols,
        rows: this.term.rows,
      }));
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
    }
    if (this.term) {
      this.term.dispose();
    }
  }
}
```

### 6.2 Mode switching logic

**Files:** `agentwire/static/js/room.js`

Update mode switching:
- Ambient mode: Hide terminal, hide monitor, show orb
- Monitor mode: Hide terminal, hide orb, show monitor
- Terminal mode: Hide orb, hide monitor, show terminal
- All modes can coexist in background (terminal WebSocket stays connected)

**Optimization:** Keep terminal connected when switching to other modes (don't disconnect unless user explicitly closes it)

## Wave 7: Terminal Lifecycle Management

### 7.1 Activation/deactivation flow

**Flow:**
1. User switches to Terminal tab → sees "Activate Terminal" button
2. Clicks activate → creates xterm.js instance, connects WebSocket
3. Terminal shows loading, then connects to tmux
4. User can switch to other tabs (Ambient, Monitor) without disconnecting
5. Terminal keeps running in background
6. User can return to Terminal tab, sees live terminal
7. Close terminal button → disconnect WebSocket, dispose xterm.js

### 7.2 Handle connection failures

**Files:** `agentwire/static/js/terminal.js`

**Error scenarios:**
- tmux session doesn't exist
- tmux attach fails (permissions, etc.)
- WebSocket connection fails
- Session killed while terminal active

**UI feedback:**
```javascript
socket.onerror = (error) => {
  terminalStatus.textContent = '❌ Connection failed';
  terminalStatus.className = 'terminal-status error';
};

socket.onclose = (event) => {
  if (event.code !== 1000) {
    // Abnormal closure
    terminalStatus.textContent = '⚠️ Connection lost. Reconnect?';
    // Show reconnect button
  }
};
```

## Wave 8: Polish and UX

### 8.1 Terminal theme matching

**Files:** `agentwire/static/css/room.css`

Match terminal colors to portal theme:
- Dark theme: xterm dark theme
- Light theme: xterm light theme (if supported)
- Custom colors for AgentWire branding

### 8.2 Keyboard shortcuts

**Files:** `agentwire/static/js/terminal.js`

**Shortcuts:**
- `Cmd/Ctrl + K` - Clear terminal (send `clear` command)
- `Cmd/Ctrl + D` - Disconnect terminal
- All other shortcuts passed through to tmux

**Important:** Don't intercept Cmd+C, Cmd+V (let terminal handle)

### 8.3 Copy/paste support

xterm.js handles this automatically, but verify:
- Right-click context menu (if needed)
- Cmd/Ctrl+C/V works
- Middle-click paste on Linux

### 8.4 Terminal status indicator

**Files:** `agentwire/templates/room.html`

Show connection status:
```html
<div class="terminal-status">
  <span class="status-indicator connected"></span>
  Connected to myproject (80x24)
</div>
```

States:
- 🟢 Connected (green)
- 🟡 Connecting (yellow)
- 🔴 Disconnected (red)
- ⚠️ Error (amber)

## Wave 9: Testing and Documentation

### 9.1 Test all scenarios

**Test matrix:**

| Scenario | Monitor | Terminal | Expected |
|----------|---------|----------|----------|
| Create session via portal | ✓ | - | Monitor shows output |
| Activate terminal | ✓ | ✓ | Both work simultaneously |
| Type in monitor input | ✓ | ✓ | Both see input |
| Type in terminal | ✓ | ✓ | Both see input |
| AskUserQuestion | ✓ | - | Popup shows in monitor |
| Permission request | ✓ | - | Modal shows in monitor |
| Vim in terminal | - | ✓ | Works normally |
| Switch tabs | ✓ | ✓ | Terminal stays connected |
| Close terminal | ✓ | - | WebSocket disconnects |
| Local tmux attach | ✓ | ✓ | All three work together |

### 9.2 Update documentation

**Files:** `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`

**Document:**
- Three modes and when to use each
- How to activate terminal mode
- Keyboard shortcuts
- Known limitations (if any)
- Architecture diagram with WebSocket flow

**CLAUDE.md Portal Features section:**

```markdown
## Portal Modes

### Ambient Mode
- Orb visualization
- Voice input/output
- Minimal UI, conversation-focused
- **Use for:** Hands-free interaction, casual queries

### Monitor Mode
- Read-only terminal output
- Text input for prompts
- AskUserQuestion popups
- Permission modals
- **Use for:** Observing Claude work, guided interaction

### Terminal Mode
- Full interactive terminal (xterm.js)
- Attached to tmux session
- Vim, readline, tab completion
- **Use for:** Real development work, interactive commands

**All modes work simultaneously** - you can switch between them without disconnecting.
```

## Completion Criteria

- [ ] Sessions start in correct directory (cd before Claude starts)
- [ ] "Terminal Mode" renamed to "Monitor Mode" everywhere
- [ ] Terminal tab shows in mode selector (disabled until activated)
- [ ] xterm.js libraries loaded
- [ ] `/ws/terminal/{room}` WebSocket endpoint works
- [ ] Terminal activation flow works (button → connect → terminal)
- [ ] Terminal input/output bidirectional
- [ ] Terminal resize works
- [ ] Can switch between modes without disconnecting terminal
- [ ] Monitor and Terminal work simultaneously
- [ ] Local tmux attach works alongside portal modes
- [ ] Documentation updated with all three modes

## Technical Notes

**tmux attach limitations:**
- `tmux attach` is a blocking command
- Must run in subprocess with stdout/stdin pipes
- Handle SIGWINCH for resize (may need tmux control mode)
- Detach cleanly on WebSocket close

**Alternative approach (tmux control mode):**
- `tmux -CC attach` gives programmatic control
- More complex but cleaner resize handling
- Evaluate if basic attach doesn't work well

**Security considerations:**
- Terminal WebSocket uses same auth as monitor (room-based)
- No additional authentication needed
- Users already trust tmux sessions they create
- Terminal can't access other rooms (enforced by WebSocket path)

**Performance:**
- xterm.js is highly optimized (used by VS Code)
- WebSocket overhead minimal
- Terminal works fine over network (like SSH)
- Monitor mode keeps working (independent polling)

## Migration Notes

**Existing users:**
- "Terminal Mode" becomes "Monitor Mode" (same functionality)
- No breaking changes to existing workflows
- Terminal Mode is opt-in, doesn't activate automatically
- All existing features preserved

**Config changes:**
- None required

**Database changes:**
- None required
