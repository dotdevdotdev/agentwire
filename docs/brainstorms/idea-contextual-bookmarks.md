# Contextual Bookmarks: Save and Share Discovery Moments

> Voice-activated bookmarks that capture context, code locations, and insights for quick reference and delegation.

## Problem

During a coding session, you discover valuable things:

- "The bug is in this function, line 47"
- "This pattern keeps causing issues"
- "The fix should use the existing UserService"
- "Don't touch this file - it breaks the build"

But this knowledge is ephemeral:

1. **Lost on context switch**: You step away, come back, forget where you were
2. **Hard to delegate**: "Check that thing I found earlier" doesn't work
3. **No structured capture**: Insights live in terminal scroll-back or your head
4. **Workers start blind**: Each worker re-discovers the same things

Session Replay captures *everything* but finding specific insights means searching through noise. Warmup provides *general* context but not session-specific discoveries.

## Why This Matters

1. **Interrupted workflows** - You get pulled away mid-debugging, lose the thread
2. **Delegation friction** - Explaining discoveries to workers wastes time
3. **Knowledge decay** - Yesterday's debugging session is a blur today
4. **Team handoffs** - Sharing context with colleagues is ad-hoc

Bookmarks capture the "aha moments" - the 5% of a session that's actually valuable.

## Proposed Solution: Contextual Bookmarks

### 1. Create Bookmarks via Voice

```
[User]: "Bookmark this"
[System]: "Saved bookmark. What should I call it?"
[User]: "Auth bug location"
[System]: "Bookmarked: Auth bug location"
```

Or inline naming:
```
[User]: "Bookmark: the validation is wrong here"
[System]: "Bookmarked: the validation is wrong here"
```

### 2. What Gets Captured

A bookmark snapshot includes:

```yaml
bookmark:
  name: "Auth bug location"
  created: "2024-01-15T10:30:00"
  session: "api-server"
  pane: 0

  # Context at bookmark time
  context:
    working_file: "src/auth/validate.ts"  # Last file being discussed
    line_range: [45, 52]                   # If specific lines mentioned
    recent_transcript: "...the validation fails because..."  # Last ~200 chars
    recent_files_read:
      - "src/auth/validate.ts"
      - "src/auth/types.ts"

  # Optional user annotation
  note: "Check the regex on line 47 - doesn't handle Unicode"

  # Tags for organization
  tags: ["bug", "auth", "urgent"]
```

### 3. Reference Bookmarks

**List bookmarks:**
```
[User]: "What bookmarks do I have?"
[System]: "Three bookmarks in this session: Auth bug location,
          UserService pattern, and Don't touch config."
```

**Get bookmark details:**
```
[User]: "Show me auth bug location"
[System]: "Auth bug location, created 10 minutes ago.
          File: validate.ts lines 45-52.
          Note: Check the regex on line 47."
```

**Navigate to bookmark:**
```
[User]: "Go to auth bug location"
[System]: *Opens file at bookmarked location, reads relevant lines*
```

### 4. Share with Workers

The key use case - passing discoveries to workers:

```
[User]: "Helper, look at the auth bug location bookmark and fix it"
[System]: *Spawns worker with bookmark context injected*
```

Worker receives:
```
## Bookmark Context: Auth bug location

File: src/auth/validate.ts (lines 45-52)
```typescript
45: function validateEmail(email: string): boolean {
46:   // BUG: This regex doesn't handle Unicode
47:   const pattern = /^[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-z]+$/;
48:   return pattern.test(email);
49: }
```

Note: Check the regex on line 47 - doesn't handle Unicode

Recent context: "...the validation fails because emails with
non-ASCII characters return false even though they're valid..."

---

Your task: Fix the auth bug described above.
```

### 5. Auto-Bookmarks

System creates bookmarks automatically for significant events:

```yaml
auto_bookmarks:
  - type: error_found
    trigger: "Agent identifies error root cause"

  - type: decision_made
    trigger: "Agent commits to an approach"

  - type: file_created
    trigger: "New file created"

  - type: test_fixed
    trigger: "Failing test now passes"
```

These appear in bookmark list with `[auto]` tag:
```
[User]: "Show bookmarks"
[System]: "Auth bug location, [auto] Error in config.ts,
          [auto] Created jwt-utils.ts"
```

### 6. Bookmark Persistence

Bookmarks persist across session restarts:

```
~/.agentwire/bookmarks/
├── api-server/
│   ├── auth-bug-location.yaml
│   └── userservice-pattern.yaml
└── frontend/
    └── css-grid-issue.yaml
```

Or in project directory:
```
.agentwire/bookmarks/
├── auth-bug-location.yaml
└── userservice-pattern.yaml
```

## CLI Commands

```bash
# List bookmarks
agentwire bookmarks list [-s session]
agentwire bookmarks list --all  # All sessions

# Show bookmark details
agentwire bookmarks show "auth bug location"

# Create bookmark manually
agentwire bookmarks create "name" --file src/auth.ts --lines 45-52 --note "..."

# Delete bookmark
agentwire bookmarks delete "auth bug location"

# Export bookmarks (for sharing)
agentwire bookmarks export > session-bookmarks.yaml

# Import bookmarks
agentwire bookmarks import session-bookmarks.yaml
```

## MCP Tools

```python
@mcp.tool()
def bookmark_create(
    name: str,
    file: str | None = None,
    lines: str | None = None,  # "45-52"
    note: str | None = None,
    tags: list[str] | None = None
) -> str:
    """Create a contextual bookmark.

    Captures current context (recent files, transcript) plus
    optional file/line/note specifics.
    """

@mcp.tool()
def bookmark_list(session: str | None = None) -> str:
    """List bookmarks in session.

    Returns names, creation times, and brief descriptions.
    """

@mcp.tool()
def bookmark_get(name: str) -> str:
    """Get full bookmark details.

    Returns file, lines, note, context, and recent transcript.
    """

@mcp.tool()
def bookmark_inject(name: str) -> str:
    """Get bookmark content formatted for injection into prompts.

    Use this when delegating to workers - returns markdown block
    with all relevant context.
    """
```

