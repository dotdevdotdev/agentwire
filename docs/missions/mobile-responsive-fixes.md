# Mission: Mobile/Tablet Responsive Fixes

> Fix UI issues identified during mobile/tablet testing at 500px viewport width.

**Branch:** `mission/mobile-responsive-fixes` (created on execution)

## Context

Testing at 500px viewport width revealed several responsive design issues affecting usability on tablets and phones. Issues range from critical (trapped in fullscreen) to low (cosmetic cramping).

Reference: `docs/mobile-tablet-ui-issues.md`

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required.

## Wave 2: Critical & High Priority

All tasks start immediately (no dependencies):

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | **Chat fullscreen exit** - Add visible exit button when Chat window is fullscreen. WinBox hides the title bar in fullscreen mode, trapping users. Add an overlay exit button and/or enable Escape key to exit. | `agentwire/static/js/windows/chat-window.js`, `agentwire/static/css/desktop.css` |
| 2.2 | **Terminal/Monitor text handling** - Fix text truncation in session output. Currently uses `white-space: pre-wrap` but content still gets cut off. Add horizontal scroll or improve word-wrap. Check the `.session-output` class and xterm container handling. | `agentwire/static/js/session-window.js`, `agentwire/static/css/desktop.css` |
| 2.3 | **Config modal responsive** - Config values are truncated (e.g., "http://localho..."). Add horizontal scroll for value fields, tooltips on hover/tap, or stack label/value vertically on narrow screens. | `agentwire/static/js/windows/config-window.js`, `agentwire/static/css/desktop.css` |
| 2.4 | **Maximized window title bar hidden** - When maximizing a window (not fullscreen), the title bar slides under the top menu bar and becomes invisible/inaccessible. The window is still draggable if you click just below the menu bar, but the title bar is hidden. Fix WinBox maximize positioning to account for menu bar height. Affects all screen sizes but critical on mobile. | `agentwire/static/css/desktop.css`, possibly `agentwire/static/js/list-window.js` or WinBox config |

## Wave 3: Medium Priority

All tasks start immediately (no dependencies):

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | **Modal overlap management** - When multiple modals open, they stack confusingly. Implement auto-minimize for previous modals or single-modal policy on narrow viewports. This affects the `desktop-manager.js` window registration system. | `agentwire/static/js/desktop-manager.js`, `agentwire/static/js/list-window.js` |
| 3.2 | **Machines window controls** - Add missing window control buttons (minimize, maximize, fullscreen, close) to match Sessions window. The Machines window uses `ListWindow` but may not have the same WinBox options. | `agentwire/static/js/windows/machines-window.js` |
| 3.3 | **Nav bar time responsive** - Time display wraps awkwardly at 500px. Hide time on narrow viewports or use compact format. Add CSS media query. | `agentwire/static/css/desktop.css` |

## Wave 4: Low Priority

All tasks start immediately (no dependencies):

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | **Window controls spacing** - WinBox header buttons (min/max/full/close) appear cramped at tablet width. Adjust spacing or hide some controls on narrow viewports. | `agentwire/static/css/desktop.css` |
| 4.2 | **Taskbar responsiveness** - Minimized window items in taskbar may be truncated. Ensure taskbar items are fully visible or add horizontal scroll. | `agentwire/static/css/desktop.css` |

## Technical Notes

### WinBox Fullscreen Behavior
WinBox hides the title bar when in fullscreen mode. The solution for 2.1 should add an overlay button that appears only in fullscreen state, positioned in a corner.

### ListWindow Component
Tasks 3.1 and 3.2 involve the shared `list-window.js` component used by Sessions, Machines, and Config windows. Changes here affect all three.

### CSS Media Queries
Most responsive fixes should use a consistent breakpoint. Recommend `@media (max-width: 600px)` for tablet/mobile targeting.

### Viewport Meta
Verify `base.html` has proper viewport meta tag for mobile scaling.

## Completion Criteria

- [ ] Chat window has working exit from fullscreen (button + Escape key)
- [ ] Terminal output readable without horizontal truncation
- [ ] Config values fully visible (scroll, tooltip, or stacked layout)
- [ ] Maximized windows show title bar below menu bar (not hidden under it)
- [ ] Only one modal visible at a time on narrow viewports (or clear z-index hierarchy)
- [ ] Machines window has same controls as Sessions window
- [ ] Time display doesn't wrap on narrow screens
- [ ] All changes tested at 500px viewport width
- [ ] No regressions on desktop (1200px+) viewport
