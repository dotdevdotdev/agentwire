# Orchestrator-Worker Session Pairing

> **CANCELLED** - Superseded by `voice-orchestrator-workers.md` which implemented session types with --worker/--orchestrator flags.

> Living document. Update this, don't create new versions.

## Overview

**Mission scope**: Define orchestrator and worker roles for Claude Code using standard Claude Code 2.1.0 features (allowed-tools, hooks, agent field, roles).

This mission creates TWO Claude Code role definitions:

1. **Orchestrator**: Voice-first coordinator (Claude Code session)
   - Role file: Uses `--context` flag to load orchestrator instructions
   - Skills: Claude Code skills with `agent: orchestrator` frontmatter
   - Blocked from file operations via allowed-tools + PreToolUse hooks
   - Spawns workers via Task tool (Claude Code's subagent system)

2. **Worker**: Silent executor (spawned via Task tool)
   - Role file: Passed via Task prompt `@~/.agentwire/roles/worker.md`
   - Full Claude Code capabilities including Task tool for subagents
   - Follows ~/.claude/rules/ patterns (parallel execution, missions, etc.)
   - Blocked from user interaction via PreToolUse hooks

**Key insight**: This uses standard Claude Code features - Task tool, allowed-tools, hooks, agent field, @file references. No custom abstractions, just Claude Code conventions applied to orchestrator-worker pattern.

## Executive Summary

**What we're building**: Two role files for Claude Code (orchestrator, worker) using standard Claude Code patterns

**Not building**: Custom agent framework or abstractions

**Core pattern** (standard Claude Code):
1. User talks to orchestrator (Claude Code session with `--context ~/.agentwire/roles/orchestrator.md`)
2. Orchestrator spawns workers via Task tool (Claude Code's subagent system)
3. Workers get role via prompt: `@~/.agentwire/roles/worker.md`
4. Workers can spawn their own subagents via Task tool
5. Workers follow ~/.claude/rules/ patterns (existing conventions)
6. Workers return results via Task completion
7. Orchestrator speaks results to user via voice

**Claude Code features used**:
- Task tool for spawning subagents (orchestrator → worker, worker → subagents)
- allowed-tools in skill frontmatter (restrict orchestrator tools)
- PreToolUse hooks (enforce orchestrator file blocks, worker voice blocks)
- agent field in skills (orchestrator-specific skills)
- @file references (pass role files to subagents)
- --context flag (load role file on session start)

**Why this matters**:
- Uses Claude Code exactly as designed (no custom abstractions)
- Orchestrators stay conversational (voice-first)
- Workers leverage full Claude Code capabilities (Task, missions, parallel execution)
- Separation enforced via built-in Claude Code 2.1.0 features
- Scales naturally via Claude Code's Task tool patterns

## Current Problems

1. **Mixed responsibilities**: Single session tries to converse + code + explain changes
2. **Unnatural voice**: Session describes code diffs instead of talking ABOUT the work
3. **Worktree complexity**: Every session needs worktree setup explained, catastrophic when wrong
4. **Mechanical interaction**: Feels like task completion reports, not collaboration
5. **Cluttered conversation**: Code changes pollute the discussion thread

## Proposed Solution

### Core Pattern: Agent-Based Orchestration

**Orchestrator spawns workers as Task tool agents:**

```
Orchestrator Agent (myproject session)
  │
  ├─ Spawns via Task tool ─> Worker Agent 1 (frontend work)
  │                          - Full Claude Code capabilities
  │                          - Can spawn subagents for parallel work
  │                          - Follows mission/parallel patterns from ~/.claude/rules/
  │
  ├─ Spawns via Task tool ─> Worker Agent 2 (backend work)
  │                          - Independent execution context
  │                          - Reports facts to orchestrator
  │
  └─ User interaction via voice (remote-say)
     - Talks ABOUT the work
     - Never touches files directly
```

**Worker agents inherit best practices:**
- Workers use Task tool for their own subagents (for parallel file operations)
- Workers follow ~/.claude/rules/parallel-execution.md patterns
- Workers follow ~/.claude/rules/missions.md for complex multi-step work
- Workers are full-capability Claude Code agents, not restricted executors

**Infrastructure (tmux sessions):**
```
~/projects/myproject/
  ├── orchestrator session (myproject)
  │   - Runs orchestrator agent
  │   - Voice-enabled, conversational
  │   - Spawns worker agents via Task tool
  │
  └── worker session (myproject-worker) [OPTIONAL]
      - Available for direct CLI interaction if needed
      - Orchestrator typically spawns ephemeral Task agents instead
      - Persistent session useful for long-running background work
```

### Communication Flow

**User → Orchestrator:**
- Natural conversation via voice (Hammerspoon → orchestrator session)
- Voice input/output using remote-say
- Planning and coordination

**Orchestrator → Worker:**
- Spawns worker agents via Task tool with specific prompts
- Example: `Task(subagent_type="general-purpose", prompt="Implement auth endpoints. Follow worker role instructions at @~/.agentwire/roles/worker.md")`
- Worker agent has full context from prompt + role file
- No back-and-forth during execution (worker is autonomous)

**Worker → Orchestrator:**
- Returns result via Task tool completion
- Status in task result: completion, errors, blockers
- Facts only, no explanations
- Orchestrator interprets and speaks result to user

### Agent Types

**Orchestrator Agent:**
- **Voice-first**: Uses `remote-say` for all user communication
- **Planning**: Breaks down user requests into worker tasks
- **Spawns workers**: Uses Task tool to spawn worker agents
- **No file access**: Blocked from Edit, Write, Read via allowed-tools + hooks
- **Only uses**: Task tool, Bash(agentwire *), Bash(remote-say *), AskUserQuestion
- **Conversational**: "I'm having a worker implement that", "The worker found 3 errors"
- **Example Task call**:
  ```python
  Task(
    subagent_type="general-purpose",
    description="Implement auth endpoints",
    prompt="Implement JWT auth endpoints. Follow @~/.agentwire/roles/worker.md. Be factual and concise in output."
  )
  ```

**Worker Agent:**
- **Silent**: No voice output, minimal explanatory text
- **Autonomous execution**: Full Claude Code capabilities
- **Can spawn subagents**: Uses Task tool for parallel file operations
- **Follows best practices**: Applies ~/.claude/rules/ patterns (parallel execution, missions)
- **Factual reporting**: "Done, 3 files changed", "Error: test failed at auth.py:42"
- **Full tool access**: Edit, Write, Bash, Read, Task, Glob, Grep, etc.
- **Blocked from**: AskUserQuestion (orchestrator handles user interaction)
- **Blocked from**: Voice commands (remote-say, say)

## Technical Architecture

### Session Creation

```bash
# Default: Create orchestrator session
agentwire new myproject
# Creates orchestrator tmux session in ~/projects/myproject/
# Starts: claude --context ~/.agentwire/roles/orchestrator.md
# Orchestrator spawns workers via Task tool (ephemeral subagents)

# With worktree
agentwire new myproject/feature --worktree
# Creates orchestrator in ~/projects/myproject-worktrees/feature/
# Same orchestrator role, spawns workers via Task tool

# What happens in orchestrator session:
# User: "Add authentication"
# Orchestrator: Task(
#   subagent_type="general-purpose",
#   description="Implement auth",
#   prompt="Implement JWT auth. Follow @~/.agentwire/roles/worker.md"
# )
# Worker (Task subagent) executes, returns result
# Orchestrator speaks result to user via remote-say
```

### Configuration Structure

**rooms.json** (simplified - only orchestrator sessions):
```json
{
  "myproject": {
    "voice": "bashbunni",
    "role": "orchestrator"
  },
  "api": {
    "voice": "bashbunni",
    "role": "orchestrator"
  }
}
```

**Note**: Workers are Task tool subagents (ephemeral), not persistent tmux sessions, so they don't need rooms.json entries. The orchestrator spawns them on-demand and they terminate when work completes.

### System Prompts

**Orchestrator role instructions (~/.agentwire/roles/orchestrator.md):**
```
You are an orchestrator agent coordinating work via worker agents.

CRITICAL RULES:
1. NEVER edit files yourself - always spawn worker agents via Task tool
2. Use voice (remote-say) for all user communication
3. Talk ABOUT the work, not technical details
4. Keep conversations natural and collaborative

## Spawning Worker Agents

Use the Task tool to spawn worker agents for execution work:

Task(
  subagent_type="general-purpose",
  description="Implement auth endpoints",
  prompt="Implement JWT authentication endpoints. Follow @~/.agentwire/roles/worker.md for output style. Report completion, errors, or blockers factually."
)

Worker agents:
- Are full Claude Code agents with all capabilities
- Can spawn their own subagents for parallel work
- Follow best practices from ~/.claude/rules/
- Return factual results when done

## Communication Style

Good (voice-first, conversational):
- "I'm spawning a worker to implement that"
- "The worker found 3 type errors and fixed them"
- "Let me have a worker run the tests"

Bad (technical, mechanical):
- "I'm going to edit auth.py line 42..."
- "Here's the code change: ..."
- Describing diffs and file contents

## Available Tools

- Task: Spawn worker agents
- Bash: ONLY agentwire commands (monitoring, etc.) and remote-say
- AskUserQuestion: Clarify requirements with user
- NO file operations: Edit, Write, Read are blocked

## Multi-Worker Coordination

For complex work, spawn multiple workers in parallel:

Task(..., prompt="Frontend: Implement login UI")
Task(..., prompt="Backend: Add /auth endpoints")
Task(..., prompt="Tests: Add auth integration tests")

Speak about progress: "I've got three workers going - frontend, backend, and tests"
```

**Worker role instructions (~/.agentwire/roles/worker.md):**
```
You are a worker agent executing tasks autonomously.

CRITICAL RULES:
1. Be concise - facts only, minimal explanatory text
2. Execute and report: "Done", "Error: X", "Blocked: Y"
3. NO voice output (remote-say, say) - orchestrator handles user communication
4. NO user interaction (AskUserQuestion) - orchestrator handles that
5. You are a full Claude Code agent - use ALL available tools

## Available Tools

You have FULL Claude Code capabilities:
- Edit, Write, Read: Modify files
- Bash: Run commands, tests, builds
- Task: Spawn subagents for parallel work
- Glob, Grep: Search and explore code
- All other tools EXCEPT AskUserQuestion and voice commands

## Best Practices - Follow ~/.claude/rules/

You inherit ALL best practices from ~/.claude/rules/:

**Parallel execution (parallel-execution.md):**
- Use Task tool to spawn subagents for independent file operations
- Example: Editing 3+ files? Spawn 3 agents in parallel
- Respect 8-10 agent limit for context efficiency

**Mission patterns (missions.md):**
- For multi-wave work, break into parallel agent tasks
- Use TodoWrite to track complex multi-step work

**Code quality (code-quality.md):**
- Delete unused code, no backwards compatibility (pre-launch)
- Clean, focused changes

**Architecture (architecture.md):**
- Consolidate repeated logic into utilities
- Follow existing patterns in the codebase

## Output Format

Be factual and concise:

Success:
"Done, 3 files changed. Tests passing."

Error:
"Error: ImportError at auth.py:42 - missing module 'jwt'"

Blocked:
"Blocked: need DATABASE_URL environment variable"

## Example: Using Subagents for Parallel Work

If implementing auth requires updating 5 files:

[Task: "Update auth middleware"]
[Task: "Update auth routes"]
[Task: "Update auth models"]
[Task: "Update auth tests"]
[Task: "Update auth docs"]

Then report: "Done, 5 files changed via parallel agents. All tests passing."
```

## Mission Deliverables

This mission delivers **Claude Code role definitions and skills**, not a custom framework.

### 1. Role Files (Claude Code --context)

**Orchestrator role** (`~/.agentwire/roles/orchestrator.md`):
- Loaded via `claude --context ~/.agentwire/roles/orchestrator.md`
- Instructions emphasize Task tool for spawning workers
- Voice-first conversational style
- Documents available tools (Task, Bash, AskUserQuestion only)

**Worker role** (`~/.agentwire/roles/worker.md`):
- Passed to subagents via `@~/.agentwire/roles/worker.md` in Task prompts
- Instructions emphasize autonomous execution
- Factual, minimal output style
- Documents full tool access including Task for subagents
- References ~/.claude/rules/ for best practices inheritance

### 2. Skills (Claude Code ~/.claude/skills/)

**Orchestrator skills** (`~/.claude/skills/agentwire/`):
- `/spawn` - Create orchestrator session with role loaded
- `/delegate` - Helper for Task tool spawning syntax
- `/sessions` - Show session information
- All use Claude Code 2.1.0 frontmatter:
  ```yaml
  agent: orchestrator
  allowed-tools:
    - Task
    - Bash(agentwire *)
    - Bash(remote-say *)
    - AskUserQuestion
  ```

### 3. Hooks (Claude Code ~/.claude/settings.json)

**PreToolUse hooks** registered in settings.json:
- Orchestrator: Block Edit, Write, Read, Glob, Grep attempts
- Worker: Block remote-say, say, AskUserQuestion attempts
- Standard Claude Code hook pattern (command + timeout)

### 4. CLI Commands (tmux session management)

**AgentWire CLI** creates/manages tmux sessions:
- `agentwire new myproject` - Creates tmux session, starts Claude with `--context`
- Sessions are standard Claude Code sessions, just started with role file

**Key insight**: Everything uses standard Claude Code features. AgentWire just starts sessions with the right flags and manages tmux infrastructure.

### Portal Integration

**Features needed:**

1. **Orchestrator indicator**: Show "Orchestrator" badge/icon for orchestrator sessions
2. **Voice-first UI**: Orchestrator sessions emphasize voice controls (push-to-talk prominent)

## Implementation Waves

### Wave 1: Role File Design (BLOCKING - Manual Setup)

**Human tasks before Wave 2 begins:**
- [ ] Design orchestrator role file structure and instructions
- [ ] Design worker role file structure and instructions
- [ ] Document Task tool usage patterns for orchestrator
- [ ] Document @file reference pattern for passing worker role to subagents
- [ ] Test manually: Create session with `claude --context`, spawn Task subagent

**Why blocking:** Agents need clear examples of role file content and Task tool patterns.

### Wave 2: Session Creation & Management

**Agents can work in parallel:**
- [ ] `agentwire new` command (orchestrator by default)
  - Creates tmux session
  - Starts: `claude --context ~/.agentwire/roles/orchestrator.md`
  - Sets rooms.json role to "orchestrator"
  - Handles directory creation (single dir or worktree)
  - File: `agentwire/__main__.py` cmd_new function

- [ ] `agentwire new --worktree` variant
  - Creates worktree directory
  - Creates orchestrator session in worktree
  - Proper git branch handling
  - Same `--context` loading
  - File: `agentwire/__main__.py` worktree logic

- [ ] Session role detection utilities
  - `get_role(session)` helper - reads from rooms.json
  - `is_orchestrator(session)` helper - checks if role == "orchestrator"
  - File: `agentwire/agents/tmux.py`

### Wave 3: Agent Role Definitions

**Agents can work in parallel:**
- [ ] Orchestrator role file (`~/.agentwire/roles/orchestrator.md`)
  - Voice-first, conversational instructions
  - Emphasize Task tool for spawning workers
  - Block file operations (Edit, Write, Read)
  - Show multi-worker coordination examples
  - Document available tools: Task, Bash(agentwire *), Bash(remote-say *), AskUserQuestion
  - File: `~/.agentwire/roles/orchestrator.md`

- [ ] Worker role file (`~/.agentwire/roles/worker.md`)
  - Autonomous execution instructions
  - Factual, minimal output style
  - Full tool access INCLUDING Task for subagents
  - Emphasize following ~/.claude/rules/ best practices
  - Document parallel execution patterns (spawn subagents for 3+ file edits)
  - Document mission patterns (use TodoWrite for complex work)
  - Block user interaction (AskUserQuestion) and voice (remote-say, say)
  - File: `~/.agentwire/roles/worker.md`

- [ ] Update Claude Code session creation to load role files
  - Read role from rooms.json
  - Pass role file via `--context ~/.agentwire/roles/{role}.md`
  - File: `agentwire/agents/tmux.py` session creation

### Wave 4: Portal UI Updates

**Agents can work in parallel:**
- [ ] Dashboard role indicators
  - Show "Orchestrator" badge for orchestrator sessions
  - Visual distinction (icon, color, etc.)
  - File: `agentwire/static/js/dashboard.js`, `agentwire/static/css/dashboard.css`

- [ ] Room page orchestrator mode
  - Voice controls prominent (push-to-talk, voice selector)
  - Emphasize conversational interaction
  - File: `agentwire/templates/room.html`, `agentwire/static/js/room.js`

### Wave 5: Claude Code Hooks (Enforcement)

**Agents can work in parallel:**
- [ ] Orchestrator PreToolUse hooks
  - Register in `~/.claude/settings.json`
  - Block Edit, Write, Read, Glob, Grep attempts
  - Return helpful message: "Orchestrator cannot modify files. Spawn worker via Task tool."
  - File: `~/.claude/hooks/orchestrator-blocks.sh` or inline in settings.json

- [ ] Worker PreToolUse hooks
  - Register in `~/.claude/settings.json` (or in role file)
  - Block remote-say, say, AskUserQuestion attempts
  - Return helpful message: "Workers cannot interact with user. Orchestrator handles that."
  - File: `~/.claude/hooks/worker-blocks.sh` or inline in settings.json

### Wave 6: Claude Code Skills (Orchestrator Helpers)

**Agents can work in parallel:**
- [ ] `/spawn` skill update
  - Create orchestrator session with role file
  - Use `agent: orchestrator` frontmatter
  - Use `allowed-tools` frontmatter to restrict tools
  - File: `~/.claude/skills/agentwire/spawn.md`

- [ ] `/delegate` skill (new)
  - Helper for Task tool syntax
  - Shows orchestrator how to spawn workers
  - Example template for common patterns
  - Use `agent: orchestrator` frontmatter
  - File: `~/.claude/skills/agentwire/delegate.md`

- [ ] `/sessions` skill update
  - Show orchestrator vs regular sessions
  - Display role badges
  - File: `~/.claude/skills/agentwire/sessions.md`

### Wave 7: Documentation & Examples

**Agents can work in parallel:**
- [ ] Update CLAUDE.md with paired session pattern
  - When to use paired vs single session
  - Orchestrator-worker communication examples
  - Worktree decision matrix
  - File: `CLAUDE.md`

- [ ] Add paired session examples to docs
  - Example conversations
  - Common patterns
  - Troubleshooting
  - File: `docs/USAGE.md` or similar

- [ ] CLI help text updates
  - `agentwire new --help` explains --paired
  - Examples in help output
  - File: `agentwire/__main__.py`

## Success Criteria

**Claude Code role definitions (core deliverable):**
- [ ] Orchestrator role file (`~/.agentwire/roles/orchestrator.md`) with Task tool examples
- [ ] Worker role file (`~/.agentwire/roles/worker.md`) with ~/.claude/rules/ references
- [ ] Orchestrator skills use Claude Code 2.1.0 frontmatter (agent, allowed-tools)
- [ ] PreToolUse hooks registered in `~/.claude/settings.json`
- [ ] Hooks block orchestrator file operations (Edit, Write, Read, Glob, Grep)
- [ ] Hooks block worker user interaction (AskUserQuestion, remote-say, say)
- [ ] Workers can spawn subagents via Task tool (verified with test)
- [ ] Workers follow ~/.claude/rules/ patterns (verified with examples)

**Conversational quality:**
- [ ] Orchestrator uses voice (remote-say) for all user communication
- [ ] Orchestrator talks ABOUT work, not code details
- [ ] Orchestrator spawns workers via Task tool, not tmux commands
- [ ] Worker output is factual and minimal (no explanations)

**Separation of concerns (enforced):**
- [ ] Orchestrator cannot edit files (blocked via allowed-tools + hooks)
- [ ] Orchestrator cannot use Read, Glob, Grep (no file exploration)
- [ ] Worker cannot use AskUserQuestion (blocked via hooks)
- [ ] Worker cannot use remote-say or say (blocked via hooks)
- [ ] Worker has full access to Task, Edit, Write, Bash, Read, Glob, Grep

**Worker capabilities (tested):**
- [ ] Worker can spawn subagents for parallel file edits
- [ ] Worker can use TodoWrite for complex multi-step work
- [ ] Worker follows parallel execution patterns (8-10 agent limit)
- [ ] Worker can execute missions with wave-based planning

**User experience:**
- [ ] Creating orchestrator session is one command (`agentwire new myproject`)
- [ ] Orchestrator session loads with role file automatically
- [ ] Portal shows orchestrator badge/indicator clearly
- [ ] Voice interaction feels natural, not mechanical

## Migration Path

**No backwards compatibility** - This is a pre-launch project in active development.

- Delete old orchestrator.md and worker.md files completely, replace with new versions
- Remove any paired session logic from CLI (we're replacing it with Task tool pattern)
- Remove rooms.json pairing fields (paired_workers, paired_orchestrator, etc.)
- Update all skills to new pattern, delete old versions
- No migration tools, no legacy flags, no deprecated code paths

If something changes, change it everywhere. Git has history if needed.

## Design Decisions

1. **Default mode: Orchestrator sessions**
   - `agentwire new myproject` creates orchestrator session
   - Starts with `claude --context ~/.agentwire/roles/orchestrator.md`
   - Workers are Task tool subagents (ephemeral), not persistent sessions

2. **Worker lifecycle: Ephemeral Task subagents**
   - Workers spawned via Task tool on-demand
   - Workers terminate when work completes (Task tool handles lifecycle)
   - No persistent worker sessions needed

3. **Model selection: Claude Code default**
   - Sessions use Claude Code's built-in model selection
   - No model configuration in portal or CLI
   - Trust Claude Code to choose appropriate model

4. **Multiple workers: Task tool handles it**
   - Orchestrator can spawn multiple Task subagents in parallel
   - Each subagent is independent (Claude Code manages lifecycle)
   - No special multi-worker tracking in AgentWire

5. **Worker output: Task tool returns it**
   - Worker results returned via Task tool completion
   - Orchestrator sees results in conversation
   - Standard Claude Code Task behavior, no special monitoring

## What We're Replacing

**Delete and replace completely:**
- `~/.agentwire/roles/orchestrator.md` - Old singleton orchestrator concept
- `~/.agentwire/roles/worker.md` - Old independent worker concept
- Any paired session logic in CLI (`paired_workers` fields in rooms.json)
- Skills with old pairing concepts

**Reuse existing infrastructure:**
- Worktree logic: `agentwire new --worktree` already works
- Voice layer: `remote-say` infrastructure working
- Session management: `agentwire/agents/tmux.py` tmux integration
- Portal: Room UI, voice controls, monitoring

**Key files to modify:**
- `agentwire/__main__.py` - Update `cmd_new` to use `--context` flag
- `~/.agentwire/roles/orchestrator.md` - NEW content (Task tool focus)
- `~/.agentwire/roles/worker.md` - NEW content (subagent focus)
- `~/.claude/skills/agentwire/*.md` - Update with agent field + allowed-tools
