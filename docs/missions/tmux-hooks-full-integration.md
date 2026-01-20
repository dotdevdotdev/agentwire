# Mission: Full Tmux Hooks Integration

> Leverage tmux hooks throughout AgentWire for real-time state tracking and enhanced UX.

## Background

With the tmux-portal-sync mission complete, we have the foundation:
- Global hooks for `session-created` and `session-closed`
- Per-session hooks for `after-kill-pane`
- `/api/notify` endpoint and `agentwire notify` command
- WebSocket broadcast infrastructure

Now we can expand to cover all useful tmux hooks.

## Hook Inventory

| Hook | Fires When | Use Case |
|------|------------|----------|
| `client-attached` | Client attaches to session | Show presence indicator (who's viewing) |
| `client-detached` | Client detaches from session | Update presence, detect orphaned sessions |
| `after-split-window` | New pane created | Track pane creation (complement to after-kill-pane) |
| `session-renamed` | Session renamed | Update UI, maintain session tracking |
| `alert-activity` | Activity in monitored window | Desktop notifications for background sessions |
| `pane-focus-in` | Pane gains focus | Track active pane, highlight in UI |
| `window-renamed` | Window renamed | Update window/pane labels in UI |

## Waves

### Wave 1: Human Actions (BLOCKING)

- [ ] Review hook priority - confirm order of implementation
- [ ] Decide on presence indicator UX (avatar, dot, tooltip?)

### Wave 2: Presence Tracking (client-attached/detached)

**Goal:** Show who's attached to each session in the portal.

- [ ] Add `client_attached` and `client_detached` event types to notify endpoint
- [ ] Install global hooks for client-attached and client-detached
- [ ] Track attached clients per session in server state
- [ ] Add presence indicator to sessions list UI
- [ ] Handle edge case: multiple clients attached to same session

### Wave 3: Pane Creation (after-split-window)

**Goal:** Complete pane lifecycle tracking (we already have after-kill-pane).

- [ ] Add `pane_created` handling for after-split-window hook
- [ ] Install hook in `cmd_spawn` and `cmd_split`
- [ ] Update sessions list pane counts in real-time
- [ ] Show new pane indicator/animation in UI

### Wave 4: Session Rename (session-renamed)

**Goal:** Keep UI in sync when sessions are renamed.

- [ ] Add `session_renamed` event type with old/new names
- [ ] Install global hook for session-renamed
- [ ] Update session windows to track by ID not just name
- [ ] Handle taskbar button updates on rename

### Wave 5: Activity Notifications (alert-activity)

**Goal:** Desktop notifications for background session activity.

- [ ] Add `session_activity` event type
- [ ] Install per-session hook when creating monitored sessions
- [ ] Implement browser notification permission request
- [ ] Show desktop notification with session name and preview
- [ ] Add notification preferences to config

### Wave 6: Active Pane Tracking (pane-focus-in)

**Goal:** Know which pane is focused in multi-pane sessions.

- [ ] Add `pane_focused` event type
- [ ] Install hook in sessions with multiple panes
- [ ] Track active pane in session state
- [ ] Highlight active pane in worker dashboard view
- [ ] Update `agentwire info` to include active pane

### Wave 7: Polish & Edge Cases

- [ ] Handle portal restart (re-install all hooks)
- [ ] Clean up stale hooks from crashed sessions
- [ ] Add `agentwire hooks list` to show all installed hooks
- [ ] Rate limiting for high-frequency events (pane-focus-in)
- [ ] Documentation for hooks system

## Completion Criteria

- [ ] Presence indicators show attached clients in sessions list
- [ ] Pane counts update in real-time for both creation and destruction
- [ ] Session renames propagate to open windows and taskbar
- [ ] Desktop notifications fire for background session activity
- [ ] Active pane highlighted in multi-pane session views
- [ ] All hooks survive portal restart
