# Mission: Desktop Control Center

> Full frontend rewrite - replace all existing frontend code with a clean WinBox-based control center.

**Branch:** `mission/desktop-control-center` (created on execution)

## Context

The current `/desktop` page is a proof-of-concept using WinBox.js for draggable/resizable windows. It shows potential for a better UX than the main dashboard - more performant, familiar OS-like metaphor, and built-in window management.

This mission transforms it into a proper **control center** for orchestrating sessions across machines. Not every session needs to be visually open - the goal is quick access and visibility when needed.

## IMPORTANT: Full Rewrite

**This is a complete frontend rewrite, not a refactor.**

- **DELETE** any code, files, or assets not being used
- **REMOVE** the old dashboard, session pages, and their routes
- **CLEAN UP** docs, skills, instructions, comments referencing old attempts
- **NO** dead code, deprecated code, legacy fallbacks, or backwards-compat shims
- **RENAME** files/classes to fit the new architecture cleanly

The goal is a well-structured frontend with zero remnants from previous iterations. Multiple passes are expected - each pass should leave the codebase cleaner.

**Files likely to DELETE:**
- `static/js/dashboard.js`, `static/css/dashboard.css`
- `static/js/session.js`, `static/css/session.css`
- `templates/dashboard.html`, `templates/session.html`
- Any unused JS modules, CSS files, or assets
- Route handlers for removed pages

**Files to KEEP (refactor as needed):**
- `static/js/orb.js`, `static/css/orb.css` (for Chat feature)
- `static/js/terminal.js` (xterm.js utilities)
- `static/js/audio.js` (TTS playback)
- `static/js/websocket.js` (if useful, else rewrite)
- `templates/base.html` (update for new structure)

## Design Principles

- Clean desktop by default (logo wallpaper, nothing open)
- Black + green theme (consistent with branding)
- Windows open on-demand from menu bar (Sessions/Machines/Config each open as WinBox windows)
- Clear distinction: Monitor (read-only) vs Terminal (interactive)
- Desktop becomes root URL (`/`), old `/desktop` route removed
- Chat window = voice input to a selected session (not a separate assistant)
- Desktop-first design (mobile can be basic/degraded)

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required.

## Wave 2: Core Architecture

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Create `DesktopManager` class - singleton that manages windows, WebSocket, state | `static/js/desktop-manager.js` |
| 2.2 | Create `SessionWindow` class - encapsulates WinBox + terminal/monitor + cleanup | `static/js/session-window.js` |
| 2.3 | Create `ListWindow` class - reusable list window (sessions, machines, config) | `static/js/list-window.js` |
| 2.4 | Update CSS with clean black + green theme, logo wallpaper | `static/css/desktop.css` |

## Wave 3: Menu Windows

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Sessions window - list all sessions with status, "Monitor" and "Connect" buttons | `static/js/windows/sessions-window.js` |
| 3.2 | Machines window - list machines with status, connection info | `static/js/windows/machines-window.js` |
| 3.3 | Config window - display current config values (read-only) | `static/js/windows/config-window.js` |

## Wave 4: Session Modes

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 4.1 | Monitor mode window - read-only terminal view, auto-scroll, no input | 2.2 |
| 4.2 | Terminal mode window - full xterm.js interactive terminal | 2.2 |
| 4.3 | Add window icon using favicon, proper titles | 2.2 |

## Wave 5: Integration & Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 5.1 | Refactor `desktop.js` to use new classes, remove old code | 2.1, 2.2, 2.3 |
| 5.2 | Update `desktop.html` - simplify to just desktop container + menu trigger | 5.1 |
| 5.3 | Add taskbar window buttons, minimize/restore behavior | 5.1 |
| 5.4 | WebSocket reconnection and proper cleanup on window close | 2.1 |

## Wave 6: Chat & Voice Input

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 6.1 | Create `ChatWindow` class - orb + voice input targeting selected session | 2.2, existing orb.js |
| 6.2 | Add "Chat" menu item that opens ChatWindow with session selector | 5.1, 6.1 |
| 6.3 | Wire orb states to voice activity (listening, processing, speaking) | 6.1 |

## Wave 7: Cleanup & Documentation

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 7.1 | Delete old frontend files (dashboard.js/css, session.js/css, templates) | 5.1 |
| 7.2 | Update routes: `/` serves desktop, remove `/desktop` and `/session/` routes | 7.1 |
| 7.3 | Update CLAUDE.md - remove references to old frontend, document new structure | 7.1 |
| 7.4 | Update README.md - screenshots, feature descriptions for new UI | 7.1 |
| 7.5 | Clean up any skills/docs referencing old "portal modes" (ambient/monitor/terminal as separate pages) | 7.1 |
| 7.6 | Final pass - grep for dead imports, unused functions, TODO comments | 7.1-7.5 |

## Technical Notes

**WinBox usage pattern:**
```javascript
new WinBox({
    title: "Sessions",
    icon: "/static/favicon-green.jpeg",
    mount: containerElement,
    class: ["no-max", "no-full"],  // optional constraints
    onclose: () => cleanup()
});
```

**Session modes:**
- Monitor: Uses output-only WebSocket endpoint, no stdin
- Terminal: Full xterm.js with bidirectional WebSocket

**Theme colors:**
- Background: `#000000` (pure black)
- Accent: Extract green from logo (`#4ade80` or similar)
- Text: `#e2e8f0` (light gray)
- Window chrome: `#1a1a1a` (dark gray)

## Completion Criteria

**Functionality:**
- [ ] Desktop loads with logo wallpaper, empty by default
- [ ] Sessions menu opens Sessions window with Monitor/Connect buttons
- [ ] Machines menu opens Machines window with status
- [ ] Config menu opens Config window
- [ ] Monitor mode shows read-only terminal output
- [ ] Terminal mode provides full interactive terminal
- [ ] Windows can be dragged, resized, minimized to taskbar
- [ ] Multiple windows can be open simultaneously
- [ ] WebSocket properly disconnects on window close
- [ ] Chat window shows orb with voice states
- [ ] Clean black + green theme throughout

**Cleanup (REQUIRED):**
- [ ] Old dashboard/session pages deleted (JS, CSS, HTML templates)
- [ ] Old routes removed from server.py
- [ ] No dead code, unused imports, or unreachable functions
- [ ] No comments referencing old implementations
- [ ] No backwards-compat shims or legacy fallbacks
- [ ] CLAUDE.md updated with new frontend structure
- [ ] README.md updated (no references to old "portal modes")
- [ ] `grep -r "dashboard\|ambient\|monitor mode\|terminal mode"` returns no stale references
