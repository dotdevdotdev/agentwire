# AgentWire Usage Guide

> Living document. Update this, don't create new versions.

This guide covers common usage patterns, workflows, and best practices for AgentWire.

---

## Orchestrator-Worker Pattern

The orchestrator-worker pattern is AgentWire's core workflow, leveraging Claude Code's Task tool for spawning subagents.

### Basic Workflow

1. **Create orchestrator session:**
   ```bash
   agentwire new -s myproject
   # Creates orchestrator in ~/projects/myproject/
   # Loads with --context ~/.agentwire/roles/orchestrator.md
   ```

2. **Interact via voice or text:**
   - Voice: Push-to-talk in browser → orchestrator responds via TTS
   - Text: Type in Monitor tab → orchestrator reads and responds

3. **Orchestrator spawns workers:**
   - Orchestrator uses Task tool to spawn worker agents
   - Workers execute code changes autonomously
   - Workers return factual results
   - Orchestrator speaks results to user

### Example: Feature Implementation

**User request (voice):**
> "Add a REST API endpoint for creating users"

**Orchestrator response (voice):**
> "I'm spawning a worker to implement that"

**Behind the scenes:**
```python
Task(
  subagent_type="general-purpose",
  description="Implement user creation endpoint",
  prompt="""
  Implement POST /users endpoint with the following:
  - Input validation
  - Database persistence
  - Error handling
  - Unit tests

  Follow @~/.agentwire/roles/worker.md for output style.
  """
)
```

**Worker execution:**
- Edits `routes/users.py` (adds endpoint)
- Edits `models/user.py` (validation)
- Edits `tests/test_users.py` (tests)
- Runs tests
- Returns: "Done, 3 files changed. Tests passing."

**Orchestrator reports (voice):**
> "The endpoint is ready. All tests passing."

---

## Common Patterns

### Pattern 1: Single Worker for Focused Tasks

**When to use:** Bug fixes, small features, isolated changes

**Example:**
```
User: "Fix the timeout bug in auth.py"
Orchestrator: "Looking into it"
  → Spawns 1 worker
  → Worker fixes bug, runs tests
  → Worker: "Fixed, tests passing"
Orchestrator: "Bug fixed"
```

### Pattern 2: Multiple Parallel Workers

**When to use:** Complex features requiring multiple independent changes

**Example:**
```
User: "Add authentication with login UI and backend"
Orchestrator: "I'll have workers handle frontend, backend, and tests"
  → Spawns 3 workers in parallel:
    - Worker 1: Frontend login form
    - Worker 2: Backend auth endpoints
    - Worker 3: Integration tests
  → All workers complete independently
  → Workers report results
Orchestrator: "Authentication complete. Frontend, backend, and tests all done."
```

### Pattern 3: Worker with Subagents

**When to use:** Worker needs to modify 3+ files in parallel

**Example:**
```
Orchestrator spawns worker: "Refactor auth module"
Worker analyzes work:
  - Need to update 5 files
  - Spawns 5 subagents in parallel (Claude Code pattern):
    Task(..., prompt="Update auth/login.py")
    Task(..., prompt="Update auth/logout.py")
    Task(..., prompt="Update auth/session.py")
    Task(..., prompt="Update auth/middleware.py")
    Task(..., prompt="Update auth/tests.py")
  - Subagents complete
Worker reports: "Done, 5 files changed. Tests passing."
Orchestrator: "Refactor complete"
```

### Pattern 4: Mission Execution

**When to use:** Multi-wave work with dependencies

**Example:**
```
User: "Execute the auth-refactor mission"
Orchestrator:
  - Reads docs/missions/auth-refactor.md
  - Spawns workers for all waves in parallel:
    - Wave 2: Database schema updates
    - Wave 3: API changes
    - Wave 4: Frontend integration
  - Workers follow mission instructions
  - Workers use TodoWrite for complex sub-tasks
  - Workers report completion
Orchestrator: "Mission complete. All waves done."
```

---

## Worktree Workflows

### Creating Worktree Sessions

```bash
# Project with worktree (creates feature branch)
agentwire new -s myproject/feature

# Creates:
# - ~/projects/myproject-worktrees/feature/
# - Git branch: feature
# - Orchestrator session: myproject/feature
```

### Recreating (Fresh Start)

```bash
# Destroy and recreate with latest code
agentwire recreate -s myproject/feature

# Steps:
# 1. Kills session
# 2. Removes worktree
# 3. Pulls latest main
# 4. Creates fresh worktree from main
# 5. Starts new orchestrator session
```

### Forking (Preserve Context)

```bash
# Fork session to try different approach
agentwire fork -s myproject/feature -t myproject/experiment

# Steps:
# 1. Creates new worktree (experiment branch)
# 2. Forks Claude conversation context
# 3. New session continues from original's conversation
```

---

## Voice Interaction Tips

### Effective Voice Prompts

**Good prompts (natural, conversational):**
- "Add authentication"
- "Fix the timeout bug"
- "Run the tests"
- "What's the status?"

**Less effective (too technical):**
- "Edit line 42 of auth.py to add error handling"
- "Run pytest with verbose flag"

Let the orchestrator decide HOW to accomplish the work. Focus on WHAT you want.

### Using Voice vs Text

| Situation | Use Voice | Use Text |
|-----------|-----------|----------|
| Planning discussion | ✅ Natural | ❌ Slower |
| Quick requests | ✅ Fast | ✅ Also fine |
| Providing code snippets | ❌ Error-prone | ✅ Copy-paste |
| Reviewing logs/output | ❌ Hard to hear | ✅ Read visually |

