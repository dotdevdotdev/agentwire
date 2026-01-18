# Mission: Conversation History

> Surface Claude Code session history through CLI and Portal for easy resume and browsing.

**Branch:** `mission/conversation-history` (created on execution)

**Depends on:** `projects-model` (must be completed first)

## Context

Claude Code persists all conversations with rich metadata. Two key data sources:

1. **`~/.claude/history.jsonl`** - Index of ALL user messages across all projects/sessions
2. **`~/.claude/projects/{encoded-path}/*.jsonl`** - Full conversation files with summaries

Claude CLI supports:
- `--resume <uuid>` - Resume existing conversation
- `--session-id <uuid>` - Start with specific session ID
- `--continue` - Continue most recent in current directory
- `--fork-session` - Fork instead of continue when resuming

**Key design decisions:**
- CLI subcommand is `history` (not `conversations`) to distinguish from tmux sessions
- "Resume" always forks under the hood (preserves original, avoids conflicts)
- History is always scoped to a project (from projects-model mission)
- No delete command - users manage ~/.claude directly if needed

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required.

## Wave 2: CLI Foundation

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | **History utility module** - Create utility to read conversation data. Filter by project path. Supports local and remote machines (SSH for remote `~/.claude/`). Primary source: `~/.claude/history.jsonl` (indexed user messages with sessionId, project, timestamp). Secondary: scan session files for summaries. Group by sessionId, extract first/last message, message count. | `agentwire/history.py` |
| 2.2 | **CLI list command** - Add `agentwire history list`. Requires being in a tracked project dir (has `.agentwire.yml`) OR `--project <path>`. Options: `--machine <id>` (default local), `--limit N` (default 20), `--json`. Display: short session ID, last summary, relative timestamp, message count. | `agentwire/__main__.py` |
| 2.3 | **CLI show command** - Add `agentwire history show <session-id>`. Display: full session ID, all summaries (timeline), first user message preview, start/end timestamps, git branch if available, total messages. | `agentwire/__main__.py` |

## Wave 3: CLI Resume Integration

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | **Resume command** - Add `agentwire history resume <session-id>`. **Always forks** using `claude --resume <uuid> --fork-session`. Spawns new tmux session on appropriate machine. Options: `--name <tmux-name>` for session name, `--machine <id>` (required for remote projects). Respects project's `.agentwire.yml` for type/roles. | `agentwire/__main__.py` |

## Wave 4: Portal API

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | **List history endpoint** - `GET /api/projects/<path>/history`. Query: `machine` (required), `limit` (default 20). Returns array of `{sessionId, firstMessage, lastSummary, timestamp, messageCount}`. Uses history utility via CLI. Project path URL-encoded. | `agentwire/server.py` |
| 4.2 | **Get history detail endpoint** - `GET /api/history/<session-id>`. Query: `machine` (required). Returns full metadata: all summaries, message previews, timestamps, git branch. | `agentwire/server.py` |
| 4.3 | **Resume endpoint** - `POST /api/history/<session-id>/resume`. Body: `{name?: string, projectPath: string, machine: string}`. Calls CLI `history resume` internally. Returns new tmux session name. | `agentwire/server.py` |

## Wave 5: Portal UI

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | **History tab in project detail** - Add "History" tab to project detail panel (from projects-model mission). Shows conversation list for that project. Columns: ID (short), Summary, Time (relative), Messages. | `agentwire/static/js/windows/projects-window.js` |
| 5.2 | **History detail modal** - When conversation selected, show modal with: full ID, all summaries as timeline, first message preview, timestamps. "Resume" button that creates new forked session. | `agentwire/static/js/windows/projects-window.js` |
| 5.3 | **Resume flow** - "Resume" button spawns session, then opens/focuses the new session in Sessions window. Shows toast notification on success. | `agentwire/static/js/windows/projects-window.js` |

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

### Remote Machine Support
History lives in `~/.claude/` on the machine where Claude Code runs:
- **Local**: Read files directly from `~/.claude/`
- **Remote**: SSH to machine, read `~/.claude/history.jsonl` and session files

```python
def get_history(project_path: str, machine: str = 'local') -> list[dict]:
    if machine == 'local':
        return read_local_history(project_path)
    else:
        # SSH to remote, read ~/.claude/history.jsonl
        # Filter by project_path, return results
        return read_remote_history(machine, project_path)
```

This is a key differentiator - AgentWire lets you browse conversation history across all your machines from one Portal.

### Efficient Implementation
1. Read `history.jsonl` line-by-line, filter by project path
2. Group by sessionId, get first/last message, count
3. For summaries, grep session files for `"type":"summary"` lines only
4. Cache results with file mtime for invalidation

### Resume Flow (Always Forks)
```bash
# User clicks "Resume" in portal for session abc123 on remote machine "workstation"
POST /api/history/abc123/resume {name: "project-resumed", projectPath: "/path/to/project", machine: "workstation"}

# Server calls CLI
agentwire history resume abc123 --name project-resumed --project /path/to/project --machine workstation

# CLI spawns tmux on remote machine with forked session
ssh workstation "tmux new-session -d -s project-resumed -c /path/to/project"
ssh workstation "tmux send-keys -t project-resumed 'claude --resume abc123 --fork-session' Enter"
```

### Why Always Fork?
1. **Preserves original** - Can resume from same point multiple times
2. **Avoids conflicts** - No issues if another device has the session open
3. **Simpler UX** - "Resume" just works, no edge cases
4. **Audit trail** - Original conversations remain as immutable references

## Completion Criteria

- [ ] `agentwire history list` shows conversations for current project (local and remote)
- [ ] `agentwire history show <id>` displays full conversation metadata
- [ ] `agentwire history resume <id>` spawns forked session on appropriate machine
- [ ] Portal project detail has History tab showing conversations from that machine
- [ ] Portal can resume conversations into new sessions
- [ ] Original conversations preserved after resume (fork behavior)
- [ ] Remote machine history accessible via SSH

## References

- [Claude Code Conversation History](https://kentgigger.com/posts/claude-code-conversation-history)
- [Resume Claude Code Sessions](https://mehmetbaykar.com/posts/resume-claude-code-sessions-after-restart/)
- [Claude Code Session Management](https://stevekinney.com/courses/ai-development/claude-code-session-management)
