# Voice Orchestrator + Worker Sessions

> Living document. Update this, don't create new versions.

## Overview

**Mission scope**: Add session types to AgentWire that separate the voice/interaction layer from the execution layer.

**Core concept**: The orchestrator is the user's conversational interface. It spawns worker sessions to do actual file work, monitors their progress, and reports back conversationally. The user stays engaged with the orchestrator while workers execute in parallel.

```
User (voice/text)
    │
    ▼
Orchestrator Session (voice-enabled, no file access)
    │
    ├── agentwire new myproject/auth-work --worker
    │   └── Worker 1: Implementing auth endpoints
    │
    ├── agentwire new myproject/test-suite --worker
    │   └── Worker 2: Writing integration tests
    │
    └── agentwire send / agentwire output
        └── Orchestrator monitors, reports to user
```

**What already exists (leverage, don't rebuild)**:
- `agentwire new` with worktree support
- `agentwire send` for sending prompts to sessions
- `agentwire output` for reading session output
- `agentwire list` for session discovery
- rooms.json for per-session config
- Voice layer (say command with smart routing, push-to-talk)
- Permission modes (bypass, normal, restricted)

**What we're adding**:
- Session types: `orchestrator` vs `worker`
- Tool restrictions per type (Claude Code `--disallowedTools`)
- Role files loaded via `--append-system-prompt` flag
- Preset agent personas for common worker tasks
- Type-specific skills

## The User Experience

**Example interaction:**

```
User: "Let's execute mission auth-refactor now"

Orchestrator (voice): "Found the mission file. I'll spawn workers for
each wave. The first wave has 3 tasks - auth endpoints, middleware
updates, and test coverage. I'll get those going now."

[Spawns 3 worker sessions in worktrees]

Orchestrator (voice): "All three workers are running. This should take
about 5-10 minutes. Want to discuss anything while we wait?"

User: "Yeah, I've been thinking about adding OAuth support later"

Orchestrator (voice): "That's a good addition. Let me spawn a research
worker to look at OAuth patterns in similar projects so we can make
an informed decision."

[Spawns research worker]

[Meanwhile, auth workers complete]

Orchestrator (voice): "The auth workers just finished. All tests passing,
12 files changed across the three tasks. The research worker found some
OAuth patterns - want me to summarize?"
```

**Key characteristics:**
- Orchestrator talks ABOUT work, never describes code
- Orchestrator stays available for conversation while workers execute
- Workers are silent executors (no voice, no user questions)
- Orchestrator interprets worker output for natural reporting

## Session Types

### Orchestrator Sessions

**Purpose**: Voice-first interaction layer with user

**Created by**: `agentwire new myproject` (default, or explicit `--orchestrator`)

**Tool restrictions** (via Claude Code `--disallowedTools`):
- BLOCKED: `Edit`, `Write`, `Read`, `Glob`, `Grep`, `NotebookEdit`
- ALLOWED: `Task`, `Bash`, `AskUserQuestion`, `WebFetch`, `WebSearch`, `TodoWrite`

**Bash restrictions** (via PreToolUse hook):
- ALLOWED: `agentwire *`, `say *`, `git status`, `git log`, `git diff`
- BLOCKED: All other bash commands (no direct file manipulation)

**Behavior**:
- Uses voice (say) for all user communication
- Spawns workers via `agentwire new --worker`
- Monitors workers via `agentwire output`
- Sends instructions via `agentwire send`
- Plans and coordinates, never executes file changes

**Role file**: `~/.agentwire/roles/orchestrator.md`

### Worker Sessions

**Purpose**: Silent autonomous execution

**Created by**: `agentwire new myproject/task-name --worker`

**Tool restrictions** (via Claude Code `--disallowedTools`):
- BLOCKED: `AskUserQuestion`
- ALLOWED: Everything else (full Claude Code capabilities)

**Bash restrictions** (via PreToolUse hook):
- BLOCKED: `say *` (no voice output)
- ALLOWED: Everything else

**Behavior**:
- Full Claude Code capabilities for file operations
- Can spawn subagents via Task tool for parallel work
- Follows ~/.claude/rules/ patterns (parallel execution, missions)
- Outputs factual summaries: "Done, 3 files changed. Tests passing."
- Never interacts with user directly

**Role file**: `~/.agentwire/roles/worker.md`

## Configuration

### rooms.json Schema Update

```json
{
  "myproject": {
    "voice": "bashbunni",
    "type": "orchestrator",
    "bypass_permissions": true
  },
  "myproject/auth-work": {
    "type": "worker",
    "spawned_by": "myproject",
    "bypass_permissions": true
  }
}
```

**New fields:**
- `type`: `"orchestrator"` | `"worker"` (default: `"orchestrator"` for backwards compat)
- `spawned_by`: Parent orchestrator session (for worker sessions)

### CLI Changes

```bash
# Create orchestrator session (default)
agentwire new myproject
agentwire new myproject --orchestrator  # Explicit

# Create worker session
agentwire new myproject/auth-work --worker

# Worker inherits project from name prefix
# Creates worktree: ~/projects/myproject-worktrees/auth-work/
# Sets type: worker in rooms.json
# Starts Claude with --append-system-prompt and --disallowedTools
```

### Claude Code Startup

**Orchestrator sessions:**
```bash
claude --append-system-prompt "$(cat ~/.agentwire/roles/orchestrator.md)" \
       --disallowedTools Edit Write Read Glob Grep NotebookEdit
```

**Worker sessions:**
```bash
claude --append-system-prompt "$(cat ~/.agentwire/roles/worker.md)" \
       --disallowedTools AskUserQuestion
```

## Role Files

### Orchestrator Role (`~/.agentwire/roles/orchestrator.md`)

```markdown
# Orchestrator Role

You are the voice interface for a development session. You coordinate work
by spawning worker sessions, never by editing files directly.

## Your Capabilities

You can:
- Talk to the user via voice (say)
- Spawn worker sessions: `agentwire new project/task-name --worker`
- Send instructions to workers: `agentwire send -s project/task-name "prompt"`
- Check worker progress: `agentwire output -s project/task-name`
- List all sessions: `agentwire list`
- Plan and discuss with the user
- Research via web search
- Read mission files to understand work scope

You cannot:
- Edit, write, or read files directly (spawn a worker instead)
- Run arbitrary bash commands (only agentwire and voice commands)

## Communication Style

Voice-first, conversational:
- "I'll spawn a worker to handle that"
- "The auth worker just finished - 5 files updated, tests passing"
- "Let me check on the frontend worker... still running, about halfway done"

Never describe code or diffs. Talk ABOUT the work at a high level.

## Spawning Workers

For any file-changing task, spawn a worker:

```bash
agentwire new myproject/descriptive-task-name --worker
agentwire send -s myproject/descriptive-task-name "Your task: implement X.
Follow the patterns in the codebase. Report completion status when done."
```

For parallel work, spawn multiple workers:
```bash
agentwire new myproject/frontend-auth --worker
agentwire new myproject/backend-auth --worker
agentwire new myproject/auth-tests --worker
# Then send instructions to each
```

## Monitoring Workers

Check progress periodically:
```bash
agentwire output -s myproject/task-name
```

Report to user conversationally:
- "The worker is still going, looks like it's running tests now"
- "Done! 8 files changed, all tests passing"
- "Hit a blocker - needs a DATABASE_URL env var"

## Using Personas

When spawning workers, you can reference preset personas for common tasks:

```bash
agentwire send -s myproject/refactor "Apply @~/.agentwire/personas/refactorer.md
to consolidate the auth utilities."
```

Available personas are in ~/.agentwire/personas/
```

### Worker Role (`~/.agentwire/roles/worker.md`)

```markdown
# Worker Role

You are a silent executor. Complete tasks autonomously and report results
factually. Never use voice or ask the user questions.

## Your Capabilities

Full Claude Code capabilities:
- Edit, Write, Read files
- Run bash commands (tests, builds, etc.)
- Spawn subagents via Task tool for parallel work
- Search codebase with Glob, Grep
- Follow ~/.claude/rules/ patterns

You cannot:
- Use voice (remote-say, say) - orchestrator handles user communication
- Ask user questions (AskUserQuestion) - work autonomously

## Execution Style

Work autonomously. If you encounter a blocker:
- Try alternative approaches
- If truly stuck, output a clear blocker message for orchestrator to see

## Output Format

Be factual and concise. Your output is read by the orchestrator.

**Success:**
```
Done. 3 files changed:
- src/auth/login.ts (new)
- src/auth/middleware.ts (updated)
- tests/auth.test.ts (new)
Tests: 12 passing
```

**Error:**
```
Error: Build failed
- src/auth/login.ts:42 - Cannot find module 'jsonwebtoken'
- Missing dependency, needs: npm install jsonwebtoken
```

**Blocker:**
```
Blocked: Need DATABASE_URL environment variable
Cannot proceed without database connection for migration.
```

## Parallel Execution

For 3+ file changes, spawn subagents:

```
[Task: "Update auth middleware"]
[Task: "Update auth routes"]
[Task: "Update auth tests"]
```

Follow ~/.claude/rules/parallel-execution.md patterns.

## Best Practices

Follow ~/.claude/rules/:
- architecture.md: Consolidate repeated logic
- code-quality.md: No backwards compatibility (pre-launch)
- parallel-execution.md: Use subagents for parallel work
```

## Agent Personas

Preset prompting patterns for common worker tasks.

**Location**: `~/.agentwire/personas/`

### refactorer.md
```markdown
# Refactorer Persona

Focus: Consolidating and cleaning code without changing behavior.

Approach:
1. Identify repeated patterns (3+ occurrences)
2. Extract to shared utilities
3. Update all call sites
4. Verify tests still pass
5. Delete unused code completely

Output: List of consolidations made, files changed, test status.
```

### implementer.md
```markdown
# Implementer Persona

Focus: Building new features following existing patterns.

Approach:
1. Study similar existing features for patterns
2. Create minimal implementation first
3. Add tests alongside code
4. Follow project conventions exactly
5. No over-engineering

Output: Files created/modified, test coverage, any integration notes.
```

### debugger.md
```markdown
# Debugger Persona

Focus: Systematic bug investigation and fixing.

Approach:
1. Reproduce the issue first
2. Add logging/debugging to narrow down
3. Identify root cause before fixing
4. Fix minimally - don't refactor during debug
5. Add regression test

Output: Root cause, fix applied, regression test added.
```

### researcher.md
```markdown
# Researcher Persona

Focus: Gathering information for decision-making.

Approach:
1. Search codebase for relevant patterns
2. Check external docs/examples if needed
3. Summarize findings concisely
4. Present options with trade-offs
5. Don't make changes - just report

Output: Summary of findings, options identified, recommendation if clear.
```

## Implementation Waves

### Wave 1: Session Type Infrastructure (BLOCKING)

Human tasks:
- [x] Decide: Use `--disallowedTools` flag for tool blocking
- [x] Verified `--append-system-prompt` flag loads role files correctly
- [x] Verified `--disallowedTools` accepts space-separated tool names

### Wave 2: CLI & Configuration

Parallel tasks:
- [x] Add `--worker` flag to `agentwire new` command
  - Sets `type: worker` in rooms.json
  - Loads worker role via `--append-system-prompt`
  - Applies `--disallowedTools AskUserQuestion`
  - File: `agentwire/__main__.py` cmd_new

- [x] Add `--orchestrator` flag (explicit, optional)
  - Sets `type: orchestrator` in rooms.json
  - Loads orchestrator role via `--append-system-prompt`
  - Applies `--disallowedTools Edit Write Read Glob Grep NotebookEdit`
  - File: `agentwire/__main__.py` cmd_new

- [x] Update rooms.json schema
  - Add `type` field (orchestrator | worker)
  - Add `spawned_by` field for workers
  - Backwards compat: missing type = orchestrator
  - File: `agentwire/server.py` RoomConfig

### Wave 3: Role Files & Personas

Parallel tasks:
- [x] Create orchestrator role file
  - Voice-first instructions
  - agentwire command examples
  - Worker spawning patterns
  - File: `~/.agentwire/roles/orchestrator.md`

- [x] Create worker role file
  - Autonomous execution instructions
  - Factual output format
  - Parallel execution guidance
  - File: `~/.agentwire/roles/worker.md`

- [x] Create persona files
  - refactorer.md, implementer.md, debugger.md, researcher.md
  - Reusable prompting patterns
  - File: `~/.agentwire/personas/*.md`

### Wave 4: Tool Enforcement

Parallel tasks:
- [x] Orchestrator tool blocking
  - Block Edit, Write, Read, Glob, Grep via `--disallowedTools`
  - Block non-agentwire bash commands via PreToolUse hook
  - File: `agentwire/hooks/session-type-bash-hook.py`

- [x] Worker tool blocking
  - Block AskUserQuestion via `--disallowedTools`
  - Block say bash command via PreToolUse hook
  - File: `agentwire/hooks/session-type-bash-hook.py`

### Wave 5: Skills & Portal UI

Parallel tasks:
- [x] Orchestrator-specific skills
  - /workers - list active worker sessions
  - /spawn-worker - helper for worker creation
  - /check-workers - batch check all worker outputs
  - Files: `agentwire/skills/workers.md`, `spawn-worker.md`, `check-workers.md`

- [x] Portal session type indicators
  - Show "Orchestrator" or "Worker" badge on dashboard
  - Different styling for worker sessions (purple for worker, blue for orchestrator)
  - File: `agentwire/static/js/dashboard.js`, `agentwire/static/css/dashboard.css`

### Wave 6: Documentation

- [x] Update CLAUDE.md with session types
- [x] Add session types section with examples
- [x] Update CLI help text (--worker, --orchestrator flags documented)

## Success Criteria

**Session types work:**
- [x] `agentwire new myproject` creates orchestrator session
- [x] `agentwire new myproject/task --worker` creates worker session
- [x] rooms.json correctly stores session types
- [x] Role files load via `--append-system-prompt` flag

**Tool restrictions enforced:**
- [x] Orchestrator cannot Edit/Write/Read files
- [x] Orchestrator can only run agentwire/voice bash commands
- [x] Worker cannot use AskUserQuestion
- [x] Worker cannot use remote-say/say

**Workflow functions:**
- [x] Orchestrator spawns workers via `agentwire new --worker`
- [x] Orchestrator sends instructions via `agentwire send`
- [x] Orchestrator monitors via `agentwire output`
- [x] Workers complete tasks and output factual results
- [ ] Orchestrator reports results conversationally to user (to be tested)

**User experience:**
- [ ] Orchestrator feels conversational, not mechanical (to be tested)
- [ ] User can discuss other topics while workers execute (to be tested)
- [x] Worker output is clear and actionable

## What We're NOT Changing

Existing infrastructure to preserve:
- Worktree logic (workers get worktrees like any session)
- agentwire send/output/list commands
- Voice layer (remote-say infrastructure)
- Permission modes (bypass/normal/restricted)
- Template system
- Remote machine support
- Damage control hooks (additive, not replacing)

## Notes

**Why persistent sessions, not Task subagents:**
- Task subagents run within the orchestrator's context/token budget
- Persistent worker sessions have their own full context
- Workers can be long-running (mission execution)
- Orchestrator stays responsive while workers execute
- Workers can be monitored, killed, restarted independently

**Session naming convention:**
- Orchestrator: `myproject`
- Workers: `myproject/task-name` (automatically creates worktree)
- This leverages existing worktree infrastructure

## Testing Issues Found

Issues discovered during hands-on testing that need to be fixed:

### Issue 1: MCP Filesystem Tools Not Blocked

**Problem:** `--disallowedTools` only blocks Claude Code's built-in tools. MCP filesystem tools are separate and bypass the restriction.

**Observed behavior:** Orchestrator used `mcp__filesystem__create_directory`, `mcp__filesystem__read_file`, etc. to create directories and explore files.

**Expected behavior:** Orchestrator should not be able to do ANY file operations - should spawn a worker instead.

**Status: FIXED** - Added all MCP filesystem tools to `ORCHESTRATOR_DISALLOWED_TOOLS` list in `agentwire/__main__.py`:
- `mcp__filesystem__read_file`
- `mcp__filesystem__read_multiple_files`
- `mcp__filesystem__write_file`
- `mcp__filesystem__edit_file`
- `mcp__filesystem__create_directory`
- `mcp__filesystem__move_file`
- `mcp__filesystem__directory_tree`
- `mcp__filesystem__list_directory`
- `mcp__filesystem__list_directory_with_sizes`
- `mcp__filesystem__search_files`
- `mcp__filesystem__get_file_info`

### Issue 2: Session-Type Bash Hook Not Registered

**Problem:** The bash restriction hook (`session-type-bash-hook.py`) was created but never registered in `~/.claude/settings.json`.

**Observed behavior:** Orchestrator ran `git init && git add && git commit` directly - arbitrary bash commands that should be blocked.

**Expected behavior:** Orchestrator should only be able to run:
- `agentwire *` commands
- `say *` commands
- `git status`, `git log`, `git diff` (read-only git)

**Status: FIXED** - Implemented using Option A (env var approach):
1. `agentwire new --orchestrator` now sets `AGENTWIRE_SESSION_TYPE=orchestrator` env var
2. `agentwire new --worker` now sets `AGENTWIRE_SESSION_TYPE=worker` env var
3. Hook updated to read `AGENTWIRE_SESSION_TYPE` env var at runtime
4. Hook installed to `~/.agentwire/hooks/session-type-bash-hook.py`
5. Hook registered in `~/.claude/settings.json` via `agentwire skills install`

Sessions without the env var (backwards compat) have no restrictions.

### Issue 3: Damage Control Bypass via Individual Deletions

**Problem:** Claude found a workaround to delete files despite damage control hooks.

**Observed behavior:**
1. `rm -rf docs .git` → BLOCKED ✓
2. `rm docs/missions/file.md && rmdir docs/missions && rmdir docs` → SUCCEEDED (bypass!)
3. `rm .git/*` → BLOCKED ✓

**Result:** The `docs/` directory was successfully deleted by using individual `rm` (no flags) and `rmdir` commands.

**Root cause:** Damage control patterns only catch:
- `rm -rf` or `rm -r` (recursive flag)
- `rm -f` (force flag)
- Operations on protected paths like `.git/`

But they DON'T catch:
- `rm specific-file.md` (no flags)
- `rmdir directory` (directory removal)

**Note:** This is somewhat mitigated by the fact that the session-type bash hook (Issue 2) SHOULD have blocked ALL these commands for orchestrators anyway. Fixing Issue 2 would prevent this bypass.

**Status: FIXED** - Added patterns to `~/.agentwire/hooks/damage-control/patterns.yaml`:
- `\brmdir\b` - blocks all rmdir commands
- `\brm\s+[^-]` - blocks rm with file paths (not just rm -rf)

---

## Wave 7: Codebase Cleanup (Pre-Launch)

Remove legacy patterns, dead code, and backwards compatibility code. This is a pre-launch project with no customers.

### 7.1 Remove `remote-say` References

The `say` and `remote-say` commands were unified with smart routing. Remove all separate references.

**Files to update:**

| File | Changes |
|------|---------|
| `agentwire/server.py` | Change regex `say\|remote-say` to just `say` (line ~69) |
| `agentwire/__main__.py` | Remove `remote-say` from help text and legacy script detection |
| `agentwire/onboarding.py` | Remove `remote-say` verification steps |
| `agentwire/templates/dashboard.html` | Update help text |
| `agentwire/hooks/session-type-bash-hook.py` | Update pattern to just `say` |

**Pattern to remove:**
```python
# OLD (bad)
r'^(say|remote-say)\s+'

# NEW (good)
r'^say\s+'
```

### 7.2 Remove Backwards Compatibility Comments/Defaults

Remove all "backwards compat" comments and defensive defaults.

**Files to update:**

| File | Line | Change |
|------|------|--------|
| `agentwire/server.py` | ~84 | Remove "for backwards compat" comment |
| `agentwire/server.py` | ~86 | Remove "for backwards compat" from type default |
| `agentwire/agents/tmux.py` | ~160, 167 | Remove backwards compat comment |
| `agentwire/hooks/session-type-bash-hook.py` | ~117 | Remove backwards compat comment |
| `agentwire/static/css/base.css` | ~30 | Remove legacy CSS alias comment |
| `agentwire/static/js/room.js` | ~45, 546 | Remove legacy flag comment |

### 7.3 Delete Legacy `session` Commands

The `agentwire session new/list/output/kill` commands were replaced by `agentwire new/list/output/kill`. Delete the legacy versions.

**File:** `agentwire/__main__.py`
- Delete `cmd_session_new()` function
- Delete `cmd_session_list()` function
- Delete `cmd_session_output()` function
- Delete `cmd_session_kill()` function
- Remove `session` subcommand group from argparse

### 7.4 Remove Hardcoded `localhost:8100` Defaults

Update default URLs to use `None` and resolve via NetworkContext.

**Files to update:**

| File | Change |
|------|--------|
| `agentwire/config.py` | Change `url: str = "http://localhost:8100"` to `url: Optional[str] = None` |
| `agentwire/validation.py` | Update validation example |

### 7.5 Clean Up Unused Code

- Remove TODO stub in `agentwire/listen.py` line 249 (incomplete OpenAI implementation)
- Remove any commented-out code blocks
- Remove unused imports

### Wave 7 Acceptance Criteria

- [ ] No references to `remote-say` as separate from `say`
- [ ] No "backwards compat" comments in codebase
- [ ] No legacy `session` command functions
- [ ] No hardcoded `localhost:8100` defaults
- [ ] Clean, minimal codebase ready for launch
