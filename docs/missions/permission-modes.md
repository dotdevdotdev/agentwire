# Mission: Permission Modes

> Per-session permission control with portal-based permission prompts via Claude Code hooks.

**Branch:** `mission/permission-modes`

## Context

Currently all sessions run with `--dangerously-skip-permissions` (global config). Users have no control over permission levels, and we have a vestigial `chatbot_mode` flag that's just cosmetic.

This mission:
1. Replaces `chatbot_mode` with functional `bypass_permissions` flag
2. Per-session choice: bypass (fast) vs normal (prompted)
3. Uses Claude Code's `PermissionRequest` hook to surface prompts in portal
4. Groups sessions by permission mode in `/status`

## Research Findings

**Key Discovery:** Claude Code doesn't show permission prompts in terminal output. Instead, it uses a **hook system**:

- `PermissionRequest` hook intercepts permission checks before Claude acts
- Hook receives JSON with tool name, parameters, context
- Hook returns `{decision: "allow"}` or `{decision: "deny"}`
- This is the proper integration point (not terminal parsing)

**Permission Types:**
| Tool Type | Needs Permission |
|-----------|------------------|
| Read-only (File reads, LS, Grep) | No |
| Bash commands | Yes - remembered permanently per project |
| File modification (Edit/Write) | Yes - remembered until session end |

## Session Types

| Type | Flag | Agent Command | Behavior |
|------|------|---------------|----------|
| **Bypass Session** | `bypass_permissions: true` | `claude --dangerously-skip-permissions` | No prompts, full trust |
| **Normal Session** | `bypass_permissions: false` | `claude` | Permission prompts via hook → portal |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Normal Session (bypass_permissions: false)                      │
│                                                                  │
│  Claude Code (no --dangerously-skip-permissions)                │
│       │                                                          │
│       ▼                                                          │
│  PermissionRequest Hook fires                                    │
│       │                                                          │
│       ▼                                                          │
│  permission-hook.sh                                              │
│       │ POST /api/permission/{room}                              │
│       ▼                                                          │
│  AgentWire Server                                                │
│       │ WebSocket: {type: "permission_request", ...}             │
│       ▼                                                          │
│  Portal UI shows modal                                           │
│       │                                                          │
│       ▼                                                          │
│  User clicks [Allow] / [Deny]                                    │
│       │                                                          │
│       ▼                                                          │
│  API returns decision to waiting hook                            │
│       │                                                          │
│       ▼                                                          │
│  Hook returns JSON to Claude Code                                │
│       │                                                          │
│       ▼                                                          │
│  Claude proceeds or aborts                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Hook Implementation

### Hook Script (`~/.claude/hooks/agentwire-permission.sh`)

```bash
#!/bin/bash
# Reads permission request from stdin, POSTs to AgentWire, returns decision

input=$(cat)
session_id=$(echo "$input" | jq -r '.session_id')
tool_name=$(echo "$input" | jq -r '.tool_name // "unknown"')

# Determine room from session or environment
room="${AGENTWIRE_ROOM:-default}"

# POST to AgentWire and wait for decision
response=$(curl -s -X POST "https://localhost:8765/api/permission/${room}" \
  -H "Content-Type: application/json" \
  -d "$input" \
  --max-time 300)  # 5 min timeout for user decision

# Return decision to Claude Code
echo "$response"
```

### Hook Configuration (`~/.claude/settings.json` - user-level)

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/agentwire-permission.sh"
          }
        ]
      }
    ]
  }
}
```

**Note:** User-level config means one-time install works for all projects.

### Hook Input (from Claude Code)

```json
{
  "session_id": "abc123",
  "cwd": "/Users/dotdev/projects/anna",
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/src/auth/login.ts",
    "old_string": "...",
    "new_string": "..."
  },
  "permission_mode": "default",
  "hook_event_name": "PermissionRequest",
  "message": "Claude needs your permission to edit /src/auth/login.ts"
}
```

### Hook Output (decision)

```json
{
  "decision": "allow"
}
```

Or to deny:

```json
{
  "decision": "deny",
  "message": "User denied permission"
}
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default for new sessions | Bypass (pre-selected) | Matches current behavior, speed-first |
| Diff preview in modal | Yes, v1 | Essential for informed decisions |
| TTS announcement | Tool + file details | "Claude wants to edit login.ts" |
| AWAITING PERMISSION orb | Orange/Amber | Warning color, attention needed |
| Hook configuration | User-level (~/.claude) | One-time install, all projects |
| Remote session support | Yes, v1 | Uses existing tunnel to localhost:8765 |
| Change mode after creation | No (locked) | Recreate session to change mode |
| Timeout behavior | Never timeout | Wait indefinitely for user response |

