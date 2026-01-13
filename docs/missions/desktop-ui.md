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
- [ ] **2.1** Add WinBox.js to static assets
- [ ] **2.2** Create `/desktop` route in server.py
- [ ] **2.3** Create `desktop.html` template with basic structure (menu bar, desktop area, taskbar)
- [ ] **2.4** Create `desktop.css` with OS-like styling

### Wave 3: Window System
- [ ] **3.1** Create session window component (terminal view in WinBox)
- [ ] **3.2** Implement window spawning from menu/taskbar
- [ ] **3.3** Add window state management (track open windows)
- [ ] **3.4** Create `desktop.js` for window orchestration

### Wave 4: Menu Bar
- [ ] **4.1** Sessions menu - list/create sessions
- [ ] **4.2** Machines menu - show connected machines
- [ ] **4.3** Voice menu - hold-to-talk button, voice settings
- [ ] **4.4** Status indicators (connection status, active sessions count)

### Wave 5: Session Windows
- [ ] **5.1** Terminal output view in window (reuse output_view component)
- [ ] **5.2** Voice orb integration per window
- [ ] **5.3** Session actions (kill, rename) in window title bar
- [ ] **5.4** Multi-session support (multiple windows open)

### Wave 6: Polish
- [ ] **6.1** Taskbar with window buttons
- [ ] **6.2** Window minimize/restore behavior
- [ ] **6.3** Keyboard shortcuts (Alt+Tab style switching?)
- [ ] **6.4** Persist window positions in localStorage

## Completion Criteria

- [ ] `/desktop` route loads and shows menu bar + empty desktop
- [ ] Can open session windows from menu
- [ ] Windows are draggable/resizable
- [ ] Terminal output displays in windows
- [ ] Voice input works per-window
- [ ] Multiple sessions can be open simultaneously

## References

- WinBox.js: https://nextapps-de.github.io/winbox/
- Current dashboard: `agentwire/templates/dashboard.html`
- Session view: `agentwire/templates/session.html`
