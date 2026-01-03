---
name: send
description: Send a prompt to a specific tmux session.
---

# /send

Send a prompt to a running Claude session in tmux.

## Usage

```
/send <session> <prompt>
```

## Arguments

| Argument | Description |
|----------|-------------|
| `session` | Session name. Local: `api`. Remote: `ml@devbox-1` |
| `prompt` | The prompt text to send to the session |

## Behavior

1. Parse session name for `@machine` suffix
2. If local (no `@`), use tmux send-keys directly
3. If remote (`name@machine`), SSH + tmux send-keys
4. Confirm prompt was sent

## Session Naming Convention

| Format | Example | Target |
|--------|---------|--------|
| `<name>` | `api` | Local tmux session "api" |
| `<name>@<machine>` | `ml@devbox-1` | Session "ml" on machine "devbox-1" |

## Examples

```bash
# Send to local session
/send api "Add rate limiting to the /users endpoint"

# Send to remote session
/send ml@devbox-1 "Train the model with the new dataset"

# Multi-line prompt (use quotes)
/send backend "Refactor the auth module to use JWT tokens instead of sessions"
```

## Implementation

Use the `agentwire send` CLI command:

```bash
# Local session
agentwire send <session> "<prompt>"

# Remote session (via SSH)
ssh <machine> "agentwire send <session> '<prompt>'"
```

**How it works:**
- `agentwire send` uses tmux paste-buffer internally for reliable multi-line input
- Automatically adds Enter to submit the prompt
- Handles long prompts and special characters properly

## Notes

- The prompt is sent as-is; ensure Claude is ready to receive input
- Use `/status` to verify the session exists before sending
- Base64 encoding on remote prevents shell escaping issues

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `session not found` | Session doesn't exist | Check session name with `/status` |
| `ssh: connect refused` | Machine unreachable | Verify machine is online |
| `no server running` | tmux not running | Start tmux on target machine |
