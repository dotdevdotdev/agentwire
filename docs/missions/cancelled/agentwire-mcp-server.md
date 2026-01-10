# CANCELLED: AgentWire MCP Server

> **CANCELLED** - Never fully implemented. Removed in Wave 8 cleanup of voice-orchestrator-workers mission.
>
> The daemon-based MCP server was planned but never fully wired to the CLI. The bash `say` command
> with smart routing via portal HTTP APIs is the working solution and remains the recommended approach.
>
> **Deleted in cleanup:**
> - `agentwire/mcp/` (server.py, tools.py, __init__.py)
> - `agentwire/tts_router.py`
> - `agentwire/session_detector.py`
> - Related test files
> - `docs/MIGRATION-MCP.md`

---

## Original Mission (for reference)

> Replace say/remote-say shell scripts with proper MCP server integration for reliable voice access.

## Why It Was Cancelled

1. **Never wired to CLI** - The MCP server code existed but was never connected to `agentwire daemon` commands
2. **Working alternative exists** - The bash `agentwire say` command with smart routing via portal HTTP APIs works well
3. **Complexity vs value** - MCP server added significant complexity for marginal benefit
4. **Session detection issues** - Detecting the calling tmux session from MCP stdio proved unreliable

## Current Solution

Use the `agentwire say` command:

```bash
# Smart routing (browser if connected, local if not)
agentwire say "Hello world"
agentwire say "Message" -v bashbunni     # Specify voice
agentwire say "Message" -r myroom        # Specify room
```

The command:
1. Detects room from `--room`, `AGENTWIRE_ROOM` env var, or tmux session name
2. Checks portal for active browser connections
3. Routes to portal (browser) or generates locally as appropriate

---

*Original mission planning content archived below for historical reference.*

---

## Original Objective

Provide Claude Code sessions with native TTS capabilities via MCP server, eliminating installation issues and improving reliability. The MCP server runs as a background daemon and auto-detects which session is calling.

## Original Background

**Current say/remote-say Problems:**
- Shell scripts requiring installation and PATH configuration
- Installation issues documented in case study (~/.local/bin not in PATH)
- Depend on AGENTWIRE_ROOM env var being set correctly
- Remote machines need portal_url configured
- Portal must be running for remote-say to work
- Silent failures if portal is down
- Instruction-based (agents must "know" to use them)

**MCP Server Benefits:**
- Native tool integration (Claude Code auto-discovers)
- Always available (background daemon)
- Works without portal running (local TTS fallback)
- Auto-detects calling session (no AGENTWIRE_ROOM needed)
- Proper error messages (not silent failures)
- No installation per session (MCP configured once globally)
- No PATH issues (MCP handles routing)

## Original Architecture

```
agentwire daemon (background service)
  |--> MCP server (stdio protocol)
  |    '--> Tools: speak, list_voices, set_voice
  |
  |--> Session detector
  |    '--> Maps PID --> tmux session --> room name
  |
  '--> TTS router (tries in order)
       |--> Portal API (if available and session has room)
       |--> Chatterbox direct (if configured)
       '--> System TTS (fallback)
```

## Lessons Learned

1. **Start simple** - The bash command approach is simpler and works reliably
2. **Avoid over-engineering** - MCP server added complexity without proven need
3. **Test integration early** - The session detection component was never fully tested in practice
4. **Clean up dead code** - Orphaned code creates maintenance burden