## UX Flow

### Creating a Session

```
┌─────────────────────────────────────────┐
│  New Session                             │
│                                          │
│  Project: [anna____________]             │
│  Name:    [feature-auth____]             │
│                                          │
│  Session Type:                           │
│    ● Bypass Permissions (Recommended)    │
│      Fast, no prompts, full trust        │
│                                          │
│    ○ Normal Session                      │
│      Permission prompts in portal        │
│                                          │
│              [Create Session]            │
└─────────────────────────────────────────┘
```

### Permission Prompt Modal

```
┌─────────────────────────────────────────┐
│  🔐 Permission Request                   │
│                                          │
│  Claude wants to:                        │
│                                          │
│  Edit file                               │
│  /src/auth/login.ts                      │
│                                          │
│  ┌─────────────────────────────────────┐ │
│  │ - const token = getToken()         │ │
│  │ + const token = await getToken()   │ │
│  └─────────────────────────────────────┘ │
│                                          │
│      [Allow]              [Deny]         │
└─────────────────────────────────────────┘
```

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
| 1.2 | Update agent command formatting based on room setting | `agents/tmux.py` |
| 1.3 | Pass room name as env var to session (`AGENTWIRE_ROOM`) | `agents/tmux.py` |
| 1.4 | Add bypass toggle to session creation API | `server.py` |

## Wave 2: Hook Infrastructure

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Create permission hook script | `hooks/agentwire-permission.sh` |
| 2.2 | Add `/api/permission/{room}` endpoint (blocking, waits for decision) | `server.py` |
| 2.3 | Store pending permission requests per room | `server.py` |
| 2.4 | Add `/api/permission/{room}/respond` endpoint for UI decisions | `server.py` |

## Wave 3: Portal UI

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | WebSocket message type for permission requests | `server.py` |
| 3.2 | Permission modal component (tool name, file path) | `templates/room.html` |
| 3.3 | Diff preview for Edit tool (old/new text display) | `templates/room.html` |
| 3.4 | Allow/Deny buttons that POST to respond endpoint | `templates/room.html` |
| 3.5 | "AWAITING PERMISSION" orb state (orange/amber) | `templates/room.html` |
| 3.6 | TTS announcement: "Claude wants to [action] [target]" | `server.py` |

## Wave 4: Session Creation UI

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Add session type toggle to dashboard create form | `templates/dashboard.html` |
| 4.2 | Pass bypass_permissions to create API | `templates/dashboard.html` |
| 4.3 | Show session type badge on dashboard | `templates/dashboard.html` |

## Wave 5: Skills & Cleanup

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Update `/status` skill to group by permission mode | `skills/status.md` |
| 5.2 | Update `/sessions` skill output | `skills/sessions.md` |
| 5.3 | Remove `chatbot_mode` references | Multiple files |
| 5.4 | Hook installation via `agentwire skills install` | `__main__.py` |

## Wave 6: Polish & Docs

| Task | Description | Files |
|------|-------------|-------|
| 6.1 | Update CLAUDE.md documentation | `CLAUDE.md` |
| 6.2 | Migration: treat missing bypass_permissions as true | `server.py` |
| 6.3 | Test remote session permission flow via tunnel | Manual testing |

## Completion Criteria

- [ ] Can create bypass vs normal sessions from portal
- [ ] Normal sessions trigger PermissionRequest hook
- [ ] Hook POSTs to AgentWire API
- [ ] Permission modal appears in portal
- [ ] Allow/Deny sends decision back to hook
- [ ] Claude proceeds or aborts based on decision
- [ ] `/status` groups sessions by permission mode
- [ ] `chatbot_mode` removed from codebase
- [ ] Existing sessions default to bypass (no breaking change)
- [ ] Hook installed via `agentwire skills install`

## Edge Cases

1. **No timeout**: Requests wait indefinitely for user response (Claude Code handles gracefully)
2. **Multiple permission requests**: Queue them, show one at a time
3. **Session disconnect**: Cancel pending permission requests
4. **Remote sessions**: Hook POSTs to localhost:8765 which tunnels back to portal
5. **Hook not installed**: Normal sessions fail gracefully with helpful error
6. **Browser not open**: Requests queue until user opens room page

## Future Enhancements (Not in v1)

- "Allow Always" option (remembers for session)
- Permission history/audit log
- Per-room permission presets
- Bulk approve/deny
- Configurable timeout (currently waits forever)
