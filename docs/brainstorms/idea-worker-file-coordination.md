# Idea: Worker File Coordination

> Prevent edit conflicts when multiple workers modify the same codebase

## Problem

When orchestrators spawn multiple workers for parallel execution, there's no coordination for file access:

1. **Worker 1** starts editing `src/auth/login.ts`
2. **Worker 2** gets a task that also requires editing `src/auth/login.ts`
3. **Worker 2** reads the pre-edit version
4. **Worker 1** writes their changes
5. **Worker 2** writes their changes → **Worker 1's work is lost**

This is especially problematic with GLM workers, which execute literally and don't check for concurrent modifications.

## Current Workarounds

- **Hope and pray** - Orchestrators try to give non-overlapping tasks
- **Serial execution** - Only run one worker at a time (defeats parallelism)
- **Git worktrees** - Each worker gets a separate branch (complex, merge conflicts later)
- **Manual coordination** - Orchestrator explicitly says "don't touch X"

None of these are satisfying. Worktrees just defer the conflict to merge time.

## Why This Matters

AgentWire's value proposition is parallel worker execution. If workers can't safely work in the same codebase, orchestrators must either:
- Micromanage file assignments (cognitive overhead)
- Serialize workers (lose parallelism)
- Accept occasional data loss (bad)

A coordination layer makes parallel workers actually reliable.

## Proposed Solution: File Intent Registry

Lightweight file-level coordination without full locking.

### 1. Intent Declaration

Before editing a file, workers declare intent:

```bash
agentwire file-intent --pane 1 --files src/auth/login.ts src/auth/middleware.ts
```

MCP equivalent:
```python
agentwire_file_intent(files=["src/auth/login.ts", "src/auth/middleware.ts"])
```

This registers that pane 1 intends to modify these files.

### 2. Conflict Detection

When a new worker spawns, orchestrator can check for conflicts:

```bash
agentwire file-conflicts --files src/auth/login.ts
# Output: [{"file": "src/auth/login.ts", "pane": 1, "since": "2024-01-15T10:30:00"}]
```

Or when assigning a task, the orchestrator asks:

```bash
agentwire file-check --task-files src/auth/login.ts src/utils.ts
# Output: {"conflict": true, "files": ["src/auth/login.ts"], "blocked_by": [1]}
```

### 3. Wait or Reassign

If conflicts exist, orchestrator can:

**Option A: Wait for completion**
```bash
agentwire wait-file --file src/auth/login.ts --timeout 300
# Blocks until pane 1 releases the file or times out
```

**Option B: Queue the task**
Store the task and send when files are available.

**Option C: Assign to the same worker**
Send follow-up work to the worker already touching that file.

### 4. Release on Completion

When a worker goes idle (writes summary, exits), their file intents are automatically released.

Manual release (if worker decides not to edit a file):
```bash
agentwire file-release --pane 1 --files src/auth/login.ts
```

## Implementation Details

### State Storage

Simple JSON file per session:

```
~/.agentwire/file-intents/{session}.json
```

```json
{
  "pane_1": {
    "files": ["src/auth/login.ts", "src/auth/middleware.ts"],
    "since": "2024-01-15T10:30:00"
  },
  "pane_2": {
    "files": ["src/api/routes.ts"],
    "since": "2024-01-15T10:31:00"
  }
}
```

Cleaned up when worker exits.

### CLI Commands

```bash
# Declare intent to modify files
agentwire file-intent [--pane N] --files file1 file2...

# Check for conflicts before assigning task
agentwire file-check --files file1 file2...

# List all current file intents in session
agentwire file-intents [--session name]

# Wait for file to become available
agentwire file-wait --file path [--timeout seconds]

# Release intent (rare - usually auto-released)
agentwire file-release [--pane N] --files file1...
```

### MCP Tools

```python
@mcp.tool()
def file_intent(files: list[str]) -> str:
    """Declare intent to modify files. Call before editing.
    
    Other workers will see these files as 'in use' and can avoid conflicts.
    Files are automatically released when your pane exits.
    """

@mcp.tool()
def file_check(files: list[str]) -> str:
    """Check if files are being modified by other workers.
    
    Returns conflict info: which files, which panes, since when.
    Use before spawning a worker to detect potential conflicts.
    """

@mcp.tool()
def file_intents() -> str:
    """List all file intents in current session.
    
    Shows which panes are modifying which files.
    """
```

