# Mission: Scheduled Workloads

> Reliable headless task execution with data pipeline

## Problem

Users want to run agent workloads on a schedule (cron), but can't reliably because:
- Session might not exist when cron fires
- Session might have crashed
- Session might be busy with other work
- No way to gather fresh data before prompting
- No way to capture/report results after

## Solution

Two primitives:

1. **`agentwire ensure`** - Reliable session management + task execution
2. **Tasks in `.agentwire.yml`** - Named workflows with pre/prompt/post phases

## Deliverables

### 1. `ensure` Command

Runs a named task from `.agentwire.yml` with reliable session management.

```bash
agentwire ensure -s newsbot --task news-check
agentwire ensure -s newsbot --task morning-briefing --timeout 600
```

**Note:** For ad-hoc prompts without task config, use `agentwire send` instead.

Behavior:
1. Acquire lock for session (fail if locked, or wait with `--wait-lock`)
2. Session exists? If not, create it (using project's `.agentwire.yml`)
3. Session healthy? If not, recreate it
4. Session idle? If not, wait until idle (respects `--timeout`)
5. Run pre-commands, validate outputs, template prompt
6. Send templated prompt to session
7. Wait for first idle (task work complete)
8. Send system summary prompt → agent writes `.agentwire/task-summary-{datetime}.md`
9. Wait for summary file to be created
10. Parse summary file for status
11. If `on_task_end` defined: send user's final prompt, wait for idle
12. Run post-commands with `{{ status }}` populated
13. If status is `failed` and retries remaining: wait `retry_delay`, retry from step 5
14. Release lock

Flags:
- `-s, --session NAME` - Target session (required)
- `--task NAME` - Task from `.agentwire.yml` (required)
- `--dry-run` - Show what would execute (skips pre commands with side effects)
- `--timeout SECONDS` - Max wait time for completion (default: 300)
- `--wait-lock` - Wait for lock instead of failing if session is locked
- `--lock-timeout SECONDS` - Max time to wait for lock (default: 60)

Exit codes:
| Code | Meaning |
|------|---------|
| 0 | Task completed successfully (`status: complete`) |
| 1 | Task failed (`status: failed`) |
| 2 | Task incomplete (`status: incomplete`) |
| 3 | Lock conflict (session locked, `--wait-lock` not used) |
| 4 | Pre-phase failure (command failed, validation failed, or timeout) |
| 5 | Timeout (hard timeout exceeded) |
| 6 | Session error (couldn't create, recreate, or connect to session) |

#### Completion Detection

Completion uses a two-phase prompt system at task end. This is reliable because we prompt the agent directly at the right moment, rather than hoping it follows instructions from earlier.

**Phase 1: System Summary (always runs)**

When first idle is detected after the task prompt, we send:

```
Write a task summary to .agentwire/task-summary-{timestamp}.md in YAML format:

---
status: complete | incomplete | failed
summary: one line describing what you accomplished
files_modified:
  - path/to/file1
  - path/to/file2
blockers:
  - any issues preventing completion
---

Additional notes can follow the YAML front matter.
```

The YAML front matter is machine-parseable for extracting `{{ status }}` and `{{ summary }}`.

**Phase 2: User's `on_task_end` (if defined)**

After the system summary is written, we send the user's custom prompt:

```
{{ user's on_task_end content }}

Reference {{ summary_file }} for task outcome.
```

This gives users full control of the final interaction, with access to the structured summary.

**Completion signals:**

| Signal | How Detected | Indicates |
|--------|--------------|-----------|
| Summary file exists | `.agentwire/task-summary-{datetime}.md` created | Agent responded to system prompt |
| Second idle | Session idle after on_task_end | All prompts processed |
| Hard timeout | `--timeout` exceeded | Failure |

**Summary file naming:** Each task run creates a new timestamped file (e.g., `.agentwire/task-summary-2024-01-15T07-00-00.md`). This preserves history across runs. User manages cleanup.

**Task-level configuration:**

```yaml
tasks:
  my-task:
    prompt: "..."
    idle_timeout: 30              # Seconds of idle before triggering completion (default: 30)
    on_task_end: |                # Optional: user's final prompt (runs after system summary)
      If status is complete, announce success.
      If failed, explain what went wrong.
```

#### Concurrency & Locking

Each session has a lock file at `~/.agentwire/locks/{session}.lock`. The lock:
- Is acquired at start of `ensure` command
- Is released after post-phase completes (or on error/timeout)
- Uses flock for atomic acquisition
- Has configurable timeout for waiting

```bash
# Fail immediately if locked
agentwire ensure -s bot --task daily  # Returns exit code 3 if locked

# Wait up to 2 minutes for lock
agentwire ensure -s bot --task daily --wait-lock --lock-timeout 120
```

### 2. Task Definition Schema

Extend `.agentwire.yml` to support `tasks:` section:

```yaml
type: opencode-bypass
roles:
  - leader
voice: may
shell: /bin/sh               # Optional: default shell for task commands (default: /bin/sh)

tasks:
  task-name:
    shell: /bin/bash         # Optional: override shell for this task
    retries: 2               # Optional: retry count on failure (default: 0)
    retry_delay: 30          # Optional: seconds between retries (default: 30)
    pre:                     # Optional: data gathering (NO {{ }} variables - these PRODUCE variables)
      var_name:
        cmd: "shell command"
        required: true       # Fail if output is empty (default: false)
        validate: "jq . > /dev/null"  # Optional validation command
        timeout: 30          # Optional: command timeout in seconds
      other_var: "simple command"     # Shorthand (no validation)
    prompt: |                # Required: the prompt (supports {{ variables }})
      Do something with {{ var_name }}
    idle_timeout: 30         # Optional: seconds of idle before completion (default: 30)
    on_task_end: |           # Optional: user's final prompt after system summary
      Read {{ summary_file }}.
      If complete, do X. If failed, do Y.
    post:                    # Optional: list of commands to run after (supports {{ variables }})
      - "shell command with {{ status }}"
    output:                  # Optional: output handling
      capture: 50                 # Lines to capture from session
      save: ~/logs/{{ task }}.log # Where to save captured output
      notify: voice               # Notification method (supports ${ENV_VAR} expansion)
```

### 3. Built-in Variables

| Variable | Available In | Description |
|----------|--------------|-------------|
| `{{ var_name }}` | prompt, on_task_end, post | Output from pre command |
| `{{ summary_file }}` | on_task_end, post | Path to current run's summary file |
| `{{ output }}` | post | Captured session output |
| `{{ status }}` | on_task_end, post | `complete`, `incomplete`, or `failed` (from summary) |
| `{{ summary }}` | on_task_end, post | One-line summary from summary file |
| `{{ date }}` | all | YYYY-MM-DD |
| `{{ time }}` | all | HH:MM:SS |
| `{{ datetime }}` | all | Full ISO timestamp |
| `{{ session }}` | all | Session name |
| `{{ task }}` | all | Task name |
| `{{ project_root }}` | all | Absolute path to project directory |
| `{{ attempt }}` | prompt, on_task_end, post | Current attempt number (1-based, for retries) |

**Variable scope rules:**
- `pre:` commands **produce** variables - they cannot use `{{ }}` syntax
- `prompt:`, `on_task_end:`, and `post:` commands **consume** variables
- Environment variables use `${ENV_VAR}` syntax (expanded at runtime)

### 4. Task Management Commands

```bash
agentwire task list [SESSION]           # List tasks for session/project
agentwire task show SESSION/TASK        # Show task definition
agentwire task validate SESSION/TASK    # Validate task syntax
```

### 5. Notification Methods

| Method | Syntax | Description |
|--------|--------|-------------|
| Voice | `notify: voice` | `agentwire say "Task {task} {status}"` |
| Alert | `notify: alert` | `agentwire alert "Task {task} {status}"` |
| Webhook | `notify: webhook ${SLACK_WEBHOOK}` | POST JSON to URL (supports `${ENV_VAR}` expansion) |
| Command | `notify: command "..."` | Run arbitrary command |

**Webhook payload:**
```json
{
  "task": "task-name",
  "session": "session-name",
  "status": "complete|incomplete|failed",
  "summary": "one-line summary from agent",
  "timestamp": "ISO8601",
  "attempt": 1
}
```

**Webhook security:** Never hardcode secrets in `.agentwire.yml`. Use environment variable expansion:
```yaml
output:
  notify: webhook ${SLACK_WEBHOOK_URL}  # Expanded at runtime from environment
```

## Implementation Plan

### Phase 1: Core `ensure` Command
- [ ] Add `ensure` subcommand to CLI
- [ ] Session existence check (reuse from `send`)
- [ ] Session health check (can we send to it?)
- [ ] Session idle detection (reuse from portal)
- [ ] Create session if missing (reuse from `new`)
- [ ] Basic wait for idle
- [ ] Implement exit codes (0-6) for different outcomes

### Phase 2: Locking
- [ ] Create `~/.agentwire/locks/` directory structure
- [ ] Implement flock-based session locking
- [ ] Add `--wait-lock` and `--lock-timeout` flags
- [ ] Release lock on completion, error, or timeout

### Phase 3: Task Loading
- [ ] Extend `.agentwire.yml` parser to load `tasks:` section
- [ ] Task schema validation (prompt required, pre/post structure)
- [ ] Support both shorthand (`var: "cmd"`) and expanded (`var: {cmd, required, validate}`) pre syntax
- [ ] `task list` command
- [ ] `task show` command
- [ ] `task validate` command

### Phase 4: Templating
- [ ] Implement `{{ variable }}` substitution
- [ ] Implement `${ENV_VAR}` expansion for environment variables
- [ ] Built-in variables (date, time, session, task, project_root, attempt, summary_file)
- [ ] Error on undefined `{{ }}` variables
- [ ] Pass through undefined `${ENV_VAR}` (shell will handle or error)

### Phase 5: Pre Phase
- [ ] Execute pre commands sequentially
- [ ] Capture stdout as variable values
- [ ] Fail on non-zero exit code
- [ ] Validate `required: true` (fail if output empty)
- [ ] Run `validate` command if specified (fail on non-zero)
- [ ] Implement per-command `timeout` option
- [ ] Log stderr but don't capture as variable
- [ ] On pre failure: release lock and exit with code 4 (no prompt sent, no post-phase)

### Phase 6: Completion Detection
- [ ] Detect first idle after task prompt sent
- [ ] Generate timestamped summary filename (e.g., `task-summary-2024-01-15T07-00-00.md`)
- [ ] Send system summary prompt with the generated filename
- [ ] Watch for summary file creation
- [ ] Parse summary file for status/summary fields
- [ ] Set `{{ status }}`, `{{ summary }}`, and `{{ summary_file }}` variables
- [ ] Send user's `on_task_end` prompt if defined (with variables expanded)
- [ ] Detect second idle (all prompts processed)
- [ ] Implement hard timeout (`--timeout` flag)

### Phase 7: Retry Logic
- [ ] Implement `retries` count from task config (default 0)
- [ ] Implement `retry_delay` seconds between attempts
- [ ] Track `{{ attempt }}` variable
- [ ] Only retry on `failed` status (not `complete` or `incomplete`)
- [ ] Recreate session if it crashed during task
- [ ] Each retry creates new timestamped summary file

### Phase 8: Post Phase
- [ ] Capture session output after completion
- [ ] Execute post commands with variables
- [ ] Handle different status values appropriately

### Phase 9: Output Handling
- [ ] `output.capture` - capture N lines after completion
- [ ] `output.save` - save captured output to file (with `{{ }}` expansion in path)
- [ ] `output.notify` - voice/alert/webhook/command with `${ENV_VAR}` expansion
- [ ] Webhook POST with JSON payload

### Phase 10: MCP Tools
- [ ] `agentwire_task_list` - list tasks for session
- [ ] `agentwire_task_show` - show task definition
- [ ] `agentwire_task_run` - run named task with full lifecycle

### Phase 11: Roles
- [ ] Create `task-runner` role for scheduled execution
- [ ] Update `leader` role with scheduled context section
- [ ] Consider `--role` override for tasks

### Phase 12: Documentation
- [ ] Update CLAUDE.md with ensure/task commands
- [ ] Update CLAUDE.md MCP tools table
- [ ] Finalize docs/scheduled-workloads.md for users
- [ ] Add examples to role files

## Test Cases

### Basic Ensure
```bash
# Session doesn't exist - should create and run task
agentwire ensure -s newsbot --task daily-check

# Session exists and idle - should run immediately
agentwire ensure -s newsbot --task daily-check

# Session busy - should wait until idle, then run
agentwire ensure -s newsbot --task daily-check

# Session locked by another ensure - should fail immediately
agentwire ensure -s newsbot --task daily-check  # Returns exit code 3

# Session locked - wait for lock
agentwire ensure -s newsbot --task daily-check --wait-lock --lock-timeout 60
```

### Locking
```bash
# In terminal 1 (holds lock for duration of task)
agentwire ensure -s bot --task long-running

# In terminal 2 (fails immediately)
agentwire ensure -s bot --task quick-check
# Error: Session 'bot' is locked by another ensure process

# In terminal 2 (waits for lock)
agentwire ensure -s bot --task quick-check --wait-lock
# Blocks until terminal 1 releases lock
```

### Pre Validation
```yaml
# .agentwire.yml
tasks:
  with-validation:
    pre:
      api_data:
        cmd: "curl -s https://api.example.com/data"
        required: true  # Fail if empty response
        validate: "jq . > /dev/null"  # Fail if not valid JSON
        timeout: 30     # Fail if takes longer than 30s
    prompt: "Process: {{ api_data }}"
```

```bash
# API returns empty - should fail before sending prompt
agentwire ensure -s bot --task with-validation
# Error: Pre command 'api_data' returned empty output (required: true)

# API returns invalid JSON - should fail validation
agentwire ensure -s bot --task with-validation
# Error: Pre command 'api_data' failed validation
```

### Completion Flow
```yaml
tasks:
  with-on-task-end:
    prompt: "Analyze the codebase and identify issues"
    on_task_end: |
      Read {{ summary_file }}.
      If status is complete, say "Analysis finished" aloud.
      If status is failed, explain what went wrong.
```

Flow:
1. Prompt sent: "Analyze the codebase..."
2. Agent works, goes idle
3. System prompt sent: "Write a task summary to .agentwire/task-summary-{datetime}.md..."
4. Agent writes summary, goes idle
5. User's on_task_end sent: "Read {{ summary_file }}..." (with actual path)
6. Agent reads summary, speaks result, goes idle
7. Task complete, post-phase runs

### Retry Logic
```yaml
tasks:
  flaky-api:
    retries: 2
    retry_delay: 30
    pre:
      data:
        cmd: "curl -s https://flaky-api.example.com/data"
        required: true
        timeout: 10
    prompt: "Process: {{ data }}"
```

```bash
# First attempt fails (API down), waits 30s, retries
# Second attempt fails, waits 30s, retries
# Third attempt succeeds
agentwire ensure -s bot --task flaky-api
# Output shows: Attempt 3/3 succeeded
```

### Task Execution
```yaml
# .agentwire.yml
tasks:
  simple:
    prompt: "Say hello"

  with-pre:
    pre:
      data: echo "test data"  # Shorthand syntax
    prompt: "Process: {{ data }}"

  full-workflow:
    pre:
      headlines:
        cmd: "curl -s https://httpbin.org/json | jq '.slideshow.title'"
        required: true
        timeout: 15
    prompt: |
      Analyze: {{ headlines }}
    on_task_end: |
      Read {{ summary_file }}.
      If complete, save your analysis to /tmp/analysis.md
    post:
      - "echo 'Task {{ task }} finished with status: {{ status }}'"
    output:
      capture: 20
      save: /tmp/test-log.txt
```

### Morning Briefing (Real World)
```yaml
tasks:
  morning-briefing:
    retries: 1
    retry_delay: 60
    pre:
      weather: curl -s "wttr.in/?format=3"
      calendar:
        cmd: "gcal-cli today --json"
        required: true
        timeout: 30
      news:
        cmd: "curl -s https://api.news.com/top | jq '.[:5]'"
        validate: "jq . > /dev/null"
        timeout: 30
    prompt: |
      Good morning! Prepare my daily briefing.

      Weather: {{ weather }}
      Calendar: {{ calendar }}
      Top News: {{ news }}

      Summarize what I need to know today.
    on_task_end: |
      Read {{ summary_file }}.
      If status is complete:
        - Save the briefing to ~/briefings/{{ date }}.md
        - Read the briefing aloud
      If status is failed or incomplete:
        - Say "Briefing could not be completed" and explain why
    post:
      - "cp {{ summary_file }} ~/logs/briefing-{{ datetime }}.md"
    output:
      capture: 50
      save: ~/briefings/{{ date }}-log.txt
      notify: webhook ${SLACK_BRIEFING_WEBHOOK}
```

```bash
# Cron entry
0 7 * * * agentwire ensure -s newsbot --task morning-briefing --timeout 600
```

## Dry Run Behavior

`--dry-run` shows what would execute without making changes:

| Phase | Dry Run Behavior |
|-------|-----------------|
| Lock | Skipped (no lock acquired) |
| Session check | Shows what would happen (create/recreate/use existing) |
| Pre phase | Shows commands but **does not execute** (may have side effects) |
| Prompt | Shows final templated prompt (with built-in vars only) |
| Send | Skipped |
| System summary prompt | Shows the hardcoded prompt |
| on_task_end | Shows user's prompt (if defined) |
| Post phase | Shows commands but does not execute |

**Note:** Since pre commands don't run in dry-run mode, `{{ var_name }}` variables will show as `<pre:var_name>` placeholders in the prompt output.

## Non-Goals

- **No built-in scheduler** - Users use cron/launchd/systemd
- **No job management UI** - Tasks are code, managed in yaml/git
- **No approval workflows** - Fire and execute
- **No cost guardrails** - User's API keys, user's problem
- **No prompt validation** - Minimal syntax check only
- **No task inheritance** - Each task is standalone (use YAML anchors if needed)
- **No sentinel files** - We don't rely on agents following "write to X when done" instructions
- **No automatic cleanup** - Summary files persist; user manages cleanup

## Cross-Platform

Works on macOS and Linux. Windows not supported (no tmux).

| Component | Approach |
|-----------|----------|
| Shell | Default `/bin/sh` (POSIX), user can override per-project or per-task |
| Paths | Python pathlib, `~/` expansion handled |
| User commands | User's responsibility to write portable pre/post commands |

Shell configuration:
```yaml
# Project-level default
shell: /bin/sh

tasks:
  needs-bash:
    shell: /bin/bash  # Task-level override
    pre:
      data: "bash-specific stuff"
```

Default: `/bin/sh` for maximum portability. Users who need bash/zsh features can override.

## Dependencies

- Jinja2 or similar for `{{ }}` templating (or simple regex replace)
- `fcntl` (stdlib) for flock-based locking
- Existing: session management, idle detection, output capture

**Note:** No external dependencies required beyond what's already in the project. Locking uses Python's `fcntl.flock()` which is available on macOS and Linux.

## Files to Modify

- `agentwire/__main__.py` - Add `ensure`, `task` commands
- `agentwire/config.py` - Extend `.agentwire.yml` schema for tasks
- `agentwire/tasks.py` - New module for task loading/execution
- `agentwire/templating.py` - New module for `{{ }}` and `${ENV}` substitution
- `agentwire/locking.py` - New module for session locking (flock-based)
- `agentwire/completion.py` - New module for completion detection (idle + summary file)
- `agentwire/mcp_server.py` - Add MCP tools for tasks
- `agentwire/roles/*.md` - Update/add roles for scheduled work
- `CLAUDE.md` - Document new commands and MCP tools
- `docs/scheduled-workloads.md` - User-facing documentation

## MCP Tools

New tools for agents to work with tasks:

```python
@mcp.tool()
def task_list(session: str | None = None) -> str:
    """List available tasks for a session/project.

    Args:
        session: Session name (uses its project's .agentwire.yml)

    Returns:
        JSON list of task names and descriptions
    """

@mcp.tool()
def task_show(session: str, task: str) -> str:
    """Show task definition details.

    Args:
        session: Session name
        task: Task name from .agentwire.yml

    Returns:
        JSON with full task configuration
    """

@mcp.tool()
def task_run(session: str, task: str, timeout: int = 300) -> str:
    """Run a named task from .agentwire.yml.

    Executes full task lifecycle:
    1. Acquire lock, ensure session exists and is healthy
    2. Run pre-commands, validate outputs
    3. Send templated prompt, wait for idle
    4. Send system summary prompt, wait for summary file
    5. Send on_task_end if defined, wait for idle
    6. Run post-commands
    7. Release lock

    Args:
        session: Target session name
        task: Task name from .agentwire.yml
        timeout: Max seconds to wait (default 300)

    Returns:
        JSON with status, summary, output capture, and attempt count
    """
```

**Note:** For ad-hoc prompts without task config, use the existing `session_send()` MCP tool.

## Role Updates

### New Role: `task-runner`

Optimized for scheduled/headless execution:

```markdown
# Task Runner

You're executing a scheduled task. Work autonomously and report results.

## Context

You're running as part of a scheduled workflow:
- Pre-commands have already gathered data (in your prompt)
- When you go idle, you'll be asked to write a task summary
- If on_task_end is defined, you'll get a final prompt after the summary
- Post-commands will handle notifications

## Task Summary Format

When asked to write the task summary, use YAML front matter:

\`\`\`yaml
---
status: complete
summary: Brief description of what you accomplished
files_modified:
  - src/feature.py
  - tests/test_feature.py
blockers: []
---
\`\`\`

Additional notes can follow the front matter if needed.

## Expectations

- Complete the task without user interaction
- Be honest about status - use 'incomplete' if you couldn't finish
- Use voice sparingly (scheduled = possibly unattended)
- Be concise - this runs repeatedly
```

### Update: `leader` Role

Add section for scheduled context awareness:

```markdown
## Scheduled Execution

When running via `agentwire ensure --task`:
- Pre-phase has populated your context with fresh data
- You'll be prompted for a summary when you finish
- on_task_end gives you a chance for final actions (voice, save files)
- Post-phase will handle notifications
- Keep output structured for automation
```

## Documentation Updates

### CLAUDE.md Additions

```markdown
## Scheduled Workloads

### ensure Command

\`\`\`bash
agentwire ensure -s session --task name           # Run named task
agentwire ensure -s session --task name --wait-lock  # Wait if locked
agentwire ensure -s session --task name --timeout 600  # Custom timeout
\`\`\`

Runs a named task from `.agentwire.yml` with reliable session management. Acquires lock to prevent concurrent execution. For ad-hoc prompts, use `agentwire send` instead.

### Tasks

Define in `.agentwire.yml`:

\`\`\`yaml
tasks:
  task-name:
    retries: 2
    pre:
      var: "command"              # Shorthand
      data:
        cmd: "curl api"           # With validation
        required: true
        validate: "jq . > /dev/null"
        timeout: 30
    prompt: "Use {{ var }} and {{ data }}"
    on_task_end: |                # Optional: runs after system summary
      Read {{ summary_file }}.
      If complete, announce success.
    output:
      notify: webhook ${SLACK_URL}
\`\`\`

### Completion Flow

1. Task prompt sent
2. Agent works, goes idle
3. System prompts for `.agentwire/task-summary-{datetime}.md`
4. If `on_task_end` defined, user's prompt sent (can reference `{{ summary_file }}`)
5. Post-phase runs with `{{ status }}` from summary

### MCP Tools

| CLI | MCP Tool |
|-----|----------|
| `agentwire ensure -s x --task y` | `agentwire_task_run(session="x", task="y")` |
| `agentwire task list x` | `agentwire_task_list(session="x")` |
| `agentwire task show x/y` | `agentwire_task_show(session="x", task="y")` |
```

## Success Criteria

1. `agentwire ensure -s session --task name` works reliably from cron
2. Concurrent `ensure` calls to same session are properly serialized (locking works)
3. Tasks with pre/prompt/post execute correctly
4. Pre command validation (`required`, `validate`, `timeout`) catches bad data before prompting
5. Variables substitute in prompt, on_task_end, and post commands (`{{ }}` and `${ENV}`)
6. Completion detection works via idle + system summary prompt
7. `on_task_end` prompt fires after system summary, with access to `{{ summary_file }}`
8. `{{ status }}` in post-phase comes from parsed summary file
9. Summary files are timestamped, preserving history across runs
10. Retry logic recovers from transient failures (retries on `failed` status)
11. Notifications fire on completion (including webhook with env var expansion)
12. Exit codes accurately reflect outcome (0=complete, 1=failed, 2=incomplete, etc.)
13. Morning briefing example works end-to-end