## Integration with Worker Spawn

```python
# In pane_spawn, support bookmark injection
@mcp.tool()
def pane_spawn(
    roles: str | None = None,
    bookmarks: list[str] | None = None,  # Bookmarks to inject
    ...
) -> str:
    """Spawn worker with optional bookmark context."""
```

Or via CLI:
```bash
agentwire spawn --roles glm-worker --bookmark "auth bug location"
```

## Voice Grammar

| Phrase | Action |
|--------|--------|
| "Bookmark this" | Create bookmark, prompt for name |
| "Bookmark: {name}" | Create bookmark with inline name |
| "Bookmark {name}: {note}" | Create with name and note |
| "What bookmarks" / "Show bookmarks" | List all |
| "Show {name}" | Get bookmark details |
| "Go to {name}" | Navigate to bookmarked location |
| "Delete bookmark {name}" | Remove bookmark |
| "Clear bookmarks" | Remove all (with confirmation) |

## Context Capture Strategies

### Detecting "Current File"

When bookmark is created, determine working file from:

1. **Explicit mention**: "This file" in recent transcript
2. **Last read**: Most recently `Read` tool target
3. **Last edit**: Most recently `Edit` tool target
4. **Discussion topic**: File path mentioned in last few exchanges

### Detecting "Current Lines"

When bookmark includes line numbers:

1. **Explicit mention**: "Line 47" in transcript
2. **Recent read range**: Lines returned by last Read call
3. **Recent edit target**: Lines in last Edit `old_string`
4. **Error location**: Line numbers in stack traces

### Transcript Window

Capture recent transcript for context:

- Last 200-500 characters of user/agent exchange
- Truncate at sentence boundaries
- Strip code blocks (already captured in file context)

## Example Workflows

### Debugging Session

```
[10:00] User investigates bug
[10:05] [User]: "Aha, found it. Bookmark: the bug is in validateEmail"
[10:06] System saves bookmark with validate.ts:47 context

[10:15] User needs to delegate fix
[User]: "Helper, fix the bookmark 'bug is in validateEmail'"
[System]: Spawns worker with full context injected

Worker receives:
- File content around line 47
- User's discovery notes
- Recent debugging transcript
```

### Knowledge Handoff

```
# End of day
[User]: "Show bookmarks"
[System]: "5 bookmarks: API rate limit fix, CSS grid workaround,
          Test mock pattern, Env var location, Deploy command"

[User]: "Export bookmarks"
[System]: Saves to session-bookmarks.yaml

# Next day or different machine
[User]: "Import yesterday's bookmarks"
[System]: "Imported 5 bookmarks"
[User]: "What was the rate limit fix?"
[System]: "API rate limit fix: Add retry logic to fetch wrapper..."
```

### Team Collaboration

```
# Developer A finds issue
agentwire bookmarks create "Redis timeout root cause" \
  --file src/cache.ts --lines 120-135 \
  --note "Connection pool exhausted under load, need to increase maxConnections"

# Developer B picks up
agentwire bookmarks show "Redis timeout root cause"
# Gets full context, proceeds with fix
```

## Potential Challenges

1. **Bookmark name collisions**: Same name in different sessions. Solution: Namespace by session, allow explicit session prefix `api-server/auth-bug`.

2. **Stale bookmarks**: Code changes, bookmark line numbers drift. Solution: Store content hash, warn if file changed since bookmark, offer to update.

3. **Too many bookmarks**: Users create tons, hard to find relevant ones. Solution: Auto-archive after 7 days, show recent first, support tags/search.

4. **Context too large**: Bookmark with 500 lines of context. Solution: Configurable max context size, summarization for large ranges.

5. **Voice name recognition**: "Auth bug location" might STT as "off bug location". Solution: Fuzzy matching, confirmation for ambiguous matches.

## Bookmark Schema

```yaml
# Full bookmark schema
name: string              # User-provided or auto-generated
session: string           # Session where created
created_at: datetime
updated_at: datetime
expires_at: datetime | null  # Auto-cleanup after this

# Location
file: string | null       # Absolute path
line_start: int | null
line_end: int | null
file_content_hash: string | null  # Detect drift

# Context
transcript_snippet: string | null  # Recent conversation
files_in_context: list[string]     # Recently accessed files
note: string | null                # User annotation

# Organization
tags: list[string]
auto_generated: bool      # System-created vs user-created
source: string | null     # What triggered auto-creation

# Content cache (for quick access)
cached_content: string | null  # File content at bookmark time
```

## Success Criteria

1. Users can create bookmarks in <3 seconds via voice
2. Workers spawned with bookmarks start 2+ turns faster
3. Bookmarks persist across session restarts
4. 80% of manually-created bookmarks used within same session
5. Users report "less re-explaining" when delegating

## Non-Goals

- **Full code search** - Bookmarks are for specific known locations
- **Version control** - Git handles code history
- **Documentation generation** - Bookmarks are working notes, not docs
- **Cross-project bookmarks** - Keep it session/project scoped

## Rollout Phases

1. **Phase 1**: Manual bookmarks via CLI/MCP (name, file, lines, note)
2. **Phase 2**: Voice creation ("bookmark this")
3. **Phase 3**: Auto-bookmarks for key events
4. **Phase 4**: Worker spawn integration
5. **Phase 5**: Import/export for sharing
