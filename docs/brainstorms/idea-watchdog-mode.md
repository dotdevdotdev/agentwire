# Watchdog Mode: Proactive Monitoring Without Polling

> Background monitors that speak alerts when specific conditions trigger, without being asked.

## Problem

AgentWire is reactive. It speaks when you ask, notifies when workers go idle, but doesn't proactively watch for events that matter. Meanwhile:

- Build breaks and you don't know until you try to deploy
- A PR gets approved but you're deep in another task
- Tests start failing after a dependency update
- A worker has been stuck for 10 minutes but hasn't gone "idle"
- CI completes but no one tells you

You have to remember to check these things. Or you notice them late, after wasting time on code that won't work anyway.

**The system knows these events happen. It just doesn't tell you.**

## Proposed Solution

**Watchdog Mode** - lightweight background monitors that trigger voice alerts when conditions are met.

### Core Concept

Define watches that run periodically or react to events:

```yaml
# ~/.agentwire/watchdogs.yaml
watchdogs:
  build-health:
    check: "npm run build --dry-run 2>&1"
    interval: 5m
    on_failure:
      say: "Build is broken. Error in {stderr_preview}"
      action: alert  # or: spawn-worker, pause-workers, etc.
    on_recovery:
      say: "Build is healthy again"

  ci-status:
    check: "gh run list --limit 1 --json status,conclusion -q '.[0]'"
    interval: 2m
    condition: ".conclusion == 'failure'"
    on_trigger:
      say: "CI failed on the latest push"

  pr-approved:
    event: github.pull_request.approved  # webhook-style
    on_trigger:
      say: "Your PR was approved by {approver}"

  worker-stuck:
    check: "agentwire panes list --json"
    interval: 1m
    condition: "any(.duration > '10m' and .status == 'active')"
    on_trigger:
      say: "Pane {pane} has been running for {duration} without progress"
```

### Watch Types

**1. Polling Watches**

Run a command periodically, check output against condition:

```yaml
disk-space:
  check: "df -h / | tail -1 | awk '{print $5}' | tr -d '%'"
  interval: 10m
  condition: "> 90"
  on_trigger:
    say: "Disk is {value} percent full"
```

**2. File Watches**

React to file changes (using fswatch/inotify):

```yaml
lockfile-changed:
  watch_files:
    - "package-lock.json"
    - "pnpm-lock.yaml"
  on_change:
    say: "Dependencies changed. You may want to run install."

env-modified:
  watch_files:
    - ".env"
    - ".env.local"
  on_change:
    say: "Environment file changed"
    action: none  # Just inform, no action
```

**3. Event Watches**

Subscribe to external events via webhooks or integrations:

```yaml
github-mentions:
  event: github.issue.mentioned
  on_trigger:
    say: "You were mentioned in issue {issue_number}: {title}"

slack-dm:
  event: slack.direct_message
  on_trigger:
    say: "New Slack message from {sender}"
```

**4. Process Watches**

Monitor background processes:

```yaml
dev-server:
  process: "next dev"  # or PID file
  on_crash:
    say: "Dev server crashed. Restarting."
    action: "npm run dev &"

test-watcher:
  process: "vitest"
  on_failure:
    say: "Tests are failing"
```

### Condition Language

Simple expression language for conditions:

```yaml
# Numeric comparisons
condition: "> 90"
condition: "< 10"
condition: "== 0"

# String matching
condition: "contains 'error'"
condition: "matches 'FAIL.*test'"

# JSON path (for structured output)
condition: ".status == 'failure'"
condition: "any(.items[].health == 'unhealthy')"

# Exit code
condition: "exit != 0"
```

### Actions

What happens when a watchdog triggers:

| Action | Description |
|--------|-------------|
| `say: "..."` | Speak the message (default) |
| `alert: "..."` | Text notification, no audio |
| `spawn-worker: {role}` | Spawn a worker to handle it |
| `send: {session} {message}` | Delegate to another session |
| `pause-workers` | Pause all active workers |
| `run: "command"` | Execute a shell command |
| `webhook: {url}` | POST to a webhook |
| `none` | Log but take no action |

Multiple actions can chain:

```yaml
on_trigger:
  - say: "Build failed"
  - pause-workers
  - spawn-worker:
      role: build-fixer
      task: "diagnose and fix the build"
```

### Cooldown and Debounce

