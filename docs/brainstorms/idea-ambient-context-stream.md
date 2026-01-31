# Ambient Context Stream

> Workers passively receive orchestrator context, reducing explicit coordination overhead.

## Problem

Current worker delegation requires detailed, explicit task specifications. Orchestrators must front-load all relevant context because workers start with zero awareness of:
- What problem the user originally described
- What the orchestrator already investigated
- What approaches were considered and rejected
- The broader goal beyond the immediate task

This leads to:
- **Verbose task descriptions** - Orchestrators spend tokens explaining context workers could infer
- **Context loss** - Workers often miss nuances that were obvious in the original conversation
- **Re-investigation** - Workers explore paths the orchestrator already ruled out
- **Brittle delegation** - Small omissions in task specs cause workers to go off-track

## Proposed Solution

**Ambient Context Stream**: A read-only feed of orchestrator activity that workers can reference without explicit coordination.

### Core Mechanism

When a worker spawns, it receives access to a context stream containing:

```yaml
# .agentwire/context/session-{id}.jsonl (append-only log)
{"type": "user_message", "content": "The auth is broken after the refactor", "ts": "..."}
{"type": "file_read", "path": "src/auth/jwt.ts", "ts": "..."}
{"type": "agent_observation", "content": "Token expiry not being checked", "ts": "..."}
{"type": "decision", "content": "Will fix in middleware, not client", "ts": "..."}
{"type": "delegation", "pane": 1, "task": "Fix JWT middleware", "ts": "..."}
```

Workers can query this stream:
- **On spawn**: Auto-summarize recent context (last 5 minutes)
- **On demand**: "What did the orchestrator learn about auth?"
- **Continuous**: Background awareness of orchestrator progress

### Integration Points

1. **Claude Code hook** - Capture significant events (file reads, decisions, errors)
2. **OpenCode plugin** - Same event capture for OpenCode sessions
3. **Stream writer** - Append events to session's context file
4. **Stream reader** - Workers read/query via MCP tool or CLI

### New MCP Tools

```python
# Worker reads orchestrator context
agentwire_context_read(
    session=None,  # Defaults to parent session
    since="5m",    # Time window
    types=["decision", "file_read"]  # Filter by event type
)

# Orchestrator annotates context (explicit markers)
agentwire_context_annotate(
    content="Confirmed: the bug is in token refresh, not initial auth",
    type="decision"
)
```

### Worker Prompt Enhancement

When spawning workers, automatically prepend context summary:

```
[AMBIENT CONTEXT from orchestrator - last 5 min]
- User reported: "auth broken after refactor"
- Files examined: src/auth/jwt.ts, src/middleware/auth.ts
- Key finding: Token expiry check missing in middleware
- Rejected approach: Client-side fix (breaks SSR)

[YOUR TASK]
Fix JWT middleware to check token expiry...
```

## Implementation Considerations

### Event Selection
Not all activity is useful context. Capture:
- User messages (the actual request)
- File reads (what was investigated)
- Explicit decisions/observations (agent reasoning)
- Errors encountered (what didn't work)
- Delegations (coordination context)

Skip:
- Tool call metadata
- Formatting/display operations
- Repeated reads of same file

### Storage & Cleanup
- One JSONL file per session in `.agentwire/context/`
- Rotate files when session ends or exceeds 1MB
- Workers only read, never write to orchestrator's stream
- Auto-cleanup after 24 hours

### Privacy Boundary
Context stays within the session hierarchy:
- Workers can read their orchestrator's stream
- Orchestrators cannot read worker streams (workers report via summaries)
- Cross-session context requires explicit sharing

### Performance
- Append-only writes (fast)
- Time-windowed reads (bounded)
- Optional summarization via small model for long streams

## Potential Challenges

1. **Signal vs Noise** - Too much context overwhelms workers. Need smart filtering and summarization.

2. **Stale Context** - Fast-moving sessions may have outdated context by the time workers read it. Timestamp-based relevance scoring could help.

3. **Hook Complexity** - Capturing "decisions" vs "observations" requires understanding agent intent. May need explicit annotation for high-value context.

4. **Token Cost** - Auto-prepending context to every worker adds tokens. Make it opt-in via role configuration.

5. **Event Schema Evolution** - Context format will need versioning as we learn what's useful.

## Success Metrics

- Reduced task description length (fewer explicit context tokens)
- Fewer worker "re-investigations" of already-explored paths
- Higher first-attempt success rate for delegated tasks
- Qualitative: Workers feel "aware" of the broader picture
