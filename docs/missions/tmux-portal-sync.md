# Mission: Tmux-Portal Sync via Hooks

> Use tmux hooks to keep portal UI in sync with session state changes.

## Problem

When sessions are killed (via CLI, manual tmux, or crash), the portal doesn't know:
- Session windows stay open showing stale content
- Sessions list doesn't update
- Users must manually refresh

## Solution

Use tmux hooks to notify the portal of state changes in real-time.

## Relevant Hooks

From `docs/tmux-hooks.md`:

| Hook | Fires When | Use Case |
|------|------------|----------|
| `session-closed` | Session destroyed | Remove from sessions list, close windows |
| `pane-died` | Pane process exits | Update pane count, close worker windows |
| `session-created` | New session | Add to sessions list |
| `window-pane-changed` | Pane focus changes | Update active pane indicator |

## Architecture

```
tmux hook fires
    ↓
run-shell calls agentwire notify
    ↓
agentwire notify POSTs to portal WebSocket
    ↓
portal broadcasts to connected clients
    ↓
client JS updates UI (closes window, refreshes list)
```

## Waves

### Wave 1: Portal Notification Endpoint (Human: None)

- [ ] Add `/api/notify` endpoint to portal server
- [ ] Endpoint accepts `{event: "session-closed", session: "name"}` etc.
- [ ] Portal broadcasts event to all connected WebSocket clients
- [ ] Client JS handlers for each event type

### Wave 2: CLI Notify Command

- [ ] Add `agentwire notify <event> --session <name>` command
- [ ] Calls portal `/api/notify` endpoint
- [ ] Works locally and remotely (uses portal URL from config)

### Wave 3: Hook Installation

- [ ] Add hook setup to `agentwire new` (session-created, session-closed)
- [ ] Add hook setup to `agentwire spawn` (pane-died for workers)
- [ ] Hooks call `agentwire notify` via `run-shell`
- [ ] Handle hook persistence (server vs session scope)

### Wave 4: Client UI Updates

- [ ] `session-closed` → close session window, remove from list
- [ ] `pane-died` → update pane count, close worker window if applicable
- [ ] `session-created` → add to sessions list (if not already there)
- [ ] Debounce rapid events

### Wave 5: Cleanup & Edge Cases

- [ ] Handle portal restart (hooks still installed, portal comes back)
- [ ] Handle remote sessions (notify via SSH tunnel or remote portal)
- [ ] Add `agentwire hooks status` to show installed hooks
- [ ] Clean up hooks on session kill

## Completion Criteria

- [ ] Killing a session via CLI immediately closes its portal window
- [ ] Killing a session via raw `tmux kill-session` also updates portal
- [ ] Spawning/killing worker panes updates portal pane counts
- [ ] Works for both local and remote sessions
