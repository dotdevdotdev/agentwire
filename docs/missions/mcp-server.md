> Living document. Update this, don't create new versions.

# Mission: AgentWire MCP Server

Expose AgentWire capabilities as an MCP server so external agents (MoltBot, Claude Desktop, etc.) can manage tmux sessions, remote machines, and voice features.

## Status: Complete

## Value Proposition

Instead of competing with all-in-one agents like MoltBot, AgentWire becomes infrastructure they plug into:
- "Add AgentWire to get terminal sessions your agent can actually control"
- "Voice interface for your automations"
- "Multi-machine orchestration from any MCP client"

## Technical Approach

### Use Official MCP Python SDK

The `mcp` package provides `FastMCP` for clean, decorator-based tool definitions:

```bash
uv add "mcp[cli]"
```

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agentwire")

@mcp.tool()
async def sessions_list() -> str:
    """List all active AgentWire sessions."""
    # Implementation
```

**Why FastMCP over rolling our own:**
- Auto-generates tool schemas from type hints + docstrings
- Handles JSON-RPC protocol correctly
- Battle-tested by Anthropic
- Future-proof as MCP evolves

### Config Resolution

Portal URL discovered in order:
1. `AGENTWIRE_PORTAL_URL` env var (for MCP config overrides)
2. `~/.agentwire/config.yaml` → `portal.url`
3. Default: `https://localhost:8765`

### File Structure

```
agentwire/
├── __main__.py          # Add `mcp` subcommand
└── mcp_server.py        # MCP server implementation
```

New CLI command:
```bash
agentwire mcp  # Starts MCP server on stdio
```

## Tool Inventory

### Session Management (Core)

| Tool | Description | Parameters |
|------|-------------|------------|
| `sessions_list` | List all active sessions | - |
| `session_create` | Create new session | `name`, `project_dir?`, `roles[]?`, `type?` |
| `session_send` | Send prompt to session | `session`, `message` |
| `session_output` | Capture session output | `session`, `lines?` |
| `session_info` | Get session metadata | `session` |
| `session_kill` | Terminate session | `session` |

### Pane Management (Workers)

| Tool | Description | Parameters |
|------|-------------|------------|
| `pane_spawn` | Spawn worker pane | `session?`, `roles[]?`, `type?` |
| `pane_send` | Send to specific pane | `pane`, `message`, `session?` |
| `pane_output` | Capture pane output | `pane`, `session?`, `lines?` |
| `pane_kill` | Kill worker pane | `pane`, `session?` |
| `panes_list` | List panes in session | `session?` |

### Machine Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `machines_list` | List configured machines | - |
| `machine_add` | Add remote machine | `id`, `host`, `user`, `port?` |
| `machine_remove` | Remove machine | `id` |

### Voice (TTS/STT)

| Tool | Description | Parameters |
|------|-------------|------------|
| `say` | Speak text via TTS | `text`, `session?`, `voice?` |
| `alert` | Send text notification | `text`, `to?` |
| `listen_start` | Start voice recording | - |
| `listen_stop` | Stop recording, return transcript | - |
| `voices_list` | List available TTS voices | - |

### Projects & Roles

| Tool | Description | Parameters |
|------|-------------|------------|
| `projects_list` | Discover available projects | - |
| `roles_list` | List available roles | - |
| `role_show` | Get role details | `name` |

### Portal Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `portal_status` | Check portal health | - |
| `tts_status` | Check TTS server status | - |
| `stt_status` | Check STT server status | - |

## Implementation Strategy

### Implementation Complete

All 25 tools implemented in a single pass:

**Session Management (6 tools):**
- [x] `sessions_list`, `session_create`, `session_send`, `session_output`, `session_info`, `session_kill`

**Pane Management (5 tools):**
- [x] `pane_spawn`, `pane_send`, `pane_output`, `pane_kill`, `panes_list`

**Machine Management (3 tools):**
- [x] `machines_list`, `machine_add`, `machine_remove`

**Voice (5 tools):**
- [x] `say`, `alert`, `listen_start`, `listen_stop`, `voices_list`

**Projects & Roles (3 tools):**
- [x] `projects_list`, `roles_list`, `role_show`

**Status (3 tools):**
- [x] `portal_status`, `tts_status`, `stt_status`

**CLI Command:**
- [x] `agentwire mcp` - starts MCP server on stdio

## Implementation Notes

### Calling CLI vs Portal API

Tools should call CLI commands via subprocess, not duplicate logic:

```python
import subprocess
import json

async def run_agentwire_cmd(args: list[str]) -> dict:
    """Run agentwire CLI command and parse JSON output."""
    result = subprocess.run(
        ["agentwire"] + args + ["--json"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(result.stderr)
    return json.loads(result.stdout)

@mcp.tool()
async def sessions_list() -> str:
    """List all active AgentWire sessions."""
    data = await run_agentwire_cmd(["list"])
    # Format for LLM consumption
    return format_sessions(data)
```

### Logging

MCP STDIO servers must NOT write to stdout (corrupts JSON-RPC). Use stderr:

```python
import logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
```

### Error Handling

Return human-readable errors, not stack traces:

```python
@mcp.tool()
async def session_send(session: str, message: str) -> str:
    """Send a message to a session."""
    try:
        await run_agentwire_cmd(["send", "-s", session, message])
        return f"Message sent to {session}"
    except Exception as e:
        return f"Failed to send message: {e}"
```

### Session Targeting

Support multiple session formats:
- `name` - local session by name
- `project/branch` - worktree session
- `name@machine` - remote session

## MCP Client Configuration

### Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "agentwire": {
      "command": "agentwire",
      "args": ["mcp"],
      "env": {
        "AGENTWIRE_PORTAL_URL": "https://localhost:8765"
      }
    }
  }
}
```

### MoltBot / Other Agents

Same pattern - they configure the MCP server in their settings. Env var allows pointing to remote AgentWire instances.

## Testing Strategy

1. **Unit tests** - Mock subprocess calls, test tool logic
2. **Integration tests** - Real CLI calls against test sessions
3. **Manual testing** - Connect from Claude Desktop, verify tools work

## Dependencies

- `mcp[cli]` - Official MCP Python SDK
- Existing `agentwire` CLI (source of truth)

## Open Questions

- [ ] Should we support MCP resources (read-only data) in addition to tools?
- [ ] Do we need auth for remote portal connections?
- [ ] Should there be rate limiting?

## References

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Build an MCP Server](https://modelcontextprotocol.io/docs/develop/build-server)
- [FastMCP Decorator Pattern](https://modelcontextprotocol.io/docs/develop/build-server#python)
