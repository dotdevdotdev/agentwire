# Idea: Session Replay & Audit Trail

> Structured capture of agent actions for debugging, review, and learning

## Problem

When agents work, their actions are ephemeral:

- **Debugging**: "Why did the agent do that?" - scroll through terminal output
- **Review**: "What exactly changed?" - manually diff files
- **Learning**: "What worked well?" - no structured record
- **Compliance**: "Who changed what when?" - hope git history is enough

Terminal output captures text but not intent. Git captures file changes but not reasoning.

## Why This Matters

1. **Debugging** - When workers fail, understanding why requires piecing together fragments
2. **Trust** - Users want to verify agent actions, especially for sensitive operations
3. **Improvement** - Can't optimize what you can't measure
4. **Handoff** - Sharing context with colleagues requires explaining what happened
5. **Compliance** - Some environments need audit trails

## Proposed Solution: Action Log

Structured capture of agent actions, queryable and replayable.

### 1. What Gets Captured

```yaml
# ~/.agentwire/logs/sessions/{session}/{timestamp}.jsonl
{"ts": "2024-01-15T10:30:00", "type": "file_read", "path": "src/auth.ts", "lines": 150}
{"ts": "2024-01-15T10:30:05", "type": "file_write", "path": "src/auth.ts", "diff_lines": 12}
{"ts": "2024-01-15T10:30:10", "type": "command", "cmd": "npm test", "exit_code": 0}
{"ts": "2024-01-15T10:30:15", "type": "tool_call", "tool": "grep", "args": {"pattern": "login"}}
{"ts": "2024-01-15T10:30:20", "type": "decision", "summary": "Using JWT instead of sessions"}
```

### 2. Capture Levels

```yaml
# .agentwire.yml
logging:
  level: standard  # minimal | standard | verbose
  retention_days: 30
```

| Level | Captures |
|-------|----------|
| `minimal` | Commands, file writes, errors |
| `standard` | + file reads, tool calls, decisions |
| `verbose` | + full file contents, command output |

### 3. CLI Commands

```bash
# View recent actions
agentwire replay -s session              # Last 50 actions
agentwire replay -s session --since 1h   # Last hour
agentwire replay -s session --type file_write  # Only writes

# Export for sharing
agentwire replay -s session --export replay.json

# Search across sessions
agentwire replay --grep "auth" --since 24h

# Summarize session activity
agentwire replay -s session --summary
```

### 4. Replay Output

```
$ agentwire replay -s myproject --since 30m

Session: myproject (30 minutes of activity)

10:30:00  📖 READ   src/auth.ts (150 lines)
10:30:05  ✏️  WRITE  src/auth.ts (+12 lines)
10:30:10  ⚡ RUN    npm test → success
10:30:15  🔍 GREP   pattern="login" (5 matches)
10:30:20  💭 DECIDE "Using JWT instead of sessions"
10:31:00  📖 READ   package.json
10:31:05  ⚡ RUN    npm install jsonwebtoken → success
10:32:00  ✏️  WRITE  src/middleware/jwt.ts (new file, 45 lines)

Summary: 2 files read, 2 files written, 2 commands run
```

### 5. Integration Points

**Hook-based capture** (non-invasive):

```python
# In session send/output handlers
def log_action(session: str, action: dict):
    log_path = Path.home() / ".agentwire/logs/sessions" / session
    log_path.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    with open(log_path / f"{today}.jsonl", "a") as f:
        f.write(json.dumps(action) + "\n")
```

**MCP tool wrapper** (for detailed capture):

```python
# Wrap tool calls to capture inputs/outputs
original_tool = mcp.get_tool("grep")

@mcp.tool()
def grep_with_logging(*args, **kwargs):
    log_action(session, {"type": "tool_call", "tool": "grep", "args": kwargs})
    return original_tool(*args, **kwargs)
```

## Action Types

| Type | Description | Captured Data |
|------|-------------|---------------|
| `file_read` | Agent reads a file | path, line count |
| `file_write` | Agent writes/edits file | path, diff size, before/after hash |
| `command` | Shell command executed | cmd, exit code, duration |
| `tool_call` | MCP tool invoked | tool name, arguments |
| `decision` | Agent makes a choice | summary text |
| `error` | Something failed | error type, message |
| `spawn` | Worker spawned | pane, roles |
| `idle` | Session went idle | duration |

## MCP Tools

```python
@mcp.tool()
def replay_list(session: str, since: str = "1h", limit: int = 50) -> str:
    """List recent actions in a session.
    
    Args:
        session: Session name
        since: Time window (1h, 30m, 24h)
        limit: Max actions to return
    """

@mcp.tool()
def replay_summary(session: str, since: str = "24h") -> str:
    """Get activity summary for a session.
    
    Returns counts of reads, writes, commands, errors.
    """

@mcp.tool()
def replay_search(pattern: str, since: str = "24h") -> str:
    """Search actions across all sessions.
    
    Useful for finding when/where something happened.
    """
```

## Storage & Retention

```
~/.agentwire/logs/
├── sessions/
│   ├── myproject/
│   │   ├── 2024-01-15.jsonl
│   │   └── 2024-01-16.jsonl
│   └── api-server/
│       └── 2024-01-15.jsonl
└── index.sqlite  # Optional: for fast search
```

**Retention policy**:
- Default: 30 days
- Configurable per-project
- Auto-cleanup via `agentwire cleanup --logs`

**Size estimates**:
- ~1KB per action (standard level)
- ~100 actions per hour of active work
- ~2.4MB per day of heavy use
- ~72MB per month

## Privacy Considerations

- File contents only captured at `verbose` level
- Secrets in commands should be redacted
- Users control what's logged
- Local storage only (not sent anywhere)

## Example Use Cases

### Debugging a Failed Worker

```bash
$ agentwire replay -s myproject --pane 2 --type error

10:45:23  ❌ ERROR  command "npm test" failed (exit 1)
10:45:30  ❌ ERROR  file write failed: permission denied
10:46:00  ❌ ERROR  tool "grep" timeout after 30s

$ agentwire replay -s myproject --pane 2 --before "10:45:23" --limit 10
# Shows what happened leading up to the error
```

### Reviewing What Changed

```bash
$ agentwire replay -s myproject --type file_write --since 2h

10:30:05  ✏️  WRITE  src/auth.ts (+12 lines)
10:32:00  ✏️  WRITE  src/middleware/jwt.ts (new, 45 lines)
10:35:00  ✏️  WRITE  tests/auth.test.ts (+20 lines)

# Compare with git
$ git diff HEAD~1 --stat
```

### Sharing Context

```bash
$ agentwire replay -s myproject --since 4h --export handoff.json
$ agentwire replay --import handoff.json --summary

# Colleague can see exactly what you did
```

## Success Criteria

1. Actions logged automatically without agent changes
2. `replay` command shows clear, scannable history
3. Errors are easy to trace back to root cause
4. Storage stays reasonable (<100MB/month typical)
5. Search finds relevant actions quickly

## Non-Goals

- **Full terminal recording** - Use asciinema for that
- **Video replay** - Just structured actions
- **Remote sync** - Local logs only
- **Real-time streaming** - Query after the fact

## Implementation Phases

1. **Phase 1**: Basic logging (file_write, command, error)
2. **Phase 2**: CLI replay command with filtering
3. **Phase 3**: MCP tools for agents to query history
4. **Phase 4**: Search index for cross-session queries
