# Mission: Permission Modes

> Per-session permission control with portal-based permission prompts.

**Branch:** `mission/permission-modes`

## Context

Currently all sessions run with `--dangerously-skip-permissions` (global config). Users have no control over permission levels, and we have a vestigial `chatbot_mode` flag that's just cosmetic.

This mission:
1. Replaces `chatbot_mode` with functional `bypass_permissions` flag
2. Per-session choice: bypass (fast) vs normal (prompted)
3. Surfaces Claude's permission prompts in portal UI
4. Groups sessions by permission mode in `/status`

## Session Types

| Type | Flag | Agent Command | Behavior |
|------|------|---------------|----------|
| **Bypass Session** | `bypass_permissions: true` | `claude --dangerously-skip-permissions` | No prompts, full trust |
| **Normal Session** | `bypass_permissions: false` | `claude` | Permission prompts in portal |

## UX Flow

### Creating a Session

```
Project: anna
Name: feature-auth

Session Type:
  ○ Bypass Permissions (fast, no prompts)
  ● Normal Session (permission prompts in portal)

[Create]
```

### Permission Prompt (Normal Sessions)

When Claude needs permission, it shows a prompt in terminal. We detect this and show modal:

```
┌─────────────────────────────────────────┐
│  Permission Request                      │
│                                          │
│  Claude wants to:                        │
│  Edit file: /src/auth/login.ts           │
│                                          │
│  [Allow Once]  [Allow Always]  [Deny]    │
└─────────────────────────────────────────┘
```

User response is sent back to session, building up `.claude/settings.json` permissions organically.

### Status Grouping

```
Bypass Sessions:
  anna (main) ● IDLE
  api (main) ● WORKING

Normal Sessions:
  untrusted-lib (main) ● IDLE
  new-project (main) ● AWAITING PERMISSION
```

## Room Config

```json
{
  "anna": {
    "voice": "bashbunni",
    "bypass_permissions": true
  },
  "untrusted-lib": {
    "voice": "bashbunni",
    "bypass_permissions": false
  }
}
```

Default: `bypass_permissions: true` (current behavior, no breaking change)

## Wave 1: Config & Agent Command

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Add `bypass_permissions` to RoomConfig dataclass | `server.py` |
| 1.2 | Update agent command formatting to use room setting | `agents/tmux.py` |
| 1.3 | Add bypass toggle to session creation API | `server.py` |
| 1.4 | Update room creation UI with session type choice | `templates/room.html` or dashboard |

## Wave 2: Permission Prompt Detection

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Research Claude Code permission prompt format | - |
| 2.2 | Create PERMISSION_PATTERN regex for detection | `server.py` |
| 2.3 | Parse permission details (action, path, etc.) | `server.py` |
| 2.4 | Add permission prompt to output polling | `server.py` |

## Wave 3: Portal UI

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Create permission modal component (like AskUserQuestion) | `templates/room.html` |
| 3.2 | WebSocket message for permission prompts | `server.py`, `templates/room.html` |
| 3.3 | Send permission response back to session | `server.py` |
| 3.4 | Handle Allow Once vs Allow Always vs Deny | `server.py` |

## Wave 4: Skills & Cleanup

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Update `/status` skill to group by permission mode | `skills/status.md` |
| 4.2 | Update `/sessions` skill output | `skills/sessions.md` |
| 4.3 | Remove `chatbot_mode` references | Multiple files |
| 4.4 | Update documentation | `CLAUDE.md`, `docs/` |

## Wave 5: Polish

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Add "AWAITING PERMISSION" state to orb | `templates/room.html` |
| 5.2 | TTS for permission prompts (optional) | `server.py` |
| 5.3 | Default bypass_permissions in config.yaml | `config.py` |
| 5.4 | Migration: treat missing bypass_permissions as true | `server.py` |

## Completion Criteria

- [ ] Can create bypass vs normal sessions from portal
- [ ] Normal sessions show permission prompts in portal
- [ ] Can approve/deny permissions from portal
- [ ] Permissions persist in Claude's `.claude/settings.json`
- [ ] `/status` groups sessions by permission mode
- [ ] `chatbot_mode` removed from codebase
- [ ] Existing sessions default to bypass (no breaking change)

## Research Needed

- [ ] Exact format of Claude Code permission prompts
- [ ] What keys to send for Allow/Allow Always/Deny
- [ ] Does Claude show different prompts for different permission types?

## Future Enhancements (Not in v1)

- Permission presets (e.g., "read-only", "no network", "no shell")
- Per-room MCP server configs
- Permission audit log
- Bulk permission management
