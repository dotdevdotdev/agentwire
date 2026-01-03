---
name: kill
description: Destroy a tmux session.
---

# /kill

Destroy a tmux session on local or remote machines.

## Usage

```
/kill <session>
```

## Arguments

- `session`: Session name. Use `@machine` suffix for remote sessions (e.g., `ml@devbox-1`).

## Behavior

1. Parse session name for `@machine` suffix
2. Check if session exists
3. **Send `/exit` to Claude Code first** (clean shutdown)
4. Wait for Claude to close (2-3 seconds)
5. Kill the tmux session if still exists
6. Confirm destruction

## Examples

```
You: /kill api
Claude: Session 'api' destroyed.

You: /kill ml@devbox-1
Claude: Session 'ml' on devbox-1 destroyed.

You: /kill nonexistent
Claude: Session 'nonexistent' does not exist.
```

## Implementation Notes

### Parsing Session Name

```bash
# Parse <name>@<machine> format
if [[ "$session" == *"@"* ]]; then
  name="${session%@*}"
  machine="${session#*@}"
else
  name="$session"
  machine=""
fi
```

### Check If Session Exists

```bash
# Local
tmux has-session -t <session> 2>/dev/null && echo "exists"

# Remote
ssh <host> "tmux has-session -t <session> 2>/dev/null" && echo "exists"
```

### Clean Shutdown (Important!)

**Always send `/exit` to Claude Code before killing tmux.** This ensures:
- Session state is saved properly
- No orphaned child processes
- Clean conversation history

```bash
# Local - clean shutdown
agentwire send-keys <session> '/exit' Enter
sleep 3  # Wait for Claude to close
tmux kill-session -t <session> 2>/dev/null  # Kill if still exists

# Remote - clean shutdown
ssh <host> "agentwire send-keys <session> '/exit' Enter"
sleep 3
ssh <host> "tmux kill-session -t <session> 2>/dev/null"
```

### Machine Registry

Look up host from `~/.agentwire/machines.json`:

```json
{
  "machines": [
    {"id": "devbox-1", "host": "devbox-1", "projects_dir": "/home/user/projects"}
  ]
}
```

## Safety Considerations

- Warn if trying to kill the orchestrator session (`agentwire`)
- Check session exists before attempting to kill

## Error Handling

| Scenario | Response |
|----------|----------|
| Session doesn't exist | "Session 'X' does not exist." |
| Remote machine offline | "Cannot reach machine 'X'." |
| Unknown machine ID | "Unknown machine: 'X'. Check ~/.agentwire/machines.json" |
