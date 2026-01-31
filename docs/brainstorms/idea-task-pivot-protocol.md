# Idea: Task Pivot Protocol

> Gracefully stop workers mid-task and redirect them to new work without losing progress

## Problem

Workers sometimes need to be stopped mid-task:

- **Priority shift**: Urgent bug comes in, current work can wait
- **Wrong direction**: Orchestrator realizes the approach is wrong
- **Dependencies discovered**: Worker A needs something Worker B hasn't finished
- **User changed mind**: "Actually, let's do it differently"

Currently, the options are bad:

```bash
# Option 1: Kill the worker (loses all progress)
agentwire kill --pane 1

# Option 2: Wait for completion (wastes time on wrong work)
# ... sit and watch worker do the wrong thing ...

# Option 3: Send interrupt message (unreliable)
agentwire send --pane 1 "STOP! Change of plans..."
# Worker may not see it, may ignore it, may be mid-tool-call
```

There's no way to:
1. Signal "stop what you're doing"
2. Capture what they've accomplished so far
3. Redirect to new work with context preservation

## Why This Matters

1. **Wasted work** - Workers complete tasks that are no longer needed
2. **Lost progress** - Killing workers loses partial implementations
3. **Slow pivots** - Must wait for workers to finish before redirecting
4. **No graceful degradation** - All-or-nothing completion model

Real scenario: Worker is implementing feature A, but the orchestrator realizes feature B is blocking. Currently must wait for A to finish or kill and restart from scratch.

## Proposed Solution: Pivot Protocol

### 1. Pivot Signal

A standardized way to request a worker pivot:

```bash
# CLI
agentwire pivot --pane 1 --reason "Higher priority task" --new-task "Fix auth bug first"

# MCP
agentwire_pane_pivot(pane=1, reason="Higher priority task", new_task="Fix auth bug first")
```

### 2. Worker Pivot Handler

Workers (via role instructions) recognize pivot signals:

```markdown
## Pivot Protocol

When you receive a **[PIVOT REQUEST]** message:

1. **Stop current work** - Complete current tool call, then pause
2. **Write checkpoint** - Save progress to `.agentwire/checkpoint-{pane}.md`:
   - What you were doing
   - What's completed (files changed, tests passing)
   - What's remaining
   - Any blockers discovered
3. **Acknowledge** - Reply with "Checkpoint saved, ready for new task"
4. **Accept new task** - Read the new task from the pivot message

Do NOT:
- Ignore pivot requests
- Rush to finish current work
- Lose uncommitted changes
```

### 3. Checkpoint Format

```markdown
# Worker Checkpoint

## Original Task
Add rate limiting to /api/users endpoint

## Status: PARTIAL

## Completed
- [x] Created `src/middleware/rateLimit.ts`
- [x] Added Redis client connection
- [x] Basic rate limiter implementation

## In Progress
- [ ] Integration with routes (50% done - /users has it, /posts doesn't)

## Remaining
- [ ] Tests for rate limiting
- [ ] Documentation update

## Files Changed (uncommitted)
- `src/middleware/rateLimit.ts` (new)
- `src/routes/users.ts` (modified)

## Notes
- Discovered: Redis connection pool may need tuning for high load
- Left TODO comment at line 47 of rateLimit.ts

## Resumption Instructions
To continue this work:
1. Read the files listed above
2. Complete route integration in src/routes/posts.ts
3. Run `npm test -- --grep "rate limit"` for tests
```

### 4. Pivot Flow

```
Orchestrator                           Worker
    |                                    |
    |  [PIVOT REQUEST]                   |
    |  reason: "Auth bug is blocking"    |
    |  new_task: "Fix login endpoint"    |
    +----------------------------------->|
    |                                    | (completes current tool call)
    |                                    | (writes checkpoint)
    |  [PIVOT ACKNOWLEDGED]              |
    |  checkpoint: checkpoint-1.md       |
    |<-----------------------------------+
    |                                    |
    |                                    | (begins new task)
    |                                    |
```

### 5. Checkpoint Retrieval

Orchestrators can retrieve checkpoints:

```bash
# Get checkpoint for pane
agentwire checkpoint --pane 1

# List all checkpoints
agentwire checkpoint list

# Resume from checkpoint (spawn new worker with context)
agentwire spawn --roles glm-worker --from-checkpoint checkpoint-1.md
```

### 6. Pivot Modes

Different urgency levels:

| Mode | Behavior |
|------|----------|
| `graceful` (default) | Complete current tool, write checkpoint, then pivot |
| `immediate` | Write checkpoint now, abandon current tool call |
| `hard` | Kill immediately (no checkpoint, same as today) |

```bash
agentwire pivot --pane 1 --mode immediate --new-task "Critical bug fix"
```

## Implementation

### CLI Command

