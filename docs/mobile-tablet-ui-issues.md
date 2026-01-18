AgentWire Portal - Mobile/Tablet UI Issues Report
Test Environment:

Viewport: 500px × 750px (Tablet Portrait Mode)
URL: https://localhost:8765/
Date: January 18, 2026

Critical Issues

1. Fullscreen Chat Mode - No Exit Option
   Severity: Critical
   Location: Chat window fullscreen mode
   When the Chat window is maximized to fullscreen:

No visible button to exit fullscreen mode or return to windowed view
The top navigation bar (Sessions, Machines, Config, Chat) disappears completely
Pressing Escape key does not exit fullscreen
Users are effectively trapped in fullscreen mode with no obvious way to exit

Recommendation: Add a visible "Exit Fullscreen" or "X" button in the fullscreen Chat view, and/or enable Escape key to exit fullscreen.

High Priority Issues 2. Terminal/Monitor Text Truncation
Severity: High
Location: Terminal window, Monitor view
Text content is cut off on the right side without horizontal scrolling:

Terminal output text does not wrap properly and is truncated
URLs are cut off mid-string (e.g., https://github.com/GoogleChrome/developer.chrome.c...)
Log entries in Monitor view are split awkwardly across lines:

[agen on one line, connect on the next
trans on one line, ition: idle on the next

Recommendation: Implement either:

Horizontal scrolling for terminal/log content
Proper word-wrapping with preserved readability
A responsive font-size reduction for narrow viewports

3. Configuration Modal - Values Truncated
   Severity: High
   Location: Configuration modal
   Configuration values are cut off and unreadable:

"TTS Default Voice" shows only "ba..."
"STT URL" shows "http://localho..."
"Projects Directory" shows "/Users/dotdev/" (cut off)
"Agent Command" shows "claude --dangerously-sk..." (severely truncated)
"Machines File" shows "/Users/dotdev/.agentwire..." (cut off)

Recommendation:

Allow horizontal scrolling for value fields
Add tooltips on hover/tap to show full values
Consider a responsive layout that stacks label/value vertically on narrow screens

Medium Priority Issues 4. Multiple Overlapping Modal Windows
Severity: Medium
Location: All modals
When multiple modals are opened, they overlap and create visual clutter:

Opening Sessions, then Machines, then Config results in stacked modals
Background modals remain visible and partially obscured
Creates confusing visual hierarchy

Recommendation:

Auto-minimize previous modals when opening a new one
Or implement a single-modal policy for narrow viewports
Add a modal backdrop that dismisses/minimizes other modals

5. Machines Modal - Missing Window Controls
   Severity: Medium
   Location: Machines modal header
   The Machines modal appears to be missing standard window control buttons (minimize, maximize, fullscreen, close) that are present in other modals like Sessions.
   Recommendation: Ensure consistent window controls across all modals.
6. Navigation Bar Time Display Overflow
   Severity: Medium
   Location: Top navigation bar
   At 500px width, the time display (e.g., "07:49 AM") in the navigation bar wraps awkwardly or appears in an unexpected position.
   Recommendation:

Hide time display on narrow viewports
Or use a more compact time format (e.g., "7:49" without AM/PM)

Low Priority Issues 7. Window Control Buttons Cramped
Severity: Low
Location: Modal headers (Sessions, Chat)
The window control buttons (minimize, copy, fullscreen, close) in modal headers appear cramped at tablet width.
Recommendation: Consider spacing adjustments or combining some functions. 8. Minimized Window Taskbar
Severity: Low
Location: Bottom taskbar for minimized windows
When a modal is minimized, the taskbar at the bottom shows the window name with some controls, but the full set of controls may be cut off at narrow widths.
Recommendation: Ensure taskbar items are fully visible or provide a scrollable taskbar.

Summary
IssueSeverityComponentNo exit from fullscreen ChatCriticalChatTerminal text truncationHighTerminal/MonitorConfig values truncatedHighConfigurationOverlapping modalsMediumAll ModalsMissing window controlsMediumMachines ModalNav bar time overflowMediumNavigationWindow controls crampedLowModal HeadersTaskbar truncationLowMinimized Windows

Testing Notes

Main page layout and owl logo display correctly at 500px width
Navigation menu items (Sessions, Machines, Config, Chat, Connected, X sessions) are visible and tappable
Sessions list displays properly with Monitor/Connect buttons
Chat voice recording functionality works (LISTENING → GENERATING states)
Session connection status updates correctly
