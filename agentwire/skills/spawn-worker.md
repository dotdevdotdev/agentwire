---
name: spawn-worker
description: Spawn a new worker session for autonomous task execution.
---
# /spawn-worker

Create a new worker session to execute tasks autonomously.

## Usage

```
/spawn-worker <task-name> [prompt]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `task-name` | Yes | Name for the worker (becomes session name suffix) |
| `prompt` | No | Initial task prompt to send after creation |

## Behavior

1. **Derive session name** - `{current-project}/{task-name}`
2. **Create worker session** - `agentwire new {session-name} --worker`
3. **Send initial prompt** - If provided, `agentwire send -s {session-name} "{prompt}"`
4. **Report success** - Confirm worker is running

## Examples

### Quick spawn with inline task

```
/spawn-worker auth-refactor "Refactor auth utilities using @~/.agentwire/personas/refactorer.md"
```

### Spawn with detailed follow-up

```
/spawn-worker frontend-tests
```

Then send detailed instructions:
```
agentwire send -s myproject/frontend-tests "Write integration tests for the login flow..."
```

### Spawn multiple workers

```
/spawn-worker api-endpoints
/spawn-worker database-migrations
/spawn-worker test-coverage
```

## Implementation

```bash
# Detect current project from session name or working directory
CURRENT_PROJECT=$(basename "$PWD")

# Create worker session
agentwire new "$CURRENT_PROJECT/$TASK_NAME" --worker

# Optionally send initial prompt
if [ -n "$PROMPT" ]; then
  agentwire send -s "$CURRENT_PROJECT/$TASK_NAME" "$PROMPT"
fi

# Confirm
echo "Worker '$CURRENT_PROJECT/$TASK_NAME' spawned"
```

## Related Skills

- `/workers` - List active worker sessions
- `/check-workers` - Check output from all workers
- `/output` - Read output from a specific session
- `/send` - Send prompt to a session
- `/kill` - Terminate a session