Prevent alert fatigue:

```yaml
build-health:
  check: "npm run build"
  interval: 5m
  cooldown: 30m  # Don't re-alert for 30 min after trigger
  debounce: 10s  # Wait for condition to stabilize
```

### Scoping

Watchdogs can be:
- **Global** (`~/.agentwire/watchdogs.yaml`) - Always active
- **Project** (`.agentwire.yml`) - Only when in that project
- **Session** - Created dynamically via voice/CLI

```yaml
# In .agentwire.yml (project-specific)
watchdogs:
  e2e-tests:
    check: "playwright test --list | wc -l"
    interval: 10m
    condition: "== 0"
    on_trigger:
      say: "E2E tests aren't finding any test files"
```

### Status Dashboard

Track watchdog state:

```bash
# CLI
agentwire watchdog list
agentwire watchdog status
agentwire watchdog logs
agentwire watchdog pause build-health
agentwire watchdog resume build-health

# Voice
[User]: "What watchdogs are active?"
[System]: "3 watchdogs active: build-health, ci-status, and worker-stuck"

[User]: "Pause watchdogs"
[System]: "All watchdogs paused. Say 'resume watchdogs' to restart."
```

### Dynamic Watchdogs

Create watchdogs via voice:

```
[User]: "Watch for test failures"
[System]: "Created watchdog. I'll alert you if tests fail."

[User]: "Tell me when the build finishes"
[System]: "Watching CI status. I'll speak when the run completes."

[User]: "Stop watching tests"
[System]: "Test watchdog removed."
```

These create temporary session-scoped watchdogs that disappear when the session ends.

## Implementation

### Architecture

```
┌─────────────────────────────────────────────┐
│  Watchdog Manager (background process)      │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ Polling │ │  File   │ │  Event  │       │
│  │ Watches │ │ Watches │ │ Watches │       │
│  └────┬────┘ └────┬────┘ └────┬────┘       │
│       │           │           │             │
│       └───────────┴───────────┘             │
│                   │                         │
│           ┌───────▼───────┐                 │
│           │   Evaluator   │                 │
│           │  (conditions) │                 │
│           └───────┬───────┘                 │
│                   │                         │
│           ┌───────▼───────┐                 │
│           │    Actions    │                 │
│           │   (say, etc)  │                 │
│           └───────────────┘                 │
└─────────────────────────────────────────────┘
```

### Watchdog Manager

Runs as part of the portal (or standalone):

```python
class WatchdogManager:
    def __init__(self):
        self.watchdogs: dict[str, Watchdog] = {}
        self.cooldowns: dict[str, datetime] = {}

    async def run(self):
        """Main loop - check all watchdogs."""
        while True:
            for name, watchdog in self.watchdogs.items():
                if self.should_check(name, watchdog):
                    result = await watchdog.check()
                    if result.triggered:
                        await self.handle_trigger(name, watchdog, result)

            await asyncio.sleep(1)  # Base tick rate

    async def handle_trigger(self, name: str, watchdog: Watchdog, result: CheckResult):
        if self.in_cooldown(name):
            return

        for action in watchdog.on_trigger:
            await self.execute_action(action, result.context)

        self.cooldowns[name] = datetime.now()
```

### File Watching

Use `watchfiles` (Python) or `fswatch` (subprocess):

```python
async def watch_files(patterns: list[str], callback):
    """Watch files and call callback on changes."""
    async for changes in watchfiles.awatch(*patterns):
        for change_type, path in changes:
            await callback(change_type, path)
```

### Event Watching

Webhook receiver in portal:

```python
@app.post("/webhook/{watchdog_name}")
async def webhook_trigger(watchdog_name: str, payload: dict):
    """External events trigger watchdogs via webhook."""
    watchdog = manager.watchdogs.get(watchdog_name)
    if watchdog and watchdog.type == "event":
        await manager.handle_trigger(watchdog_name, watchdog, payload)
```

### Voice Integration

Speak alerts through existing TTS:

```python
async def execute_say(text: str, context: dict):
    """Speak an alert."""
    expanded = text.format(**context)
    await agentwire_say(text=expanded)
```

## CLI Commands

