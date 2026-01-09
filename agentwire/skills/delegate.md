---
name: delegate
description: Helper for spawning worker agents via Task tool with proper syntax and patterns.
agent: orchestrator
allowed-tools:
  - Task
  - Bash(agentwire *)
  - Bash(remote-say *)
  - AskUserQuestion
---

# /delegate

Helper for orchestrators to spawn worker agents via Task tool. Shows syntax, examples, and common patterns for delegating work to autonomous worker agents.

## Core Pattern

Orchestrators delegate work by spawning worker agents via the Task tool:

```python
Task(
  subagent_type="general-purpose",
  description="Brief task description",
  prompt="Detailed instructions. Follow @~/.agentwire/roles/worker.md for output style."
)
```

Worker agents:
- Are full Claude Code agents with all capabilities
- Can spawn their own subagents for parallel work
- Follow best practices from `~/.claude/rules/`
- Return factual results when done

## Task Tool Syntax

```python
Task(
  subagent_type="general-purpose",           # Standard subagent type
  description="Implement auth endpoints",    # Short task summary
  prompt="""
    Implement JWT authentication endpoints:
    - POST /auth/login (email + password → token)
    - POST /auth/logout (invalidate token)
    - GET /auth/verify (check token validity)

    Follow @~/.agentwire/roles/worker.md for output style.
    Report completion, errors, or blockers factually.
  """
)
```

## Common Patterns

### Single Feature Implementation

```python
Task(
  subagent_type="general-purpose",
  description="Add rate limiting",
  prompt="Add rate limiting middleware (100 req/min per IP). Apply to /auth routes. Follow @~/.agentwire/roles/worker.md"
)
```

### Multiple Workers in Parallel

For complex work, spawn multiple workers simultaneously:

```python
# Frontend work
Task(
  subagent_type="general-purpose",
  description="Frontend: Login UI",
  prompt="Implement login form UI with validation. Follow @~/.agentwire/roles/worker.md"
)

# Backend work
Task(
  subagent_type="general-purpose",
  description="Backend: Auth endpoints",
  prompt="Add /auth/login and /auth/logout endpoints. Follow @~/.agentwire/roles/worker.md"
)

# Testing
Task(
  subagent_type="general-purpose",
  description="Tests: Auth integration tests",
  prompt="Add integration tests for auth flow. Follow @~/.agentwire/roles/worker.md"
)
```

Then speak to user: "I've got three workers going - frontend, backend, and tests"

### Bug Investigation

```python
Task(
  subagent_type="general-purpose",
  description="Investigate auth test failures",
  prompt="Tests failing at test_auth.py:15. Investigate and fix. Follow @~/.agentwire/roles/worker.md"
)
```

### Refactoring

```python
Task(
  subagent_type="general-purpose",
  description="Extract auth utilities",
  prompt="Consolidate repeated JWT logic into src/lib/auth.ts. Update all usages. Follow @~/.agentwire/roles/worker.md"
)
```

## Worker Capabilities

Workers are **full Claude Code agents** with access to:

| Tool | Purpose |
|------|---------|
| Edit, Write | Modify files |
| Read | Read file contents |
| Bash | Run commands, tests, builds |
| Task | Spawn subagents for parallel work |
| Glob, Grep | Search and explore code |
| TodoWrite | Track complex multi-step work |

**Blocked from:**
- AskUserQuestion (orchestrator handles user interaction)
- remote-say, say (orchestrator handles voice)

## Worker Output Style

Workers follow `~/.agentwire/roles/worker.md` for factual, minimal output:

✅ "Done, 3 files changed. Tests passing."
✅ "Error: ImportError at auth.py:42 - missing module 'jwt'"
✅ "Blocked: need DATABASE_URL environment variable"

❌ NO explanations, NO conversation, NO technical details

## When to Delegate

Use Task tool for:
- File editing (workers can edit, you cannot)
- Code exploration (workers have Read, Glob, Grep)
- Running tests or builds
- Multi-file changes (worker spawns subagents for parallel work)
- Any execution work

Keep in orchestrator:
- User conversation (via remote-say)
- Planning and coordination
- Asking clarifying questions (AskUserQuestion)
- Monitoring workers (you spawn them, they report back)

## Communication Flow

```
User: "Add authentication"
  ↓
Orchestrator: [spawns worker via Task]
  ↓
Worker: [executes autonomously, spawns subagents as needed]
  ↓
Worker: "Done, auth implemented. Tests passing."
  ↓
Orchestrator: remote-say "Authentication is ready. Login and logout endpoints are live."
```

## Example Session Flow

**User request:**
"Add rate limiting to the API"

**Orchestrator action:**
```python
# Spawn worker
Task(
  subagent_type="general-purpose",
  description="Add rate limiting middleware",
  prompt="Add rate limiting (100 req/min per IP). Apply to all /api routes. Follow @~/.agentwire/roles/worker.md"
)

# Speak to user
remote-say "I'm having a worker add rate limiting to the API"
```

**Worker execution:**
- Creates middleware file
- Updates routes
- Adds tests
- Runs test suite

**Worker result:**
"Done. Rate limiting middleware added (100 req/min per IP). Applied to /api routes. Tests passing."

**Orchestrator response:**
```bash
remote-say "Rate limiting is in place. All API endpoints now limit to 100 requests per minute per IP address."
```

## Related Skills

- `/spawn` - Create orchestrator sessions
- `/sessions` - List sessions with role indicators
- `/output` - Read worker output (when using persistent worker sessions)

## Remember

You are the **orchestrator**. Workers are your execution engine via Task tool:
1. User talks to you
2. You spawn workers for execution
3. Workers report facts
4. You interpret and speak results to user

Never edit files yourself - always delegate to workers via Task tool.
