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

## Implementation

Use the `agentwire kill` CLI command:

```bash
# Local session
agentwire kill -s <session>

# Remote session (via SSH)
ssh <host> "agentwire kill -s <session>"
```

**The CLI automatically:**
1. Sends `/exit` to Claude Code for clean shutdown
2. Waits for Claude to close (~3 seconds)
3. Kills the tmux session if still exists

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

- Warn if trying to kill the main agentwire session (`agentwire`)
- Check session exists before attempting to kill

## Error Handling

| Scenario | Response |
|----------|----------|
| Session doesn't exist | "Session 'X' does not exist." |
| Remote machine offline | "Cannot reach machine 'X'." |
| Unknown machine ID | "Unknown machine: 'X'. Check ~/.agentwire/machines.json" |
