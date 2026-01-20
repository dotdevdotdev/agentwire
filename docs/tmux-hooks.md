# tmux Hooks

> Research for event-driven session tracking in AgentWire.

tmux provides a hook system that runs commands in response to events. This enables AgentWire to receive real-time notifications when sessions are created, closed, or modified—eliminating the need for polling.

## Available Hooks

### Session Lifecycle

| Hook | Trigger |
|------|---------|
| `session-created` | New session created |
| `session-closed` | Session destroyed |
| `session-renamed` | Session name changed |
| `session-window-changed` | Active window changed in session |

### Client Events

| Hook | Trigger |
|------|---------|
| `client-attached` | Client attached to session |
| `client-detached` | Client detached from session |
| `client-active` | Client becomes the latest active client of its session |
| `client-session-changed` | Client switches to different session |
| `client-focus-in` | Focus enters client |
| `client-focus-out` | Focus exits client |
| `client-resized` | Client terminal resized |

### Window Events

| Hook | Trigger |
|------|---------|
| `window-linked` | Window linked into a session |
| `window-unlinked` | Window unlinked from a session |
| `window-renamed` | Window name changed |
| `window-resized` | Window resized |

### Pane Events

| Hook | Trigger |
|------|---------|
| `pane-died` | Program exits but pane remains (remain-on-exit on) |
| `pane-exited` | Program in pane exits |
| `pane-focus-in` | Focus enters pane (requires focus-events on) |
| `pane-focus-out` | Focus exits pane (requires focus-events on) |
| `pane-set-clipboard` | Terminal clipboard set via xterm escape sequence |

### Alert Hooks

| Hook | Trigger |
|------|---------|
| `alert-activity` | Window has activity (see monitor-activity) |
| `alert-bell` | Window received a bell |
| `alert-silence` | Window has been silent (see monitor-silence) |

### Command Hooks

| Hook | Trigger |
|------|---------|
| `command-error` | A tmux command fails |
| `after-*` | Runs after specific commands (e.g., `after-new-session`, `after-kill-pane`) |

The `after-*` hooks exist for most tmux commands. Run `tmux show-hooks -g` to see the full list.

## Setting Hooks

### Basic Syntax

```bash
# Set a global hook (applies to all sessions)
tmux set-hook -g <hook-name> '<command>'

# Set a session-specific hook
tmux set-hook -t <session> <hook-name> '<command>'

# Append to existing hook (creates array)
tmux set-hook -ag <hook-name> '<command>'

# Unset a hook
tmux set-hook -gu <hook-name>

# Run a hook immediately (for testing)
tmux set-hook -R <hook-name>
```

### Hook Arrays

Multiple commands can be attached to the same hook using array indices:

```bash
# First hook (index 0)
tmux set-hook -g session-created 'run-shell "echo created >> /tmp/log"'

# Append second hook (index 1)
tmux set-hook -ag session-created 'run-shell "curl -X POST http://localhost:8080/webhook"'

# Result:
# session-created[0] run-shell "echo created >> /tmp/log"
# session-created[1] run-shell "curl -X POST http://localhost:8080/webhook"
```

Set a specific index explicitly:

```bash
tmux set-hook -g session-created[42] 'run-shell "..."'
```

Setting a hook without an index clears all existing hooks for that event and sets index 0.

### Viewing Hooks

```bash
# Show all global hooks
tmux show-hooks -g

# Show session-specific hooks
tmux show-hooks -t <session>
```

## Running Shell Commands

Use `run-shell` to execute shell commands from hooks:

```bash
tmux set-hook -g session-created 'run-shell "echo #{session_name} >> /tmp/sessions.log"'
```

### run-shell Options