---

## Remote Machine Workflows

### Setting Up Remote Sessions

```bash
# Add machine
agentwire machine add gpu-server --host 192.168.1.100 --user myuser

# Create remote session
agentwire new -s ml@gpu-server

# Session runs on gpu-server, accessible from portal
```

### Remote Worktrees

```bash
# Remote session with worktree
agentwire new -s ml/experiment@gpu-server

# Creates worktree on remote machine
# Session accessible via portal
```

### Monitoring Remote Sessions

All remote sessions appear in the portal dashboard. Click to open room page, interact via voice/text/terminal.

---

## Troubleshooting Common Issues

### Orchestrator Tries to Edit Files

**Symptom:** Orchestrator attempts Edit/Write/Read directly instead of spawning worker

**Cause:** Hooks not installed or not blocking properly

**Fix:**
```bash
agentwire skills install
# Verify ~/.claude/settings.json has orchestrator hooks
```

### Worker Asks User Questions

**Symptom:** Worker uses AskUserQuestion instead of returning to orchestrator

**Cause:** Worker hooks not blocking AskUserQuestion

**Fix:**
```bash
# Check settings.json has worker PreToolUse hooks
# Should block AskUserQuestion, remote-say, say
```

### No Voice Output

**Symptom:** Orchestrator doesn't speak results

**Cause:** Missing remote-say in orchestrator prompts or TTS not configured

**Fix:**
1. Verify TTS backend configured in `~/.agentwire/config.yaml`
2. Test: `agentwire say "test"`
3. Check orchestrator role file emphasizes remote-say

### Worker Output Too Verbose

**Symptom:** Worker provides long explanations instead of facts

**Cause:** Worker not following role instructions

**Fix:**
Ensure Task prompt includes role file reference:
```python
prompt="... Follow @~/.agentwire/roles/worker.md for output style."
```

### Session Won't Start

**Symptom:** `agentwire new` fails or session immediately exits

**Possible causes:**
1. Claude Code not installed: `which claude`
2. Wrong directory: verify path exists
3. Git repo issues: check `git status` in project dir

**Fix:**
```bash
# Install Claude Code
curl -sSL https://claude.ai/install.sh | bash

# Verify installation
claude --version

# Check session output
agentwire output -s myproject
```

---

## Advanced Patterns

### Multi-Project Coordination

Run orchestrator in main session, spawn workers for different projects:

```python
# Orchestrator in "control" session
Task(..., prompt="Update frontend in ~/projects/web-app")
Task(..., prompt="Update backend in ~/projects/api")
Task(..., prompt="Update docs in ~/projects/docs")
```

### Long-Running Background Work

For tasks that take minutes/hours (builds, tests, migrations):

```python
# Orchestrator spawns worker
Task(
  description="Run full test suite",
  prompt="""
  Run the complete test suite including integration tests.
  This may take 10-15 minutes.
  Report when complete.
  Follow @~/.agentwire/roles/worker.md
  """
)

# Worker runs tests in background, reports when done
# Orchestrator can handle other requests meanwhile
```

### Iterative Refinement

Use fork workflow for exploring different approaches:

```bash
# Original approach
agentwire new -s api/auth-v1

# Try alternative approach without losing v1
agentwire fork -s api/auth-v1 -t api/auth-v2

# Both sessions available, compare results
```

---

## Best Practices

### Session Naming

| Format | Example | Use For |
|--------|---------|---------|
| `project` | `api` | Single project, no branches |
| `project/feature` | `api/auth` | Feature branch work |
| `project@machine` | `ml@gpu` | Remote GPU work |
| `project/feature@machine` | `ml/train@gpu` | Remote feature branch |

### When to Recreate vs Fork

**Recreate:**
- Starting fresh from latest main
- Previous work is complete (merged to main)
- Want clean slate

**Fork:**
- Trying different approach
- Preserving conversation context is valuable
- Comparing multiple solutions

### Voice Room Etiquette

- Use meaningful session names (shows in portal)
- Close unused sessions (reduces clutter)
- Use templates for common setups
- Lock rooms when doing sensitive work (portal feature)

---

## Portal Features

### Dashboard

- Lists all sessions (local + remote)
- Shows session status (active/idle)
- Click session name to open room

### Room Modes

| Mode | Use For |
|------|---------|
| Ambient | Voice interaction, watching orb state |
| Monitor | Text prompts, reading output |
| Terminal | Direct terminal access (vim, REPL, etc.) |

### Actions Menu

**Regular sessions:**
- New Room: Create sibling session (parallel work)
- Fork Session: Preserve conversation context
- Recreate: Fresh start from main

**System sessions** (agentwire, portal, TTS):
- Restart Service: Proper restart sequence

---

## Session Templates

Templates provide pre-configured session setups.

### Using Templates

```bash
# List available templates
agentwire template list

# Create session with template
agentwire new -s myproject -t code-review

# Template applies:
# - Voice setting
# - Permission mode
# - Initial prompt
```

### Sample Templates

| Template | Purpose |
|----------|---------|
| code-review | Review code, find bugs |
| feature-impl | Implement features with planning |
| bug-fix | Systematic debugging |
| voice-assistant | Voice-only (restricted mode) |

### Creating Custom Templates

```bash
agentwire template create my-template
# Interactive prompts for settings
```

---

## Next Steps

- Read `CLAUDE.md` for complete architecture details
- Explore role files in `~/.agentwire/roles/`
- Check mission files in `docs/missions/` for examples
- Install skills: `agentwire skills install`
