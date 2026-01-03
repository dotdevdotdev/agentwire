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

```bash
# Parse session argument
SESSION="$1"
shift
PROMPT="$*"

if [[ "$SESSION" == *"@"* ]]; then
  # Remote session: name@machine
  SESSION_NAME="${SESSION%@*}"
  MACHINE="${SESSION#*@}"

  # Use base64 + paste buffer to avoid escaping/typing issues
  PROMPT_B64=$(echo "$PROMPT" | base64)
  ssh "$MACHINE" "echo '$PROMPT_B64' | base64 -d | tmux load-buffer -"
  ssh "$MACHINE" "tmux paste-buffer -t '$SESSION_NAME'; sleep 0.1; tmux send-keys -t '$SESSION_NAME' Enter; sleep 0.1; tmux send-keys -t '$SESSION_NAME' Enter"
else
  # Local session: use paste buffer for reliable submission
  echo "$PROMPT" | tmux load-buffer -
  tmux paste-buffer -t "$SESSION"
  sleep 0.1
  tmux send-keys -t "$SESSION" Enter
  sleep 0.1
  tmux send-keys -t "$SESSION" Enter
fi
```

**Why paste-buffer?**
- `send-keys` types character-by-character, which can cause issues with long prompts
- `paste-buffer` pastes the entire text as a block, more reliable for multi-line input
- The separate `Enter` at the end submits the prompt

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
