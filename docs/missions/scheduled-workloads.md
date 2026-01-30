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

1. **`agentwire ensure`** - Reliable session + prompt execution
2. **Tasks in `.agentwire.yml`** - Named workflows with pre/prompt/post phases

## Deliverables

### 1. `ensure` Command

```bash
agentwire ensure -s newsbot --task news-check
agentwire ensure -s newsbot "inline prompt also works"
```

Behavior:
1. Session exists? If not, create it (using project's `.agentwire.yml`)
2. Session healthy? If not, recreate it
3. Session idle? If not, queue or wait
4. If `--task`: run pre-commands, template prompt
5. Send prompt to session
6. Wait for session to go idle (completion)
7. If `--task`: run post-commands, handle output

Flags:
- `-s, --session NAME` - Target session (required)
- `--task NAME` - Task from `.agentwire.yml`
- `--dry-run` - Show what would execute without running
- `--timeout SECONDS` - Max wait time for completion
- `--no-wait` - Fire and forget (skip post phase)

### 2. Task Definition Schema

Extend `.agentwire.yml` to support `tasks:` section:

```yaml
type: opencode-bypass
roles:
  - leader
voice: may

tasks:
  task-name:
    pre:                          # Optional: data gathering
      var_name: "shell command"
      other_var: "another command"
    prompt: |                     # Required: the prompt (supports {{ variables }})
      Do something with {{ var_name }}
      Write results to {{ output_file }}
    post:                         # Optional: list of commands to run after
      - "shell command with {{ output }}"
    output:                       # Optional: output handling
      file: path/to/output.md     # Where agent should write
      capture: 50                 # Lines to capture from session
      save: ~/logs/{{ task }}.log # Where to save captured output
      notify: voice               # Notification method
      on_success: "command"       # Run on success
      on_failure: "command"       # Run on failure
```

### 3. Built-in Variables

| Variable | Available In | Description |
|----------|--------------|-------------|
| `{{ var_name }}` | prompt, post | Output from pre command |
| `{{ output_file }}` | prompt, post | Path from `output.file` |
| `{{ output }}` | post | Captured session output |
| `{{ status }}` | post | `success` or `failure` |
| `{{ date }}` | all | YYYY-MM-DD |
| `{{ time }}` | all | HH:MM:SS |
| `{{ datetime }}` | all | Full ISO timestamp |
| `{{ session }}` | all | Session name |
| `{{ task }}` | all | Task name |

### 4. Task Management Commands

```bash
agentwire task list [SESSION]           # List tasks for session/project
agentwire task show SESSION/TASK        # Show task definition
agentwire task validate SESSION/TASK    # Validate task syntax
```

### 5. Notification Methods

| Method | Syntax | Description |
|--------|--------|-------------|
| Voice | `notify: voice` | `agentwire say "Task {task} complete"` |
| Alert | `notify: alert` | `agentwire alert "Task {task} complete"` |
| Webhook | `notify: webhook URL` | POST JSON to URL |
| Command | `notify: command "..."` | Run arbitrary command |

## Implementation Plan

### Phase 1: Core `ensure` Command
- [ ] Add `ensure` subcommand to CLI
- [ ] Session existence check (reuse from `send`)
- [ ] Session health check (can we send to it?)
- [ ] Session idle detection (reuse from portal)
- [ ] Create session if missing (reuse from `new`)
- [ ] Wait for completion (poll for idle)

### Phase 2: Task Loading
- [ ] Extend `.agentwire.yml` parser to load `tasks:` section
- [ ] Task schema validation (prompt required, pre/post are dicts/lists)
- [ ] `task list` command
- [ ] `task show` command
- [ ] `task validate` command

### Phase 3: Pre Phase
- [ ] Execute pre commands sequentially
- [ ] Capture stdout as variable values
- [ ] Fail fast on command failure
- [ ] Log stderr but don't capture

### Phase 4: Templating
- [ ] Implement `{{ variable }}` substitution
- [ ] Built-in variables (date, time, session, task, output_file)
- [ ] Error on undefined variables

### Phase 5: Post Phase
- [ ] Capture session output after idle
- [ ] Execute post commands with variables
- [ ] Determine success/failure status
- [ ] Run on_success/on_failure commands

### Phase 6: Output Handling
- [ ] `output.file` - inject into prompt as `{{ output_file }}`
- [ ] `output.capture` - capture N lines after completion
- [ ] `output.save` - save captured output to file
- [ ] `output.notify` - voice/alert/webhook/command

## Test Cases

### Basic Ensure
```bash
# Session doesn't exist - should create and send
agentwire ensure -s newproject "hello"

# Session exists and idle - should send immediately
agentwire ensure -s existingproject "hello"

# Session busy - should wait then send
agentwire ensure -s busyproject "hello"
```

### Task Execution
```yaml
# .agentwire.yml
tasks:
  simple:
    prompt: "Say hello"

  with-pre:
    pre:
      data: echo "test data"
    prompt: "Process: {{ data }}"

  full-workflow:
    pre:
      headlines: curl -s https://httpbin.org/json | jq '.slideshow.title'
    prompt: |
      Analyze: {{ headlines }}
      Write to: {{ output_file }}
    output:
      file: /tmp/test-output.md
      capture: 20
      save: /tmp/test-log.txt
      on_success: echo "SUCCESS"
      on_failure: echo "FAILURE"
```

### Morning Briefing (Real World)
```yaml
tasks:
  morning-briefing:
    pre:
      weather: curl -s "wttr.in/?format=3"
      calendar: gcal-cli today --json
      news: curl -s https://api.news.com/top | jq '.[:5]'
    prompt: |
      Good morning! Prepare my daily briefing.

      Weather: {{ weather }}
      Calendar: {{ calendar }}
      Top News: {{ news }}

      Summarize what I need to know.
      Write to: {{ output_file }}
      Then read it aloud.
    output:
      file: .agentwire/results/briefing.md
      save: ~/briefings/{{ date }}.md
      notify: voice
      on_failure: agentwire say "Briefing failed"
```

```bash
# Cron entry
0 7 * * * agentwire ensure -s newsbot --task morning-briefing
```

## Non-Goals

- **No built-in scheduler** - Users use cron/launchd/systemd
- **No job management UI** - Tasks are code, managed in yaml/git
- **No approval workflows** - Fire and execute
- **No cost guardrails** - User's API keys, user's problem
- **No prompt validation** - Minimal syntax check only

## Dependencies

- Jinja2 or similar for `{{ }}` templating (or simple regex replace)
- Existing: session management, idle detection, output capture

## Files to Modify

- `agentwire/__main__.py` - Add `ensure`, `task` commands
- `agentwire/config.py` - Extend `.agentwire.yml` schema for tasks
- `agentwire/tasks.py` - New module for task loading/execution
- `agentwire/templating.py` - New module for variable substitution

## Success Criteria

1. `agentwire ensure -s session "prompt"` works reliably from cron
2. Tasks with pre/prompt/post execute correctly
3. Variables substitute in prompt and post commands
4. Output capture and save works
5. Notifications fire on completion
6. Morning briefing example works end-to-end
