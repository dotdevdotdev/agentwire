# Failure Memory: Learn from What Didn't Work

> System remembers failed approaches and automatically enriches retry attempts with that context.

## Problem

Workers repeat the same mistakes. When a task fails and gets retried:

```
# Attempt 1
Worker: "I'll try using axios for the API call..."
Result: Fails (project uses fetch, axios not installed)

# Attempt 2 (new worker, same task)
Worker: "I'll try using axios for the API call..."
Result: Same failure

# Attempt 3
Worker: "Let me check what HTTP library... I'll try axios..."
Result: STILL the same failure
```

Each worker starts fresh with zero memory of what was already tried. The orchestrator knows what failed but must manually remember to include "don't use axios" in every retry instruction.

## Why This Matters

1. **Wasted turns** - Workers burn tokens rediscovering the same dead ends
2. **Orchestrator burden** - Must manually track and communicate failures
3. **Frustration** - Watching the same mistake happen 3+ times
4. **Token cost** - Paying for repeated failed attempts
5. **Time sink** - Each failed attempt takes minutes before failing

The system has the information. It just doesn't use it.

## Proposed Solution: Automatic Failure Memory

### 1. Capture Failures

When a worker reports failure or gets killed due to errors, capture:

```yaml
failure_record:
  task_id: "auth-endpoint-001"
  worker_pane: 2
  timestamp: "2024-01-15T10:30:00Z"
  task_summary: "Add JWT authentication to /api/login"

  # What was tried
  approaches_tried:
    - "Used axios library for HTTP requests"
    - "Created auth middleware in /src/middleware/"

  # Why it failed
  failure_reason: "axios not installed, project uses native fetch"
  error_output: |
    Cannot find module 'axios'

  # Files touched (for conflict detection)
  files_touched:
    - src/routes/auth.ts
    - src/middleware/jwt.ts
```

### 2. Enrich Retry Attempts

When retrying the same task (or similar task), inject failure context:

```
<previous_attempts>
## What's Already Been Tried

This task was attempted 1 time before.

### Attempt 1 (failed)
**Approach:** Used axios library for HTTP requests
**Why it failed:** axios not installed, project uses native fetch
**Lesson:** Use native fetch or existing HTTP utilities in this project
</previous_attempts>

Your task: Add JWT authentication to /api/login...
```

Workers see what was tried, why it failed, and what to do differently.

### 3. Similarity Matching

Failures apply beyond exact task matches. Similar tasks benefit too:

```python
# Task: "Add rate limiting to /api/users"
# Similar past failure: "Add JWT auth to /api/login"
#   → learned axios doesn't work

# System injects:
<related_learnings>
From similar tasks in this project:
- HTTP requests should use native fetch, not axios
</related_learnings>
```

Similarity based on:
- Same project
- Same file paths
- Same libraries/tools mentioned
- Same error types

### 4. Failure Categories

Track failure types for pattern detection:

| Category | Example | Learning |
|----------|---------|----------|
| `missing_dependency` | axios not found | Don't assume, check package.json first |
| `wrong_pattern` | Used class components | Project uses functional components |
| `path_mismatch` | src/auth/ doesn't exist | Auth code is in src/services/auth/ |
| `api_mismatch` | Used v1 API syntax | Project uses v2 API |
| `test_failure` | Tests fail after change | Specific test patterns needed |

Category-specific advice gets injected automatically.

### 5. Memory Scope

Failures are scoped appropriately:

```
Project-level (persists in .agentwire/failures/)
├── "This project uses fetch not axios"
├── "Tests must be in __tests__ directories"
└── "No default exports, use named exports"

Session-level (memory, clears on session end)
├── "File X is locked by another process"
└── "Build is currently broken"

Task-level (specific to retry chain)
├── "Approach A didn't work"
└── "Approach B hit permission error"
```

## Implementation

### Failure Storage

```
project/
├── .agentwire/
│   ├── failures/
│   │   ├── index.json       # Task → failure mapping
│   │   └── records/
│   │       ├── auth-001.yaml
│   │       └── api-002.yaml
```

```python
# index.json
{
  "task_hashes": {
    "a1b2c3": ["auth-001", "auth-001-retry1"],
    "d4e5f6": ["api-002"]
  },
  "learnings": [
    {
      "category": "missing_dependency",
      "pattern": "axios",
      "lesson": "Use native fetch, axios not installed",
      "confidence": 0.9
    }
  ]
}
```

### Failure Extraction

From worker summaries and output:

```python
def extract_failure(worker_summary: str, task_output: str) -> FailureRecord:
    """Extract structured failure info from worker output."""

    record = FailureRecord()

    # Parse the summary's "What Didn't Work" section
    record.approaches_tried = parse_approaches(worker_summary)

    # Extract error messages
    record.error_output = extract_errors(task_output)

    # Classify failure type
    record.category = classify_failure(record.error_output)

    # Generate lesson (could use LLM for complex cases)
    record.lesson = generate_lesson(record)

    return record
```

### Injection Logic

```python
def enrich_task(task: str, project_dir: str) -> str:
    """Add failure context to task description."""

    failures = load_failures(project_dir)

    # Find relevant failures
    task_hash = hash_task(task)
    exact_matches = failures.get_by_task(task_hash)
    similar = failures.find_similar(task, threshold=0.7)
    learnings = failures.get_learnings()

    context_parts = []

    if exact_matches:
        context_parts.append(format_previous_attempts(exact_matches))

    if similar:
        context_parts.append(format_related_learnings(similar))

    if learnings:
        context_parts.append(format_project_learnings(learnings))

    if not context_parts:
        return task

    return f"<failure_context>\n{chr(10).join(context_parts)}\n</failure_context>\n\n{task}"
```

