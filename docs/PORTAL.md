# AgentWire Portal Features

> Web portal documentation. For project overview, see [CLAUDE.md](../CLAUDE.md). For CLI commands, see [CLI-REFERENCE.md](./CLI-REFERENCE.md).

## Portal Modes

The portal provides three distinct modes for interacting with Claude Code sessions. All modes can work simultaneously - you can switch between them without disconnecting.

### Ambient Mode

Voice-first, minimal UI focused on conversational interaction.

**Features:**
- Animated orb visualization showing session state
- Push-to-talk voice input
- TTS audio playback
- AskUserQuestion popups
- Permission modals (for normal/restricted sessions)

**Use for:**
- Hands-free interaction
- Casual queries and conversation
- Voice-driven workflows
- Monitoring session activity at a glance

**State indicators:**

| State | Color | Meaning |
|-------|-------|---------|
| Ready | Green | Idle, waiting for input |
| Listening | Yellow | Recording voice input |
| Processing | Purple | Transcribing or agent working |
| Generating | Blue | TTS generating voice |
| Speaking | Green | Playing audio response |

### Monitor Mode

Read-only terminal output with text input for sending prompts.

**Features:**
- Live terminal output via `tmux capture-pane` polling
- Text input area for sending prompts
- AskUserQuestion popups
- Permission modals with diff preview
- Multiline input support (Enter to send, Shift+Enter for newline)

**Use for:**
- Observing Claude work in real-time
- Sending text prompts without voice
- Guided interaction with popups and modals
- Reading session output without full terminal features

**How it works:**
- Polls `tmux capture-pane` every 500ms for output
- Sends input via `tmux send-keys`
- One-way display (read-only, not a real terminal)
- Works even when Terminal mode is connected

### Terminal Mode

Full interactive terminal via xterm.js attached to tmux session.

**Features:**
- Real terminal emulation (xterm.js)
- Connected via `tmux attach` over WebSocket
- Full readline, vim, tab completion support
- Bidirectional input/output
- Hardware acceleration (WebGL when available)
- Clickable URLs (via xterm-addon-web-links)
- Auto-resize on browser window changes
- Terminal size shown in status (e.g., "Connected (120x40)")

**Use for:**
- Real development work
- Using vim, emacs, or other TUI editors
- Interactive commands (Python REPL, database shells)
- Full shell features (tab completion, command history)
- When Monitor mode's read-only view isn't enough

**Activation:**
1. Click Terminal tab
2. Click "Activate Interactive Terminal" button
3. Terminal connects via WebSocket to tmux session
4. Terminal stays connected even when switching to other modes

**Keyboard shortcuts** (only active when Terminal tab visible):

| Shortcut | Action |
|----------|--------|
| Cmd/Ctrl+K | Clear terminal (sends `clear` command) |
| Cmd/Ctrl+D | Disconnect terminal |

**Copy/paste:**
- Cmd/Ctrl+C, Cmd/Ctrl+V work natively
- Middle-click paste on Linux supported
- No UI hints shown (relies on standard browser behavior)

**Theme:**
- Automatically matches portal theme (dark/light)
- Updates when portal theme changes

**Desktop-only:**
- Terminal mode disabled on mobile/tablet devices
- Shows message: "Terminal mode requires desktop browser"

**Connection states:**

| State | Indicator | Meaning |
|-------|-----------|---------|
| Connected | Green | Active connection to tmux session |
| Connecting | Yellow | WebSocket establishing connection |
| Disconnected | Red | Connection lost or not started |
| Error | Amber | Connection failed, reconnect available |

**Error handling:**
- Shows user-friendly error messages
- Provides "Reconnect" button on failure
- Gracefully handles session termination
- Cleans up WebSocket on disconnect

### Simultaneous Operation

**All three modes work together:**

1. **Monitor + Terminal** - Monitor polling continues while Terminal is connected. Both see the same session output.
2. **Voice + Terminal** - Can use voice input in Ambient mode while Terminal mode shows the terminal.
3. **Local tmux + Portal** - Your local `tmux attach` works alongside both Monitor and Terminal modes. All attachments see the same session.

