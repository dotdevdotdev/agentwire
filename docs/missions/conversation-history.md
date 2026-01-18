# Mission: Conversation History

> Surface Claude Code session history through CLI and Portal for easy resume and browsing.

**Branch:** `mission/conversation-history` (created on execution)

## Context

Claude Code persists all conversations with rich metadata. Two key data sources:

1. **`~/.claude/history.jsonl`** - Index of ALL user messages across all projects/sessions
2. **`~/.claude/projects/{encoded-path}/*.jsonl`** - Full conversation files with summaries

Claude CLI supports:
- `--resume <uuid>` - Resume existing conversation
- `--session-id <uuid>` - Start with specific session ID
- `--continue` - Continue most recent in current directory
- `--fork-session` - Fork instead of continue when resuming

We'll expose this through CLI commands and Portal UI for both developers and chatbot users.

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required.

## Wave 2: CLI Foundation

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | **Conversations utility module** - Create utility to read conversation data. Primary source: `~/.claude/history.jsonl` (indexed user messages with sessionId, project, timestamp). Secondary: scan session files for summaries. Group by sessionId, extract first/last message, message count, project path. | `agentwire/conversations.py` |
| 2.2 | **CLI list command** - Add `agentwire conversations list`. Options: `--project <path>` filter, `--limit N` (default 20), `--json`. Display: short session ID, last summary (from session file), relative timestamp, project name, message count. | `agentwire/__main__.py` |
| 2.3 | **CLI show command** - Add `agentwire conversations show <session-id>`. Display: full session ID, all summaries (timeline), first user message preview, start/end timestamps, project path, git branch, total messages. | `agentwire/__main__.py` |

## Wave 3: CLI Resume Integration

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | **Resume command** - Add `agentwire conversations resume <session-id>`. Spawns tmux session with `claude --resume <uuid>`. Options: `--name <tmux-name>` for session name, `--fork` to use `--fork-session` flag. Respects project's `.agentwire.yml` for type/roles. | `agentwire/__main__.py` |
| 3.2 | **Delete command** - Add `agentwire conversations delete <session-id>`. Removes from history.jsonl and deletes session .jsonl file. Requires `--force` or interactive confirm. | `agentwire/__main__.py` |

## Wave 4: Portal API

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | **List conversations endpoint** - `GET /api/conversations`. Query: `project`, `limit` (default 20). Returns array of `{sessionId, project, firstMessage, lastSummary, timestamp, messageCount}`. Uses conversations utility. | `agentwire/server.py` |
| 4.2 | **Get conversation endpoint** - `GET /api/conversations/<session-id>`. Returns full metadata: all summaries, message previews, timestamps, project, git branch. | `agentwire/server.py` |
| 4.3 | **Resume endpoint** - `POST /api/conversations/<session-id>/resume`. Body: `{name?: string, fork?: boolean}`. Calls CLI `conversations resume` internally. Returns new tmux session name. | `agentwire/server.py` |

## Wave 5: Portal UI

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | **Conversations window** - New ListWindow for conversations. Columns: ID (short), Summary, Time (relative), Project. Click row for details. Refresh button. | `agentwire/static/js/windows/conversations-window.js` |
| 5.2 | **Detail panel** - When conversation selected, show: full ID, all summaries as timeline, first message preview, timestamps. "Resume" and "Resume (Fork)" buttons. | `agentwire/static/js/windows/conversations-window.js` |
| 5.3 | **Menu integration** - Add "History" menu item (between Config and Chat). Opens conversations window. Update session count area to show conversation count on hover/click. | `agentwire/templates/desktop.html`, `agentwire/static/js/desktop.js` |

## Technical Notes

### Data Sources

**Primary: `~/.claude/history.jsonl`** (fast index)
```json
{
  "display": "user message text",
  "timestamp": 1762820357320,
  "project": "/Users/dotdev/projects/anna",
  "sessionId": "uuid"
}
```

**Secondary: `~/.claude/projects/{path}/*.jsonl`** (full data)
```json
{"type": "user", "sessionId": "uuid", "timestamp": "ISO", "message": {...}, "cwd": "...", "gitBranch": "..."}
{"type": "assistant", "message": {...}}
{"type": "summary", "summary": "Desktop UI terminal fix and menu behavior polish"}
```

### Path Encoding
Project path `/Users/dotdev/projects/anna` → directory name `-Users-dotdev-projects-anna`

### Efficient Implementation
1. Read `history.jsonl` line-by-line, group by sessionId
2. For summaries, grep session files for `"type":"summary"` lines only
3. Cache results with file mtime for invalidation

### Resume Flow
```bash
# User clicks "Resume" in portal
POST /api/conversations/abc123/resume {name: "anna-resumed"}

# Server calls CLI
agentwire conversations resume abc123 --name anna-resumed

# CLI spawns tmux
tmux new-session -d -s anna-resumed -c /path/to/project
tmux send-keys "claude --resume abc123" Enter
```

## Completion Criteria

- [ ] `agentwire conversations list` shows recent sessions with summaries
- [ ] `agentwire conversations show <id>` displays full session metadata
- [ ] `agentwire conversations resume <id>` spawns tmux with resumed session
- [ ] `agentwire conversations delete <id>` removes conversation data
- [ ] Portal "History" window shows browsable conversation list
- [ ] Portal can resume/fork conversations into new sessions
- [ ] Works for both agentwire project sessions and chatbot sessions

## References

- [Claude Code Conversation History](https://kentgigger.com/posts/claude-code-conversation-history)
- [Resume Claude Code Sessions](https://mehmetbaykar.com/posts/resume-claude-code-sessions-after-restart/)
- [Claude Code Session Management](https://stevekinney.com/courses/ai-development/claude-code-session-management)