### Automatic Capture

Hook into worker idle/exit:

```python
@on_worker_exit
def capture_failure_if_any(pane: int, summary: str, status: str):
    if status in ("BLOCKED", "ERROR"):
        record = extract_failure(summary, get_pane_output(pane))
        save_failure(record)

        # Surface to orchestrator
        alert_orchestrator(f"Failure recorded: {record.lesson}")
```

## CLI Commands

```bash
# View failures for current project
agentwire failures list
agentwire failures show auth-001

# Clear old failures
agentwire failures clear --older-than 7d

# View project learnings
agentwire failures learnings

# Manually add a learning
agentwire failures learn "always use pnpm, not npm"

# Export/import (for team sharing)
agentwire failures export > team-learnings.yaml
agentwire failures import team-learnings.yaml
```

## MCP Tools

```python
@mcp.tool()
def failures_list(project_dir: str | None = None) -> str:
    """List recent failures for a project.

    Returns failure records with task summaries and lessons learned.
    """

@mcp.tool()
def failures_add_learning(lesson: str, category: str | None = None) -> str:
    """Manually add a project learning.

    Use when you discover something that should be remembered
    for future tasks without going through a failure.
    """

@mcp.tool()
def failures_clear(task_id: str | None = None, older_than: str | None = None) -> str:
    """Clear failure records.

    Args:
        task_id: Clear specific task failures
        older_than: Clear failures older than duration (e.g., '7d', '1w')
    """
```

## Configuration

```yaml
# In ~/.agentwire/config.yaml
failure_memory:
  enabled: true

  # How long to keep failures
  retention:
    task_level: 24h      # Specific attempt history
    project_level: 30d   # Project learnings

  # What to capture
  capture:
    worker_errors: true
    blocked_workers: true
    timeout_workers: true

  # Injection behavior
  injection:
    max_attempts_shown: 3      # Don't overwhelm with history
    include_error_output: true  # Include actual error messages
    include_learnings: true     # Include project-level learnings

  # Similarity threshold for "related" failures
  similarity_threshold: 0.7
```

## Example: Full Cycle

```
# Task: "Add rate limiting to /api/users"

[Worker 1 spawns]
System injects: (nothing, first attempt)

Worker 1: "I'll use express-rate-limit..."
Result: Error - "Cannot find module 'express-rate-limit'"
Worker exits with ERROR status

[System captures failure]
- Approach: Used express-rate-limit
- Error: Module not found
- Lesson: Check package.json before assuming dependencies

[Worker 2 spawns for retry]
System injects:
  <previous_attempts>
  Attempt 1 failed: Tried express-rate-limit but it's not installed.
  Lesson: Check package.json before assuming dependencies exist.
  </previous_attempts>

Worker 2: "Let me check package.json first... I see the project
          uses a custom rate limiter in src/utils/rateLimit.ts.
          I'll use that."
Result: Success

[System updates learnings]
- Project has custom rate limiter at src/utils/rateLimit.ts
```

## Orchestrator Integration

Orchestrators can query failure memory:

```
[Orchestrator thinking]
"Before spawning a worker for this auth task, let me check
what's been tried..."

agentwire_failures_list()
→ "2 previous failures for auth-related tasks:
   - Attempt to use passport.js failed (not installed)
   - JWT secret was missing from env"

"I'll include this context in the worker's task..."
```

Or automatic injection makes this unnecessary - the worker gets it automatically.

## Learning Propagation

Learnings can be shared across projects with similar characteristics:

```yaml
# Team-shared learnings (~/.agentwire/team-learnings.yaml)
learnings:
  - pattern: "nextjs-app"
    lessons:
      - "Use next/navigation, not next/router (App Router)"
      - "Server components can't use useState"

  - pattern: "typescript"
    lessons:
      - "Prefer unknown over any for error catches"
```

When a project matches a pattern, relevant learnings are included.

## Potential Challenges

1. **Stale learnings**: Project evolves, old learnings become wrong.
   - Solution: Timestamp learnings, decay confidence over time, allow override

2. **Over-constraining**: Too many "don't do X" rules limit creativity.
   - Solution: Frame as "try Y instead" not just "don't X". Cap injected context.

3. **False lessons**: One failure doesn't mean the approach is always wrong.
   - Solution: Require 2+ failures for same approach before it becomes a learning

4. **Privacy in shared learnings**: Team learnings might expose sensitive patterns.
   - Solution: Only share sanitized, generic learnings. Specific paths/names stay local.

5. **Storage growth**: Many failures over time.
   - Solution: Automatic pruning, compress into learnings, delete raw records

## Success Criteria

1. Retry attempts don't repeat the same failure (measure: same-error-rate drops >80%)
2. Orchestrators spend less time writing "don't do X" instructions
3. Average retries per task decreases
4. Token waste on repeated failures drops measurably
5. Project learnings accumulate and improve over weeks

## Non-Goals

- **Root cause analysis** - We capture what failed, not deep debugging
- **Auto-fixing** - Memory informs, doesn't auto-correct
- **Cross-project learning** - Focus on per-project memory first
- **Blame tracking** - No "worker X always fails at Y" metrics
