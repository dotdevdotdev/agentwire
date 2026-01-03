# Mission: Restricted Session Mode

> Add a "restricted" mode that only allows say/remote-say commands, auto-denying all other tool requests.

**Branch:** `mission/restricted-mode` (created on execution)

## Context

Currently sessions have two permission modes:
- **Bypass**: Auto-accepts everything (`--dangerously-skip-permissions`)
- **Prompted**: Shows permission modal for user approval

We need a third mode:
- **Restricted**: Only allows `say` and `remote-say` Bash commands, auto-denies everything else

This is useful for voice-only assistants or chatbot-style sessions where Claude should only speak, not modify files or run arbitrary commands.

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - all code changes.

---

## Wave 2: Core Infrastructure

All tasks start immediately (no dependencies):

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Add `restricted` field to RoomConfig dataclass with default False | `server.py` |
| 2.2 | Update `_get_room_config` to read restricted from rooms.json | `server.py` |
| 2.3 | Update `api_sessions` to return `restricted` field in response | `server.py` |

---

## Wave 3: Permission Handling

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 3.1 | Update `api_permission_request` to check restricted mode and auto-handle | 2.1, 2.2 |
| 3.2 | Add helper function `_is_allowed_in_restricted_mode(tool_name, tool_input)` - returns True for Bash(say/remote-say) | None - starts immediately |

**3.1 Logic:**
- If room is restricted:
  - If `_is_allowed_in_restricted_mode()` returns True → send keystroke "2" (allow_always), return immediately
  - Else → send keystroke "Escape" (deny silently), return deny response
- If not restricted: existing flow (show popup, wait for user)

Note: Silent deny chosen over custom message ("3" + text) to keep response fast and avoid TTS chatter.

---

## Wave 4: CLI Support

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 4.1 | Add `--restricted` flag to `agentwire new` command parser | None - starts immediately |
| 4.2 | Update `cmd_new` to save `restricted: true` to rooms.json when flag used | None - starts immediately |
| 4.3 | Ensure `--restricted` implies `--no-bypass` (restricted makes no sense with bypass) | 4.1 |

---

## Wave 5: Dashboard UI

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 5.1 | Update dashboard JS to show "Restricted" badge (orange?) for restricted sessions | 2.3 |
| 5.2 | Add CSS for `.session-badge.restricted` styling | None - starts immediately |
| 5.3 | Add "Restricted" radio option to Create Session form permission mode | None - starts immediately |
| 5.4 | Update form submission to send `restricted: true` when selected | 5.3 |

---

## Wave 6: Server Create Session

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 6.1 | Update `api_create_session` to accept and save `restricted` field | 2.1 |
| 6.2 | When restricted=true, ensure session is created without bypass (normal mode) | 6.1 |

---

## Wave 7: Testing & Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 7.1 | Manual test: create restricted session via CLI, verify say works, other commands denied | All previous waves |
| 7.2 | Manual test: create restricted session via dashboard, verify badges show correctly | All previous waves |
| 7.3 | Update CLAUDE.md with restricted mode documentation | None - starts immediately |

---

## Completion Criteria

- [ ] `agentwire new -s test --restricted` creates a restricted session
- [ ] In restricted session, `say "hello"` works without prompts
- [ ] In restricted session, file edits/writes are auto-denied with message
- [ ] Dashboard shows "Restricted" badge for restricted sessions
- [ ] Create Session form has Restricted option
- [ ] CLAUDE.md documents the three session modes

---

## Technical Notes

### Allowed Commands in Restricted Mode

```python
import re

def _is_allowed_in_restricted_mode(tool_name: str, tool_input: dict) -> bool:
    """Check if command is allowed in restricted mode (say/remote-say only)."""
    if tool_name != "Bash":
        return False

    command = tool_input.get("command", "").strip()

    # Must start with say or remote-say
    if not command.startswith(("say ", "say\t", "remote-say ", "remote-say\t")):
        return False

    # Guard against shell chaining: reject if command contains operators
    # that could execute additional commands after say
    dangerous_patterns = [
        r'&&',      # AND operator
        r'\|\|',    # OR operator
        r';',       # command separator
        r'\|',      # pipe
        r'\$\(',    # command substitution
        r'`',       # backtick substitution
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            return False

    return True
```

**Design decisions:**
- Uses "allow_always" (keystroke "2") for auto-approved commands
- Silent deny for blocked commands (no TTS announcement)
- Rejects shell chaining attempts (&&, ||, ;, |, $(), backticks)

### Badge Colors

| Mode | Badge | Color |
|------|-------|-------|
| Bypass | `Bypass` | Green (primary) |
| Prompted | `Prompted` | Red (error) |
| Restricted | `Restricted` | Orange |