**Input from any mode appears in all modes:**
- Type in Monitor text input -> appears in Terminal
- Type in Terminal -> appears in Monitor output
- Voice prompt in Ambient -> appears in both Monitor and Terminal

**Why this works:**
- Monitor uses `tmux capture-pane` (read-only, doesn't interfere)
- Terminal uses `tmux attach` (one of many possible attachments)
- tmux allows multiple simultaneous attachments
- All modes read from the same tmux session

## Session UI Controls

The session page header provides device and voice controls:

| Control | Purpose |
|---------|---------|
| Mode tabs | Switch between Ambient, Monitor, and Terminal modes |
| Mic selector | Choose audio input device (saved to localStorage) |
| Speaker selector | Choose audio output device (Chrome/Edge only) |
| Voice selector | TTS voice for this session (saved to sessions.json) |

**Mode persistence:** Last selected mode is remembered per session in localStorage. Reloading the page restores your previous mode.

**Activity detection:** The portal auto-detects session activity - if any output appears (even from manual commands), the orb switches to Processing state. Returns to Ready after 10s of inactivity.

## Image Attachments

Attach images to messages for debugging, sharing screenshots, or reference:

| Method | Description |
|--------|-------------|
| Paste (Ctrl/Cmd+V) | Paste image from clipboard |
| Attach button | Click to select image file |

Images are uploaded to the configured `uploads.dir` and referenced in messages using Claude Code's `@/path/to/file` syntax. Configure in `config.yaml`:

```yaml
uploads:
  dir: "~/.agentwire/uploads"  # Should be accessible from all machines
  max_size_mb: 10
  cleanup_days: 7              # Auto-delete old uploads
```

## Multiline Text Input

The text input area supports multiline messages with auto-resize:

| Action | Result |
|--------|--------|
| Type text | Textarea auto-expands as content grows |
| **Enter** | Submits the message |
| **Shift+Enter** | Adds a newline (for multi-paragraph messages) |
| Clear text | Textarea collapses back to single line |

The textarea starts as a single line and dynamically expands up to 10 lines before scrolling. This provides a natural typing experience for both quick single-line messages and longer multi-paragraph prompts.

## Voice Output

Claude (or users) can trigger TTS using the unified `agentwire say` command:

```bash
agentwire say "Hello world"          # Smart routing to browser or local
agentwire say "Message" -v voice     # Specify voice
agentwire say "Message" -s session   # Specify session
```

**How it works:**

1. Command detects session from `--session`, `AGENTWIRE_SESSION` env var, or tmux session name
2. Checks if portal has active browser connections for that session
3. If connected -> Sends to portal (plays on browser/tablet)
4. If not connected -> Generates locally and plays via system audio

**Session detection priority:**
1. `--session` argument (explicit)
2. `AGENTWIRE_SESSION` env var (set automatically when session is created)
3. Current tmux session name (if running in tmux)

**For remote sessions:** `AGENTWIRE_SESSION` includes `@machine` suffix (e.g., `myproject@dotdev-pc`)

TTS audio includes 300ms silence padding to prevent first-syllable cutoff.

## AskUserQuestion Popup

When Claude Code uses the AskUserQuestion tool, the portal displays a modal with clickable options:

- Question text is spoken aloud via TTS when the popup appears
- Click any option to submit the answer
- "Type something" options show a text input with Send button
- Supports multi-line questions

## Actions Menu (Terminal Mode)

In monitor mode, a menu button appears above the mic button. Hover over action buttons to see labels.

**For regular project sessions:**

| Action | Icon | Description |
|--------|------|-------------|
| New Session | + | Creates a sibling session in a new worktree, opens in new tab (parallel work) |
| Fork Session | Fork | Forks the Claude Code conversation context into a new session (preserves history) |
| Recreate Session | Refresh | Destroys current session/worktree, pulls latest, creates fresh worktree and Claude Code session |

**Fork Session** uses Claude Code's `--resume <id> --fork-session` to create a new session that inherits the conversation context. Creates sessions named `project-fork-1`, `project-fork-2`, etc. Useful when you want to try different approaches without losing the current session's progress.

**For system sessions** (`agentwire`, `agentwire-portal`, `agentwire-tts`):

| Action | Icon | Description |
|--------|------|-------------|
| Restart Service | Refresh | Properly restarts the service (portal schedules delayed restart, TTS stops/starts, agentwire session restarts Claude) |

## Create Session Form

The dashboard's Create Session form supports machine selection, input validation, git detection, and worktree creation:

| Field | Description |
|-------|-------------|
| Session Name | Project name (blocks `@ / \ : * ? " < > |` and spaces) |
| Machine | Dropdown: Local or any configured remote machine |
| Project Path | Auto-fills to `{projectsDir}/{sessionName}` (editable) |
| Voice | TTS voice for the session |
| Permission Mode | Bypass (recommended) or Normal (prompted) |

**Git Repository Detection:**
When the project path points to a git repo, additional options appear:
- Current branch indicator (e.g., "on main")
- **Create worktree** checkbox (checked by default)
- **Branch Name** input with auto-suggested unique name (e.g., `jan-3-2026--1`)

**Smart Defaults:**
- Session name auto-fills path: typing `api` -> `~/projects/api`
- Machine selection updates path placeholder to remote's `projects_dir`
- Branch names auto-increment to avoid conflicts
- Last selected machine is remembered in localStorage

**Session Name Derivation:**

| Machine | Worktree | CLI Session Name |
|---------|----------|------------------|
| local | no | `myapp` |
| local | yes | `myapp/jan-3-2026--1` |
| gpu-server | no | `myapp@gpu-server` |
| gpu-server | yes | `myapp/jan-3-2026--1@gpu-server` |

## Portal API

### Core Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/sessions` | GET | List all tmux sessions |
| `/api/sessions/{name}` | DELETE | Close/kill a session |
| `/api/sessions/archive` | GET | List archived sessions |
| `/api/create` | POST | Create new session (accepts machine, worktree, branch) |
| `/api/check-path` | GET | Check if path exists and is git repo |
| `/api/check-branches` | GET | Get existing branches matching prefix |

### Session Management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/session/{name}/config` | POST | Update session config (voice, etc.) |
| `/api/session/{name}/recreate` | POST | Destroy and recreate session with fresh worktree |
| `/api/session/{name}/spawn-sibling` | POST | Create parallel session in new worktree |
| `/api/session/{name}/fork` | POST | Fork Claude Code session (preserves conversation) |
| `/api/session/{name}/restart-service` | POST | Restart system service |
| `/api/sessions/{name}/connections` | GET | Get connection count for session |

### Voice & Input

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/say/{name}` | POST | Generate TTS and broadcast to session |
| `/api/local-tts/{name}` | POST | Generate TTS for local playback |
| `/api/answer/{name}` | POST | Submit answer to AskUserQuestion |
| `/api/voices` | GET | List available TTS voices |
| `/transcribe` | POST | Transcribe audio (multipart form) |
| `/upload` | POST | Upload image (multipart form) |
| `/send/{name}` | POST | Send text to session |

### Machine Management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/machines` | GET | List configured machines |
| `/api/machines` | POST | Add a machine |
| `/api/machines/{id}` | DELETE | Remove a machine |
| `/api/machine/{id}/status` | GET | Get machine status |

### Configuration & Templates

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/config` | GET | Get current config |
| `/api/config` | POST | Save config |
| `/api/config/reload` | POST | Reload config from disk |
| `/api/templates` | GET | List templates |
| `/api/templates` | POST | Create template |
| `/api/templates/{name}` | GET | Get template details |
| `/api/templates/{name}` | DELETE | Delete template |

### Permission Handling

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/permission/{name}` | POST | Submit permission request (from hook) |
| `/api/permission/{name}/respond` | POST | User responds to permission request |

### WebSocket Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/ws/{name}` | Main session WebSocket (ambient/monitor modes) |
| `/ws/terminal/{name}` | Terminal attach WebSocket (xterm.js) |
