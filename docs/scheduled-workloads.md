# Scheduled Workloads

> Living document. Update this, don't create new versions.

## The Problem

Users can't reliably cron `agentwire send` because:
- Session might not exist
- Session might have crashed
- Session might be busy
- No way to gather fresh data before prompting
- No way to capture/report results after

## The Primitive: `agentwire ensure`

```bash
agentwire ensure -s newsbot --task news-check
```

Does:
1. Session exists? If not, create it (using project's `.agentwire.yml`)
2. Session healthy? If not, recreate it
3. Session idle? If not, queue or wait
4. Run pre-commands, gather data
5. Template and send the prompt
6. Wait for completion
7. Run post-commands, report results

**Agentwire value:** Reliable headless task execution with data pipeline.

## Task Lifecycle

Three phases, all optional:

```
┌─────────────────────────────────────────────────────────────┐
│  PRE                                                        │
│  Gather data deterministically                              │
│  Shell commands → variables                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  PROMPT                                                     │
│  Template with variables → send to agent                    │
│  Agent does work, writes to output_file                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  POST                                                       │
│  Capture session output                                     │
│  Run commands, notify, save logs                            │
└─────────────────────────────────────────────────────────────┘
```

## Task Definition

Tasks live in `.agentwire.yml`:

```yaml
type: opencode-bypass
roles:
  - leader
voice: may

tasks:
  news-check:
    pre:
      headlines: curl -s https://api.news.com/latest | jq '.headlines[:10]'
      sources: cat ~/.newsbot/sources.txt
    prompt: |
      Here are today's headlines:
      {{ headlines }}

      Check against our tracked sources:
      {{ sources }}

      Write findings to: {{ output_file }}
      Alert via voice if anything critical.
    post:
      - slack-cli post "#news" "$(cat {{ output_file }})"
    output:
      file: .agentwire/results/news-check.md
      capture: 50
      save: ~/logs/news/{{ date }}.log
      on_success: agentwire say "News check complete"
      on_failure: agentwire say "News check failed"

  daily-summary:
    pre:
      commits: git log --oneline --since="yesterday"
      issues: gh issue list --state closed --json title,closedAt
      prs: gh pr list --state merged --json title,mergedAt
    prompt: |
      Generate daily summary from:

      Commits:
      {{ commits }}

      Closed Issues:
      {{ issues }}

      Merged PRs:
      {{ prs }}

      Save to: {{ output_file }}
    output:
      file: reports/daily-{{ date }}.md
      notify: voice

  cleanup:
    prompt: "Archive logs older than 7 days, clean temp files"
    output:
      capture: 20
      save: ~/logs/cleanup.log
```

## Built-in Variables

Available in `prompt` and `post`:

| Variable | Description |
|----------|-------------|
| `{{ var_name }}` | Output from pre command with that name |
| `{{ output_file }}` | Path where agent should write results |
| `{{ output }}` | Captured session output after completion |
| `{{ status }}` | `success` or `failure` |
| `{{ date }}` | Current date (YYYY-MM-DD) |
| `{{ time }}` | Current time (HH:MM:SS) |
| `{{ datetime }}` | Full timestamp |
| `{{ session }}` | Session name |
| `{{ task }}` | Task name |

## Output Options

```yaml
output:
  file: path/to/output.md      # Tell agent where to write (via {{ output_file }})
  capture: 50                   # Capture last N lines of session after idle
  save: ~/logs/{{ task }}.log  # Save captured output to file
  notify: voice                 # Notification method (see below)
  on_success: "command"         # Run on success
  on_failure: "command"         # Run on failure
```

### Notification Methods

| Method | Description |
|--------|-------------|
| `voice` | `agentwire say "Task complete"` |
| `alert` | `agentwire alert "Task complete"` |
| `webhook URL` | POST to webhook with JSON payload |
| `command` | Run arbitrary command |

## Usage

```bash
# Run a task
agentwire ensure -s newsbot --task news-check

# List tasks for a project
agentwire task list newsbot

# Validate task syntax
agentwire task validate newsbot/news-check

# Dry run (show what would execute)
agentwire ensure -s newsbot --task news-check --dry-run
```

## Cron Integration

Users manage their own scheduling:

```bash
# crontab -e
*/30 * * * * agentwire ensure -s newsbot --task news-check
0 9 * * * agentwire ensure -s myproject --task daily-summary
0 2 * * 0 agentwire ensure -s myproject --task cleanup
```

## Mental Model

| Layer | Purpose | Where |
|-------|---------|-------|
| **Type** | Permissions | .agentwire.yml |
| **Roles** | Identity (who) | .agentwire.yml → roles/ |
| **Tasks** | Work items (what) | .agentwire.yml tasks: |

| Phase | Purpose | Control |
|-------|---------|---------|
| **Pre** | Data in | Deterministic, user-controlled |
| **Prompt** | Work | Agent execution |
| **Post** | Data out | Deterministic, user-controlled |

## Example: Full Workflow

```yaml
# ~/projects/newsbot/.agentwire.yml
type: opencode-bypass
roles:
  - leader
voice: may

tasks:
  morning-briefing:
    pre:
      weather: curl -s "wttr.in/?format=3"
      calendar: gcal-cli today --json
      news: curl -s https://api.news.com/top | jq '.[:5]'
      emails: gmail-cli unread --count
    prompt: |
      Good morning! Prepare my daily briefing.

      Weather: {{ weather }}
      Calendar: {{ calendar }}
      Top News: {{ news }}
      Unread Emails: {{ emails }}

      Summarize what I need to know and any actions for today.
      Write to: {{ output_file }}
      Then read the summary aloud.
    output:
      file: .agentwire/results/briefing.md
      save: ~/briefings/{{ date }}.md
      on_failure: agentwire say "Failed to generate briefing"
```

```bash
# crontab
0 7 * * * agentwire ensure -s newsbot --task morning-briefing
```

## Implementation Notes

### Pre Phase
- Commands run sequentially
- Fail fast if any command fails
- Stdout captured as variable value
- Stderr logged but not captured

### Prompt Phase
- Template variables with `{{ name }}` syntax
- `{{ output_file }}` always available if `output.file` defined
- Wait for session to go idle (task complete)

### Post Phase
- `{{ output }}` contains captured session output
- Commands have access to all variables
- `on_success`/`on_failure` based on session completion status

## Validation

Minimal - it's their system:
- Valid YAML syntax
- Task has `prompt` field
- Pre commands are strings
- Template variables exist

No gatekeeping on prompt content, command safety, etc.
