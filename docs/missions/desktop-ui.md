# Mission: Desktop UI

OS-like interface for AgentWire portal with floating windows, menu bar, and improved UX.

## Goal

Create a new `/desktop` route that provides a desktop-like experience:
- Menu bar with app launcher
- Floating/resizable windows for sessions
- Window management (minimize, maximize, close)
- Taskbar showing open windows
- Clean, modern aesthetic

## Tech Stack

- **WinBox.js** - Lightweight window manager (12kb, no deps)
- **Jinja2** - Keep existing template system
- **Vanilla JS** - Keep it simple, no React needed

## Waves

### Wave 1: Human Actions (BLOCKING)
- [ ] None - no external setup needed

### Wave 2: Foundation
- [x] **2.1** Add WinBox.js to static assets
- [x] **2.2** Create `/desktop` route in server.py
- [x] **2.3** Create `desktop.html` template with basic structure (menu bar, desktop area, taskbar)
- [x] **2.4** Create `desktop.css` with OS-like styling

### Wave 3: Window System
- [x] **3.1** Create session window component (terminal view in WinBox)
- [x] **3.2** Implement window spawning from menu/taskbar
- [x] **3.3** Add window state management (track open windows)
- [x] **3.4** Create `desktop.js` for window orchestration

### Wave 4: Menu Bar
- [x] **4.1** Sessions menu - list/create sessions
- [x] **4.2** Machines menu - show connected machines
- [x] **4.3** Voice menu - hold-to-talk button, voice settings
- [x] **4.4** Status indicators (connection status, active sessions count)

### Wave 5: Session Windows
- [x] **5.1** Terminal output view in window (interactive xterm.js terminal)
- [ ] **5.2** Voice orb integration per window
- [ ] **5.3** Session actions (kill, rename) in window title bar
- [x] **5.4** Multi-session support (multiple windows open)

### Wave 6: Polish
- [x] **6.1** Taskbar with window buttons
- [x] **6.2** Window minimize/restore behavior
- [ ] **6.3** Keyboard shortcuts (Alt+Tab style switching?)
- [ ] **6.4** Persist window positions in localStorage

## Completion Criteria

- [x] `/desktop` route loads and shows menu bar + empty desktop
- [x] Can open session windows from menu
- [x] Windows are draggable/resizable
- [x] Terminal output displays in windows (interactive xterm.js)
- [ ] Voice input works per-window
- [x] Multiple sessions can be open simultaneously

## References

- WinBox.js: https://nextapps-de.github.io/winbox/
- Current dashboard: `agentwire/templates/dashboard.html`
- Session view: `agentwire/templates/session.html`
