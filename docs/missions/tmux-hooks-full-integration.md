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

| Hook | Fires When | Scope | Use Case |
|------|------------|-------|----------|
| `client-attached` | Client attaches to session | Global | Show presence indicator |
| `client-detached` | Client detaches from session | Global | Update presence count |
| `after-split-window` | New pane created | Global | Track pane creation |
| `session-renamed` | Session renamed | Global | Update UI, maintain tracking |
| `alert-activity` | Activity in monitored window | Global | Desktop notifications |
| `pane-focus-in` | Pane gains focus | Per-session | Track active pane, highlight in UI |

## Waves

### Wave 1: Human Actions (BLOCKING)

- [x] Review hook priority - confirmed order (presence → panes → rename → notifications → focus)
- [x] Decide on presence indicator UX - **user icon with count badge** (not tracking who, just count)

### Wave 2: Presence Tracking (client-attached/detached)

**Goal:** Show attachment count per session with user icon + badge.

- [x] Add `client_attached` and `client_detached` event types to notify endpoint
- [x] Install global hooks for client-attached and client-detached
- [x] Track attached client count per session in server state
- [x] Add user icon with count badge to sessions list UI
- [x] Handle edge case: multiple clients attached to same session

### Wave 3: Pane Creation (after-split-window)

**Goal:** Complete pane lifecycle tracking (we already have after-kill-pane).

- [x] Add `pane_created` handling for after-split-window hook
- [x] Install global hook for after-split-window (catches all pane creations)
- [x] Update sessions list pane counts in real-time
- [ ] Show new pane indicator/animation in UI *(nice-to-have)*

### Wave 4: Session Rename (session-renamed)

**Goal:** Keep UI in sync when sessions are renamed.

- [x] Add `session_renamed` event type with old/new names
- [x] Install global hook for session-renamed
- [x] Update session windows to track by ID not just name
- [x] Handle taskbar button updates on rename

### Wave 5: Activity Notifications (alert-activity)

**Goal:** Desktop notifications for background session activity.

- [x] Add `window_activity` event type
- [x] Install global hook for alert-activity
- [x] Implement browser notification permission request
- [x] Show desktop notification with session name and preview
- [ ] Add notification preferences to config *(nice-to-have)*

### Wave 6: Active Pane Tracking (pane-focus-in)

**Goal:** Know which pane is focused in multi-pane sessions.

- [x] Add `pane_focused` event type
- [x] Install hook in sessions with multiple panes (via _install_pane_hooks)
- [ ] Track active pane in session state *(nice-to-have)*
- [ ] Highlight active pane in worker dashboard view *(nice-to-have)*
- [ ] Update `agentwire info` to include active pane *(nice-to-have)*

### Wave 7: Polish & Edge Cases

- [x] Handle portal restart (re-install all hooks via _install_global_tmux_hooks)
- [ ] Clean up stale hooks from crashed sessions
- [ ] Add `agentwire hooks list` to show all installed hooks
- [ ] Rate limiting for high-frequency events (pane-focus-in)
- [ ] Documentation for hooks system

## Completion Criteria

- [x] Presence indicators show attached clients in sessions list
- [x] Pane counts update in real-time for both creation and destruction
- [x] Session renames propagate to open windows and taskbar
- [x] Desktop notifications fire for background session activity
- [ ] Active pane highlighted in multi-pane session views *(nice-to-have)*
- [x] All hooks survive portal restart
