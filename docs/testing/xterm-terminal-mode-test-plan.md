# xterm.js Terminal Mode Test Plan

> Comprehensive testing scenarios for the three-mode portal system

## Test Environment Setup

**Prerequisites:**
- Local tmux session running Claude Code
- Portal running on https://localhost:8765
- Browser with WebSocket support
- Test project with git repo (for worktree testing)

## Test Matrix

### Core Functionality Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T1 | Create session via portal | 1. Open dashboard<br>2. Fill session form<br>3. Click Create | Session appears, starts in Ambient mode | |
| T2 | Switch to Monitor mode | 1. Open room<br>2. Click Monitor tab | Shows terminal output, text input visible | |
| T3 | Switch to Terminal mode | 1. Click Terminal tab<br>2. Click "Activate Terminal" | xterm.js loads, connects to tmux, shows live terminal | |
| T4 | Terminal remains connected on tab switch | 1. Activate Terminal<br>2. Switch to Ambient<br>3. Switch back to Terminal | Terminal still connected, shows recent output | |
| T5 | Monitor shows output while Terminal active | 1. Activate Terminal<br>2. Switch to Monitor<br>3. Run command in Terminal<br>4. Check Monitor | Both modes show same output | |

### Input Handling Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T6 | Type in Monitor text input | 1. Monitor mode<br>2. Type "pwd" + Enter | Command appears in both Monitor and Terminal (if connected) | |
| T7 | Type in Terminal | 1. Terminal mode<br>2. Type characters | Characters appear immediately, full terminal features work | |
| T8 | Voice input in Ambient | 1. Ambient mode<br>2. Hold mic, speak prompt<br>3. Release | Transcription appears, sent to session | |
| T9 | All three inputs work together | 1. Activate Terminal<br>2. Switch between modes<br>3. Send input from each mode | All inputs appear in session, all modes see output | |

### Interactive Features Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T10 | AskUserQuestion in Ambient | 1. Ambient mode<br>2. Trigger AskUserQuestion<br>3. Click option | Modal appears, TTS speaks question, selection submitted | |
| T11 | AskUserQuestion in Monitor | 1. Monitor mode<br>2. Trigger AskUserQuestion | Modal appears over monitor view, works correctly | |
| T12 | Permission modal in Monitor | 1. Normal mode session<br>2. Trigger permission request in Monitor | Modal appears with diff preview, allow/deny works | |
| T13 | Vim in Terminal | 1. Terminal mode<br>2. Run `vim test.txt`<br>3. Edit file<br>4. Save and quit | Vim works normally, full terminal control | |
| T14 | Interactive prompts in Terminal | 1. Terminal mode<br>2. Run interactive command (e.g., `python`)<br>3. Type input | REPL works, input/output bidirectional | |

### Connection Management Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T15 | Terminal connection failure | 1. Terminal mode<br>2. Simulate connection failure<br>3. Check UI | Error message shown, reconnect button appears | |
| T16 | Reconnect after disconnect | 1. Terminal disconnected<br>2. Click Reconnect | Terminal reconnects, shows current session state | |
| T17 | Kill session with Terminal active | 1. Terminal mode connected<br>2. Kill session via CLI | Terminal shows disconnection, Monitor shows session ended | |
| T18 | Terminal resize | 1. Terminal mode<br>2. Resize browser window<br>3. Check terminal | Terminal resizes correctly, tmux window size updates | |

### Local tmux Compatibility Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T19 | Local tmux attach alongside portal | 1. Terminal mode connected<br>2. Attach via local tmux<br>3. Type in local terminal | All three attachments see same session, all can send input | |
| T20 | Monitor polling doesn't interfere | 1. Monitor mode active<br>2. Local tmux attached<br>3. Terminal mode connected | All three work simultaneously without conflicts | |
| T21 | Detach local, others continue | 1. All three connected<br>2. Detach local tmux<br>3. Check portal modes | Portal modes unaffected by local detach | |

### Session Lifecycle Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T22 | Create worktree session | 1. Dashboard<br>2. Create session with worktree<br>3. Check Terminal mode | Session starts in correct directory (worktree path) | |
| T23 | Fork session preserves Terminal | 1. Terminal mode active<br>2. Fork session<br>3. Check new session | New session has Terminal available, conversation context preserved | |
| T24 | Recreate session cleans up Terminal | 1. Terminal connected<br>2. Recreate session<br>3. Check new session | Old Terminal disconnects, new session starts fresh | |