```python
@cli.command()
@click.option("--pane", "-p", type=int, required=True)
@click.option("--reason", "-r", help="Why pivoting")
@click.option("--new-task", "-t", help="New task to work on")
@click.option("--mode", type=click.Choice(["graceful", "immediate", "hard"]), default="graceful")
def pivot(pane: int, reason: str, new_task: str, mode: str):
    """Request a worker to pivot to a new task."""

    if mode == "hard":
        # Just kill
        kill_pane(pane)
        return

    # Send pivot signal
    pivot_message = f"""[PIVOT REQUEST]
Mode: {mode}
Reason: {reason or "Priority change"}

Write your checkpoint to .agentwire/checkpoint-{pane}.md, then acknowledge.

New task:
{new_task}
"""
    send_to_pane(pane, pivot_message)

    # Wait for acknowledgment (with timeout)
    if wait_for_checkpoint(pane, timeout=60):
        echo(f"Worker pivoted. Checkpoint: .agentwire/checkpoint-{pane}.md")
    else:
        echo("Worker did not acknowledge pivot. Consider --mode hard")
```

### MCP Tool

```python
@mcp.tool()
def pane_pivot(
    pane: int,
    reason: str | None = None,
    new_task: str | None = None,
    mode: str = "graceful"
) -> str:
    """Request a worker to pivot to a new task.

    Args:
        pane: Worker pane index
        reason: Why the pivot is needed
        new_task: The new task to work on (optional - can send separately)
        mode: graceful (default), immediate, or hard

    Returns:
        Checkpoint path if successful, error if worker didn't acknowledge.
    """
```

### Worker Role Addition

Add to `glm-worker` and `claude-worker` roles:

```markdown
## Pivot Protocol

You may receive pivot requests from the orchestrator. These have the format:

[PIVOT REQUEST]
Mode: graceful|immediate
Reason: <why pivoting>

When you see this:

1. If mode is "immediate": stop NOW, write checkpoint
2. If mode is "graceful": finish current tool call, then write checkpoint

Checkpoint file: `.agentwire/checkpoint-{your_pane_number}.md`

After writing checkpoint, respond with:
"[PIVOT ACKNOWLEDGED] Checkpoint saved to .agentwire/checkpoint-{pane}.md"

Then immediately start the new task if one was provided.
```

### Checkpoint Storage

```
project/
└── .agentwire/
    ├── checkpoint-1.md      # Pane 1's checkpoint
    ├── checkpoint-2.md      # Pane 2's checkpoint
    └── worker-1.md          # Normal completion summary
```

Checkpoints differ from completion summaries:
- **Checkpoint**: Partial progress, resumable
- **Summary**: Completed work, for orchestrator review

## Use Cases

### Priority Interrupt

```
Orchestrator: "Add dark mode to settings"
Worker: [starts implementing...]

Orchestrator: [discovers critical bug]
agentwire_pane_pivot(pane=1,
    reason="Critical auth bug discovered",
    new_task="Fix: login returns 500 when password contains special chars"
)

Worker: [checkpoints dark mode progress, pivots to auth fix]
```

### Approach Correction

```
Orchestrator: "Refactor the API to use GraphQL"
Worker: [starts massive refactor...]

Orchestrator: [realizes REST is fine, just needs cleanup]
agentwire_pane_pivot(pane=1,
    reason="Changed approach - GraphQL overkill",
    new_task="Just clean up the existing REST endpoints"
)
```

### Dependency Discovery

```
Worker A: [implementing feature that needs config changes]
Worker A: "I need FOO_API_KEY in env, but it's not there"

Orchestrator:
agentwire_pane_pivot(pane=1,  # Worker B
    reason="Worker A is blocked on config",
    new_task="Add FOO_API_KEY to .env.example and document it"
)
```

### Work Redistribution

```
# Worker 1 is slow, Worker 2 is idle
agentwire_pane_pivot(pane=1,
    reason="Redistributing work",
    new_task="Just finish the tests, I'm giving routes to another worker"
)
```

## Potential Challenges

1. **Worker compliance** - Workers must respect pivot signals; LLMs may try to "just finish this one thing"
   - Mitigation: Strong role instructions, mode=immediate for urgent cases

2. **Checkpoint quality** - Workers may write poor checkpoints
   - Mitigation: Checkpoint template, validation

3. **State consistency** - Worker may have uncommitted changes
   - Mitigation: Checkpoint includes git status, warns about uncommitted work

4. **Tool call interruption** - Can't interrupt mid-API-call
   - Mitigation: graceful mode waits for tool completion; immediate mode accepts lost work

5. **New task handoff** - New task may lack context from checkpoint
   - Mitigation: `--from-checkpoint` spawns with checkpoint context injected

## Success Criteria

1. Workers acknowledge pivot within 60 seconds
2. Checkpoints capture enough detail to resume work
3. No progress lost when using graceful mode
4. Orchestrators can redirect workers without killing
5. Works for both Claude Code and OpenCode workers

## Future Extensions

- **Auto-pivot on blockers**: Worker detects it's blocked, auto-pivots to notify orchestrator
- **Pivot chains**: Redirect multiple workers at once
- **Checkpoint diff**: Show what changed since last checkpoint
- **Resume queue**: Track pivoted tasks for later resumption