### Integration with Worker Roles

Update `glm-worker` role to declare intent:

```markdown
## File Coordination

Before editing files, declare your intent:
1. Identify all files you plan to modify
2. Call `agentwire_file_intent(files=[...])` 
3. Proceed with edits
4. Intent auto-releases when you exit

This prevents conflicts with other workers.
```

## Scope Considerations

### What This IS

- **Intent tracking** - "I plan to edit this file"
- **Conflict detection** - "Is anyone else editing this?"
- **Advisory coordination** - Orchestrator decides what to do

### What This IS NOT

- **Hard locking** - Workers can still write if they want
- **Automatic merging** - No git merge logic
- **Mandatory enforcement** - Just information for smarter decisions

The goal is to give orchestrators the information they need to prevent conflicts, not to enforce a locking regime.

## Example Workflow

```
Orchestrator receives: "Add auth and logging to the API"

1. Orchestrator plans:
   - Worker 1: Add auth middleware (files: auth.ts, middleware.ts)
   - Worker 2: Add logging (files: logging.ts, middleware.ts)  
   
   Conflict detected: middleware.ts

2. Orchestrator options:
   a) Give both tasks to one worker (serialized)
   b) Worker 1 does auth first, Worker 2 waits for middleware.ts
   c) Worker 1 does auth, Worker 2 does logging without middleware changes,
      then Worker 1 adds logging to middleware

3. Orchestrator chooses (b):
   - Spawn Worker 1: "Add auth middleware" 
   - Worker 1 declares intent: [auth.ts, middleware.ts]
   - Spawn Worker 2: "Add logging to logging.ts only, DO NOT touch middleware"
   - Worker 2 declares intent: [logging.ts]
   - Worker 1 completes, releases files
   - Spawn Worker 3: "Add logging calls to middleware.ts"
```

## Edge Cases

### Worker Crashes

When a worker crashes (pane dies unexpectedly), we detect this via pane list and auto-release their intents.

### Stale Intents

If a worker declares intent but takes too long (timeout), orchestrator can:
- Force-release the intent
- Kill the worker
- Reassign the task

### Overlapping Globs

Worker declares `src/**/*.ts`. Another worker wants `src/auth/login.ts`. The glob includes the specific file → conflict.

Simple approach: Expand globs to specific files at declaration time.

## Alternatives Considered

### Full Git Worktrees

Each worker gets a branch:
```bash
agentwire spawn --branch feature-auth
```

**Pros:** Complete isolation
**Cons:** Merge conflicts at the end, complex orchestration, more disk space

### File Locking (Hard)

Actual flock on files, block other writes.

**Pros:** Guaranteed no conflicts
**Cons:** Workers can hang waiting, doesn't work across machines

### Optimistic Locking

Let workers write freely, detect conflicts at commit time.

**Pros:** Simple, no coordination overhead
**Cons:** Work gets lost, need redo

### This Proposal: Intent Registry

**Pros:** 
- Lightweight (just metadata)
- Advisory (orchestrator decides)
- Works with existing patterns
- No git complexity

**Cons:**
- Workers must cooperate (declare intent)
- Not foolproof (worker can ignore)

## Rollout Strategy

1. **Phase 1: CLI commands** - Add file-intent, file-check, file-intents commands
2. **Phase 2: MCP tools** - Expose as MCP tools for agents
3. **Phase 3: Role updates** - Add intent declaration to worker roles
4. **Phase 4: Leader guidance** - Update leader role to check conflicts before spawning

## Open Questions

- Should intent be required or optional? (Start optional, see if workers adopt)
- Should orchestrator auto-check conflicts before spawning? (Probably yes)
- How granular? File-level seems right, but what about line ranges?
- Should we integrate with git status to detect modified files automatically?

## Success Criteria

1. Orchestrators can query which files are being edited
2. Workers can declare file intent with one command/MCP call
3. No additional cognitive load for simple (no conflict) cases
4. Parallel workers complete without overwriting each other's changes
5. System gracefully handles worker crashes

## Dependencies

- Existing pane management (spawn, kill, list)
- Session state directory (`~/.agentwire/`)
- MCP server for tool exposure