| Flag | Effect |
|------|--------|
| `-b` | Run in background (don't block tmux) |
| `-C` | Run as tmux command instead of shell command |
| `-c <dir>` | Set working directory |
| `-d <secs>` | Delay execution by N seconds |
| `-t <pane>` | Target pane for output |

**Important:** Without `-b`, `run-shell` blocks tmux until the command completes. Always use `-b` for network calls or slow operations.

```bash
# Non-blocking webhook call
tmux set-hook -g session-created 'run-shell -b "curl -s http://localhost:8080/hook"'
```

## Format Variables

Hook commands are expanded using tmux's format system. Key variables for hooks:

### Hook-Specific Variables

| Variable | Description |
|----------|-------------|
| `#{hook}` | Name of the running hook |
| `#{hook_session}` | ID of session where hook ran |
| `#{hook_session_name}` | Name of session where hook ran |
| `#{hook_window}` | ID of window where hook ran |
| `#{hook_window_name}` | Name of window where hook ran |
| `#{hook_pane}` | ID of pane where hook ran |
| `#{hook_client}` | Name of client where hook ran |

### Common Session/Window/Pane Variables

| Variable | Alias | Description |
|----------|-------|-------------|
| `#{session_name}` | `#S` | Session name |
| `#{session_id}` | | Unique session ID (e.g., `$0`) |
| `#{window_id}` | | Unique window ID (e.g., `@0`) |
| `#{window_name}` | `#W` | Window name |
| `#{pane_id}` | `#D` | Unique pane ID (e.g., `%0`) |
| `#{pane_pid}` | | PID of process in pane |
| `#{pane_current_path}` | | Current working directory |

### Example: Rich Webhook Payload

```bash
tmux set-hook -g session-created 'run-shell -b "curl -s -X POST http://localhost:8080/tmux/session-created \
  -H \"Content-Type: application/json\" \
  -d \"{\\\"session\\\": \\\"#{session_name}\\\", \\\"id\\\": \\\"#{session_id}\\\"}\""'
```

## Persistence

**Hooks do NOT persist across tmux server restarts.** They are runtime configuration only.

### Making Hooks Persistent

Add hook configuration to `~/.tmux.conf`:

```bash
# ~/.tmux.conf
set-hook -g session-created 'run-shell -b "curl -s http://localhost:8080/session-created?name=#{session_name}"'
set-hook -g session-closed 'run-shell -b "curl -s http://localhost:8080/session-closed?name=#{hook_session_name}"'
```

Reload config: `tmux source-file ~/.tmux.conf`

### Server Lifecycle

- Hooks only exist while the tmux server is running
- When all sessions close, the server exits and hooks are lost
- On next `tmux` command, server restarts and reads `~/.tmux.conf`
- If tmux server crashes, hooks are lost (read from config on restart)

## Gotchas and Limitations

### 1. session-closed Uses hook_session_name

When a session closes, `#{session_name}` is empty. Use `#{hook_session_name}` instead:

```bash
# WRONG - session_name is empty
tmux set-hook -g session-closed 'run-shell "echo #{session_name}"'

# RIGHT - use hook_session_name
tmux set-hook -g session-closed 'run-shell "echo #{hook_session_name}"'
```

### 2. Blocking Commands Freeze tmux

Without `-b`, `run-shell` blocks all tmux operations until the command completes:

```bash
# BAD - blocks tmux for 5 seconds on every session create
tmux set-hook -g session-created 'run-shell "sleep 5"'

# GOOD - runs in background
tmux set-hook -g session-created 'run-shell -b "sleep 5"'
```

### 3. Quote Escaping is Tricky

Nested quotes require careful escaping:

```bash
# Shell → tmux → shell → command
tmux set-hook -g session-created 'run-shell "echo \"session: #{session_name}\""'

# For JSON, escape is even deeper
tmux set-hook -g session-created 'run-shell -b "curl -d \"{\\\"name\\\": \\\"#{session_name}\\\"}\""'
```

### 4. No Hook for "Session About to Close"

There's no pre-close hook. `session-closed` fires after the session is already destroyed. The session's panes and windows are gone.

### 5. Hooks Run in tmux Server Context

Hooks run in the tmux server process, not in any terminal or session. Environment variables from your shell are not available.

### 6. Error Handling

If a hook command fails, tmux continues normally. Use `command-error` hook to catch failures:

```bash
tmux set-hook -g command-error 'run-shell -b "echo \"tmux error\" >> /tmp/tmux-errors.log"'
```

### 7. Array Index Behavior

Setting a hook without an index **clears all existing hooks** for that event:

```bash
tmux set-hook -g session-created 'echo first'   # Sets [0]
tmux set-hook -ag session-created 'echo second' # Appends [1]
tmux set-hook -g session-created 'echo third'   # CLEARS both, sets [0]
```

## Common Use Cases

### Logging Session Activity

```bash
# Log all session lifecycle events
tmux set-hook -g session-created 'run-shell -b "echo \"$(date): created #{session_name}\" >> ~/.tmux-sessions.log"'
tmux set-hook -g session-closed 'run-shell -b "echo \"$(date): closed #{hook_session_name}\" >> ~/.tmux-sessions.log"'
```

### Desktop Notifications

```bash
# macOS notification on session close
tmux set-hook -g session-closed 'run-shell -b "osascript -e \"display notification \\\"Session closed: #{hook_session_name}\\\" with title \\\"tmux\\\"\""'
```

### Auto-Rename Windows

```bash
# Rename window to current directory
tmux set-hook -g after-select-pane 'run-shell "tmux rename-window \"#{b:pane_current_path}\""'
```

### Sync Session List

```bash
# Write session list to file on any session change
tmux set-hook -g session-created 'run-shell -b "tmux list-sessions > /tmp/tmux-sessions"'
tmux set-hook -g session-closed 'run-shell -b "tmux list-sessions > /tmp/tmux-sessions"'
```

## AgentWire Integration

### Recommended Approach: Webhook Notifications

Instead of polling `tmux list-sessions`, set hooks to notify the portal of changes:

```bash
# In ~/.tmux.conf or set programmatically
PORTAL_URL="http://localhost:8765"

set-hook -g session-created 'run-shell -b "curl -s -X POST ${PORTAL_URL}/api/tmux/session-created \
  -H \"Content-Type: application/json\" \
  -d \"{\\\"name\\\": \\\"#{session_name}\\\", \\\"id\\\": \\\"#{session_id}\\\"}\""'

set-hook -g session-closed 'run-shell -b "curl -s -X POST ${PORTAL_URL}/api/tmux/session-closed \
  -H \"Content-Type: application/json\" \
  -d \"{\\\"name\\\": \\\"#{hook_session_name}\\\"}\""'

set-hook -g session-renamed 'run-shell -b "curl -s -X POST ${PORTAL_URL}/api/tmux/session-renamed \
  -H \"Content-Type: application/json\" \
  -d \"{\\\"name\\\": \\\"#{session_name}\\\", \\\"id\\\": \\\"#{session_id}\\\"}\""'
```

### Portal Webhook Endpoints

The portal would need these endpoints:

```python
@app.post("/api/tmux/session-created")
async def on_session_created(data: dict):
    name = data["name"]
    session_id = data["id"]
    # Update internal session list
    # Broadcast to WebSocket clients
    await broadcast({"type": "session_created", "name": name})

@app.post("/api/tmux/session-closed")
async def on_session_closed(data: dict):
    name = data["name"]
    # Remove from internal list
    # Broadcast to WebSocket clients
    await broadcast({"type": "session_closed", "name": name})
```

### Hook Installation Script

AgentWire could install hooks on startup:

```python
def install_tmux_hooks(portal_url: str):
    hooks = [
        ("session-created", f'run-shell -b "curl -s -X POST {portal_url}/api/tmux/session-created ..."'),
        ("session-closed", f'run-shell -b "curl -s -X POST {portal_url}/api/tmux/session-closed ..."'),
        ("session-renamed", f'run-shell -b "curl -s -X POST {portal_url}/api/tmux/session-renamed ..."'),
    ]
    for hook_name, command in hooks:
        subprocess.run(["tmux", "set-hook", "-g", hook_name, command])

def uninstall_tmux_hooks():
    for hook in ["session-created", "session-closed", "session-renamed"]:
        subprocess.run(["tmux", "set-hook", "-gu", hook])
```

### Fallback Strategy

Since hooks don't persist across tmux server restarts:

1. **On portal start:** Install hooks via `tmux set-hook`
2. **Periodic check:** Every 60s, verify hooks are still set
3. **Initial sync:** On startup, poll once to get current state
4. **Event-driven after:** Rely on webhooks for real-time updates

### Benefits Over Polling

| Aspect | Polling | Hooks + Webhooks |
|--------|---------|------------------|
| Latency | 1-5s (poll interval) | ~50ms (instant) |
| CPU usage | Constant | Only on events |
| Scalability | Degrades with sessions | Constant |
| Complexity | Simple | Moderate |
| Reliability | High (always works) | Needs fallback |

## References

- `man tmux` - HOOKS section
- `man tmux` - FORMATS section for variable expansion
- `tmux show-hooks -g` - List all available hooks
- `tmux list-commands` - See set-hook, show-hooks commands