```bash
# Manage watchdogs
agentwire watchdog list               # List all watchdogs
agentwire watchdog add <name> <spec>  # Add from YAML
agentwire watchdog remove <name>      # Remove a watchdog
agentwire watchdog test <name>        # Test-run a watchdog

# Control
agentwire watchdog pause [name]       # Pause one or all
agentwire watchdog resume [name]      # Resume one or all
agentwire watchdog mute 30m           # Mute all alerts for 30 min

# Debugging
agentwire watchdog status             # Show current state
agentwire watchdog logs               # View trigger history
agentwire watchdog logs <name>        # View specific watchdog

# Quick create
agentwire watchdog watch "test failures" \
  --check "npm test" \
  --condition "exit != 0" \
  --say "Tests are failing"
```

## MCP Tools

```python
@mcp.tool()
def watchdog_list() -> str:
    """List active watchdogs with their status."""

@mcp.tool()
def watchdog_create(
    name: str,
    check: str,
    condition: str,
    on_trigger_say: str,
    interval: str = "5m"
) -> str:
    """Create a new polling watchdog."""

@mcp.tool()
def watchdog_pause(name: str | None = None) -> str:
    """Pause a watchdog (or all if name not specified)."""

@mcp.tool()
def watchdog_remove(name: str) -> str:
    """Remove a watchdog."""
```

## Configuration

```yaml
# ~/.agentwire/config.yaml
watchdogs:
  enabled: true

  # Default intervals
  defaults:
    interval: 5m
    cooldown: 15m
    debounce: 5s

  # Quiet hours (no alerts)
  quiet_hours:
    start: "22:00"
    end: "08:00"
    days: [saturday, sunday]

  # Global alert prefix
  alert_prefix: ""  # e.g., "Watchdog alert: "

  # Max concurrent checks
  max_concurrent: 5
```

## Example: Full Setup

```yaml
# ~/.agentwire/watchdogs.yaml
watchdogs:
  # Development
  build-broken:
    check: "npm run build 2>&1"
    interval: 5m
    condition: "exit != 0"
    on_trigger:
      say: "Build is broken"
    on_recovery:
      say: "Build is fixed"

  tests-failing:
    check: "npm test -- --passWithNoTests 2>&1"
    interval: 10m
    condition: "exit != 0"
    on_trigger:
      say: "Some tests are failing"
    cooldown: 30m

  # Git/GitHub
  upstream-changes:
    check: "git fetch && git rev-list HEAD..origin/main --count"
    interval: 15m
    condition: "> 0"
    on_trigger:
      say: "There are {value} new commits on main"

  pr-merged:
    event: github.pull_request.merged
    on_trigger:
      say: "Your PR was merged into {base_branch}"

  # Infrastructure
  dev-server-health:
    check: "curl -s -o /dev/null -w '%{http_code}' localhost:3000"
    interval: 1m
    condition: "!= 200"
    on_trigger:
      say: "Dev server is not responding"
    cooldown: 5m

  # Workers
  worker-timeout:
    check: "agentwire panes list --json"
    interval: 2m
    condition: |
      any(.panes[] |
        .index > 0 and
        .idle_seconds == null and
        .running_seconds > 600)
    on_trigger:
      say: "A worker has been running for over 10 minutes"
```

## Potential Challenges

1. **Resource usage**: Many polling watches could be expensive.
   - Solution: Stagger checks, use lightweight commands, batch similar checks

2. **Alert fatigue**: Too many alerts become noise.
   - Solution: Smart cooldowns, quiet hours, priority levels, consolidation ("3 things need attention")

3. **False positives**: Transient failures trigger alerts.
   - Solution: Debounce, require N consecutive failures, hysteresis

4. **Complexity creep**: Condition language becomes its own DSL.
   - Solution: Keep it simple, use external scripts for complex logic

5. **Security**: Running arbitrary commands periodically.
   - Solution: Sandbox checks, validate configs, audit logging

6. **State management**: Knowing when something "recovers" requires state.
   - Solution: Track last-known-good state per watchdog

## Success Criteria

1. Users learn about problems before they waste time on broken code
2. Reduced "wait, was CI passing?" moments
3. Workers get unstuck faster (timeout alerts)
4. External events (PR approval, mentions) get surfaced immediately
5. Users report feeling more "in the loop" without manually checking things

## Non-Goals

- Full monitoring/observability platform (use Datadog, etc.)
- Complex alerting rules (use PagerDuty, etc.)
- Metrics collection and graphing
- Log aggregation and search

This is lightweight, voice-first alerting for the developer's immediate context.
