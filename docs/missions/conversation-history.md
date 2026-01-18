# Mission: Conversation History

> Surface Claude Code session history through CLI and Portal for easy resume and browsing.

**Branch:** `mission/conversation-history` (created on execution)

## Context

Claude Code already persists sessions as `.jsonl` files in `~/.claude/projects/{encoded-path}/`. Each session contains timestamps, summaries, and full conversation history. This data is currently only accessible through Claude's interactive `--resume` picker.

We can expose this data through:
1. CLI commands for listing/managing conversations
2. Portal API for fetching conversation metadata
3. Portal UI for browsing and resuming past conversations

This benefits both developers (CLI power users) and chatbot users (Portal).

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required.

## Wave 2: CLI Foundation

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | **Session scanner utility** - Create a utility module to scan `~/.claude/projects/` directories, parse `.jsonl` files, extract metadata (session ID, first/last timestamp, summaries, cwd, message count). Handle large files efficiently (stream parsing, don't load entire file). | `agentwire/conversations.py` |
| 2.2 | **CLI list command** - Add `agentwire conversations list` command. Options: `--project <path>` to filter by project, `--limit N` for recent N, `--json` for JSON output. Display: session ID (short), last summary, timestamp, message count. | `agentwire/__main__.py` |
| 2.3 | **CLI show command** - Add `agentwire conversations show <session-id>` to display full metadata for a session. Include all summaries, first user message preview, timestamps, cwd, git branch. | `agentwire/__main__.py` |

## Wave 3: CLI Resume Integration

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | **Resume via agentwire** - Add `agentwire conversations resume <session-id>` that spawns a tmux session with `claude --resume <uuid>`. Respect project's `.agentwire.yml` for type/roles. Option: `--session-name <name>` to specify tmux session name. | `agentwire/__main__.py` |
| 3.2 | **Delete command** - Add `agentwire conversations delete <session-id>` to remove a conversation. Confirm before delete unless `--force`. | `agentwire/__main__.py` |

## Wave 4: Portal API

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | **Conversations API endpoint** - Add `GET /api/conversations` endpoint. Query params: `project` (filter by project path), `limit` (default 20). Return array of conversation metadata objects. | `agentwire/server.py` |
| 4.2 | **Single conversation endpoint** - Add `GET /api/conversations/<session-id>` for full conversation details including all summaries and message previews. | `agentwire/server.py` |
| 4.3 | **Resume conversation endpoint** - Add `POST /api/conversations/<session-id>/resume` to spawn a tmux session resuming that conversation. Body: `{session_name?: string}`. Uses CLI internally. | `agentwire/server.py` |

## Wave 5: Portal UI

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | **Conversations window** - Create new "Conversations" window (like Sessions/Machines). List conversations with: short ID, summary, relative timestamp ("2 hours ago"), project name. Click to see details. | `agentwire/static/js/windows/conversations-window.js`, `agentwire/static/css/desktop.css` |
| 5.2 | **Conversation detail view** - Show full conversation metadata in the window. Display all summaries as a timeline. "Resume" button to start a new session continuing this conversation. | `agentwire/static/js/windows/conversations-window.js` |
| 5.3 | **Menu integration** - Add "Conversations" menu item to nav bar. Wire up to open conversations window. | `agentwire/templates/desktop.html`, `agentwire/static/js/desktop.js` |

## Technical Notes

### Session File Location
Sessions stored in `~/.claude/projects/{encoded-path}/` where path is encoded as `-Users-dotdev-projects-foo` for `/Users/dotdev/projects/foo`.

### JSONL Structure
```jsonl
{"type": "user", "sessionId": "uuid", "timestamp": "ISO", "message": {...}, ...}
{"type": "assistant", "message": {...}, ...}
{"type": "summary", "summary": "text", ...}
```

### Efficient Parsing
For listing, only need:
- First line with `type: "user"` for session start time
- Last line for end time
- All `type: "summary"` lines for summaries
- File stats for modification time

Use streaming/line-by-line parsing, not full JSON load.

### Path Encoding
To find sessions for a project path:
1. Take absolute path: `/Users/dotdev/projects/anna`
2. Replace `/` with `-`: `-Users-dotdev-projects-anna`
3. Look in `~/.claude/projects/-Users-dotdev-projects-anna/`

## Completion Criteria

- [ ] `agentwire conversations list` shows recent sessions with summaries
- [ ] `agentwire conversations show <id>` displays full session metadata
- [ ] `agentwire conversations resume <id>` spawns tmux with resumed session
- [ ] Portal shows Conversations window with browsable history
- [ ] Portal can resume a conversation into a new session
- [ ] Works for both agentwire project sessions and chatbot sessions
