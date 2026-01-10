---
name: check-workers
description: Check output from all active worker sessions.
---
# /check-workers

Batch check output from all worker sessions spawned by the current orchestrator.

## Usage

```
/check-workers [lines]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `lines` | No | Number of lines to read from each worker (default: 20) |

## Behavior

1. **List workers** - Find all sessions with `type: worker` spawned by current orchestrator
2. **Read output** - Run `agentwire output -s {worker} -n {lines}` for each
3. **Summarize status** - Parse output to determine: running, done, blocked, or error
4. **Report conversationally** - Provide voice-friendly summary

## Output Format

For each worker, determine status from output:
- **Running** - Still processing (ongoing tool calls, thinking indicators)
- **Done** - Completed successfully ("Done.", "Completed", tests passing)
- **Blocked** - Waiting on something ("Blocked:", "Need:", missing dependency)
- **Error** - Failed ("Error:", build/test failures)

Example response:
```
3 workers checked:

auth-refactor: Done - 5 files changed, tests passing
frontend-tests: Running - currently writing test cases
database-schema: Blocked - needs DATABASE_URL env var
```

## Implementation

```bash
# Get workers spawned by this orchestrator
ORCHESTRATOR=$(tmux display-message -p '#S')
WORKERS=$(agentwire list --json | jq -r ".local[] | select(.spawned_by == \"$ORCHESTRATOR\") | .name")

# Check each worker
for WORKER in $WORKERS; do
  echo "=== $WORKER ==="
  agentwire output -s "$WORKER" -n "${LINES:-20}"
  echo ""
done
```

## Status Detection Patterns

| Pattern | Status |
|---------|--------|
| `Done`, `Completed`, `Success` | Done |
| `Blocked:`, `Need:`, `Missing:` | Blocked |
| `Error:`, `Failed`, `FAILED` | Error |
| Ongoing tool output, thinking | Running |

## Related Skills

- `/workers` - List workers (name only, no output)
- `/spawn-worker` - Create new worker session
- `/output` - Read output from specific session
- `/send` - Send prompt to a session