### UI/UX Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T25 | Mode selector shows all three tabs | 1. Open room<br>2. Check mode selector | Three tabs visible: Ambient, Monitor, Terminal | |
| T26 | Last mode remembered per room | 1. Switch to Terminal<br>2. Reload page | Terminal mode still selected (from localStorage) | |
| T27 | Terminal status indicator | 1. Terminal mode<br>2. Connect<br>3. Check status | Shows "Connected (120x40)" with green indicator | |
| T28 | Keyboard shortcuts only in Terminal | 1. Terminal mode, Cmd+K clears<br>2. Switch to Monitor, try Cmd+K | Shortcuts work in Terminal, don't interfere in other modes | |
| T29 | Mobile detection | 1. Open room on mobile device<br>2. Click Terminal tab | Shows desktop-only message, no activation button | |

### Theme and Styling Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T30 | Terminal matches portal theme | 1. Dark mode portal<br>2. Activate Terminal<br>3. Check colors | Terminal uses dark theme (bg: #1e1e1e) | |
| T31 | Terminal adapts to theme change | 1. Terminal active<br>2. Toggle portal theme<br>3. Check Terminal | Terminal theme updates to match portal | |

### Performance Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T32 | Terminal handles rapid output | 1. Terminal mode<br>2. Run `yes` or similar<br>3. Observe performance | Terminal remains responsive, no lag | |
| T33 | Monitor polling doesn't slow Terminal | 1. Monitor and Terminal both active<br>2. Type in Terminal<br>3. Observe latency | No noticeable latency from Monitor polling | |
| T34 | WebGL addon loads | 1. Activate Terminal<br>2. Check browser console | WebGL addon loads successfully (or falls back to canvas) | |

### Error Handling Tests

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|----------------|--------|
| T35 | Session doesn't exist | 1. Navigate to /room/nonexistent<br>2. Try activating Terminal | Clear error message, no WebSocket errors | |
| T36 | WebSocket connection drops | 1. Terminal connected<br>2. Simulate network drop<br>3. Check UI | Terminal shows disconnected state, reconnect option | |
| T37 | tmux attach fails | 1. Terminal mode<br>2. Session locked by another process<br>3. Check error | User-friendly error message, reconnect option | |

## Testing Procedures

### Manual Testing Checklist

For each release/PR, run through:

1. **Core Flows** (T1-T5): Verify basic mode switching works
2. **Input Methods** (T6-T9): Test all three input mechanisms
3. **Interactive Features** (T10-T14): Verify modals, vim, prompts
4. **Connection** (T15-T18): Test connection reliability
5. **Compatibility** (T19-T21): Verify local tmux compatibility

### Automated Testing

**Future enhancement:** Automate key scenarios using Playwright:

```javascript
// Example automated test
test('Terminal mode activation', async ({ page }) => {
  await page.goto('https://localhost:8765/room/test-session');
  await page.click('[data-mode="terminal"]');
  await page.click('#activateTerminal');
  await expect(page.locator('#terminal')).toBeVisible();
  await expect(page.locator('.terminal-status')).toContainText('Connected');
});
```

## Known Limitations

Document any known issues discovered during testing:

1. **Copy/paste on mobile** - May not work consistently across all browsers
2. **WebGL fallback** - Some older browsers won't support WebGL, falls back to canvas
3. **SSH sessions** - Remote sessions via SSH may have additional latency
4. **Very large output** - Extremely rapid output (10k+ lines/sec) may cause slowdown

## Test Results Template

```markdown
## Test Run: [Date]

**Environment:**
- Portal version: [version]
- Browser: [browser + version]
- OS: [macOS/Linux/Windows]
- Session type: [local/remote/worktree]

**Results:**

| Test ID | Status | Notes |
|---------|--------|-------|
| T1 | ✅ Pass | |
| T2 | ✅ Pass | |
| T3 | ⚠️ Warning | WebGL fallback to canvas |
| T4 | ✅ Pass | |
| ... | | |

**Issues Found:**
- [Issue description]

**Overall Assessment:**
[Pass/Fail with summary]
```

## Regression Testing

After any changes to:
- WebSocket handling (`server.py`)
- Terminal mode UI (`room.html`, `terminal.js`)
- Mode switching logic (`room.js`)

Run at minimum: T1-T5, T10-T14, T19-T21

## User Acceptance Testing

Have real users test:
1. Create a session and explore all three modes
2. Use Terminal mode for real development work (vim, git, etc.)
3. Switch between modes during active Claude session
4. Provide feedback on UX, performance, and reliability

## Sign-off Criteria

Before marking Wave 9 complete:

- [ ] All Core Functionality tests (T1-T5) pass
- [ ] All Input Handling tests (T6-T9) pass
- [ ] All Interactive Features tests (T10-T14) pass
- [ ] All Connection Management tests (T15-T18) pass
- [ ] All Local tmux Compatibility tests (T19-T21) pass
- [ ] At least 90% of all other tests pass
- [ ] No critical bugs identified
- [ ] Documentation updated
- [ ] At least 2 real users have tested successfully
