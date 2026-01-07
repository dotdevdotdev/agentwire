# AgentWire TTS/STT Architecture Review

> Created: 2026-01-07
> Status: Analysis complete, cleanup pending

## Executive Summary

The AgentWire TTS/STT system has evolved incrementally, resulting in **redundant pathways, broken components, and confusing abstractions**. This document maps the current state and proposes cleanup.

**Key findings:**
- ✅ MCP `speak()` tool is the **clean, modern path** (connection-aware routing)
- ❌ `daemon.py` is **broken** and never successfully starts
- ⚠️ CLI `say`/`remote-say` commands have **legitimate use cases** but overlap with MCP
- ⚠️ Trigger system for `say` commands is **redundant** with MCP speak()
- ❌ `ChatterboxClient` in TTSRouter is **never used** (all paths go through portal)

---

## Current TTS Pathways

### 1. MCP `speak()` Tool (NEW - Connection-Aware)

**Path:** MCP tool → TTSRouter → PortalClient

**Implementation:**
- File: `agentwire/mcp/server.py` + `agentwire/tts_router.py`
- Entry: Claude Code calls `speak(text, voice?)` via MCP protocol
- Auto-detects tmux session via process tree walk

**Routing logic:**
```
SessionDetector → get tmux session
  ↓
TTSRouter.speak()
  ↓
Check portal connections (GET /api/rooms/{room}/connections, 3s timeout)
  ↓
┌──────────────────────────────┬─────────────────────────────────┐
│ has_connections = true       │ has_connections = false/timeout │
│ → POST /api/say/{room}       │ → POST /api/local-tts/{room}    │
│ → Portal broadcasts to       │ → Portal generates TTS via      │
│    browser via WebSocket     │    chatterbox and plays via     │
│                              │    afplay/aplay on server       │
└──────────────────────────────┴─────────────────────────────────┘
```

**Status:** ✅ **This is the clean, modern path**
- Works correctly
- Connection-aware (plays where you're paying attention)
- Fully integrated with MCP protocol
- Handles remote machines correctly

---

### 2. CLI `agentwire say` Command

**Path:** CLI → _local_say() → chatterbox → afplay/aplay

**Implementation:**
- File: `agentwire/__main__.py:cmd_say()`
- Entry: `agentwire say "text" [--voice NAME] [--room ROOM]`
- Uses NetworkContext to resolve TTS URL with tunnel support

**Behavior:**
- If `--room` specified: calls `_remote_say()` → POST `/api/say/{room}` (portal broadcast)
- Otherwise: calls `_local_say()` → generates TTS, plays locally

**Status:** ⚠️ **Legitimate use case, but overlaps with MCP**
- Useful for shell scripts and non-MCP contexts
- Provides flags for voice/exaggeration/cfg not exposed in MCP
- But: most Claude sessions should use MCP `speak()` instead

**Use cases:**
- Shell scripts that need TTS
- Manual testing outside Claude sessions
- Direct control over TTS parameters (exaggeration, cfg_weight)

---

### 3. `remote-say` Script

**Path:** Script → _remote_say() → POST /api/say/{room} → portal broadcast

**Implementation:**
- Separate script/executable: `remote-say "text"`
- Calls `agentwire say --room $AGENTWIRE_ROOM "text"`
- Room determined from AGENTWIRE_ROOM env var or tmux session name

**Status:** ⚠️ **Overlaps with MCP speak() but has use cases**
- Used in: voice.md rules for local voice input integration
- Convenient for manual testing
- But: most voice features should use MCP speak() instead

**Use cases:**
- Integration with external voice input (Hammerspoon)
- Quick manual testing from terminal

---

### 4. Portal Endpoints

#### `/api/say/{room}` (Browser Broadcast)

**Implementation:**
- File: `agentwire/server.py:api_say()`
- Takes: `{"text": str, "voice": Optional[str]}`
- Generates TTS via chatterbox backend
- Broadcasts to browser via WebSocket

**Called by:**
- MCP `speak()` when connections active
- `agentwire say --room` command
- `remote-say` script

**Status:** ✅ **Core functionality, keep**

#### `/api/local-tts/{room}` (Local Speaker Playback)

**Implementation:**
- File: `agentwire/server.py:api_local_tts()`
- Takes: `{"text": str, "voice": Optional[str]}`
- Generates TTS via chatterbox backend
- Plays on server machine speakers (afplay/aplay)
- Async playback (doesn't block response)

**Called by:**
- MCP `speak()` when no connections

**Status:** ✅ **Core functionality, keep**

#### `/api/rooms/{room}/connections` (Connection Check)

**Implementation:**
- File: `agentwire/server.py:api_room_connections()`
- Returns: `{"has_connections": bool, "connection_count": int}`
- Checks `active_websockets` dict for room

**Called by:**
- TTSRouter._check_portal_connections()

**Status:** ✅ **Core functionality, keep**

---

### 5. Trigger System (Config Pattern Matching)

**Path:** Portal output monitoring → trigger match → action

**Implementation:**
- File: `agentwire/server.py` (trigger processing)
- Config: `~/.agentwire/config.yaml` (trigger definitions)
- Pattern: `'(?:^|\n)(?:remote-)?say\s+(?:"([^"]+)"|''([^'']+)'')'`

**Behavior:**
- Portal monitors tmux session output
- Matches pattern for `say "text"` or `remote-say "text"`
- Triggers TTS action

**Status:** ❌ **REDUNDANT with MCP speak()**
- MCP `speak()` tool provides same functionality
- Adds complexity with pattern matching
- Less reliable than direct tool calls
- Should be **REMOVED**

**Rationale for removal:**
- Claude can now call `speak()` directly via MCP
- No need for pattern matching on terminal output
- Reduces magic behavior and makes debugging easier

---

### 6. AgentWire Daemon

**Path:** Background process → MCP server on stdio (attempted)

**Implementation:**
- File: `agentwire/daemon.py`
- Entry: `agentwire daemon start`
- Attempts to run MCP server in background tmux session

**Status:** ❌ **BROKEN, never successfully starts**

**Problems:**
1. Import errors (MCPServer class doesn't exist in that form)
2. Process spawning issues (Python shebang resolution)
3. Never successfully tested or used
4. MCP server works fine via `claude mcp add` registration - no daemon needed

**Evidence:**
- Earlier session showed daemon failing to start with import errors
- No successful daemon execution logs
- MCP server works when Claude Code starts it directly

**Rationale for removal:**
- Claude Code's MCP client handles server lifecycle
- No need for separate daemon process
- Adds unnecessary complexity
- Never successfully implemented

---

### 7. ChatterboxClient (Unused Code)

**Path:** TTSRouter → ChatterboxClient → direct TTS backend

**Implementation:**
- File: `agentwire/tts_router.py:ChatterboxClient`
- Usage: TTSRouter.speak() calls it when `session is None`

**Status:** ❌ **NEVER USED in practice**

**Why:**
- Session detection always succeeds (even outside tmux, falls back to no session)
- When no session, routes to `local` via portal endpoint, not chatterbox direct
- Only theoretical use case: MCP server can't reach portal
- But: portal is always local, so connection always works

**Rationale for removal:**
- All TTS paths go through portal endpoints
- Portal handles chatterbox backend communication
- Simplifies TTSRouter logic
- Reduces code paths to maintain

---

## STT (Speech-to-Text) Pathways

### 1. Portal Upload Endpoint

**Path:** Browser → POST /upload (multipart) → STT backend → transcription

**Implementation:**
- File: `agentwire/server.py:handle_upload()`
- Takes: Multipart form with audio file
- Backends: WhisperKit, OpenAI, WhisperCpp
- Returns: `{"text": str}`

**Status:** ✅ **Core functionality, keep**

### 2. STT Backend Configuration

**Implementation:**
- Config: `~/.agentwire/config.yaml` (stt section)
- Backends: `whisperkit`, `openai`, `whispercpp`, `none`
- Model paths, API keys, language settings

**Status:** ✅ **Core functionality, keep**

---

## Recommended Cleanup

### Remove Immediately

| Component | File | Reason |
|-----------|------|--------|
| `daemon.py` | `agentwire/daemon.py` | Broken, never works, not needed |
| `cmd_daemon_start/stop/restart` | `agentwire/__main__.py` | Daemon commands for broken daemon |
| `say_command` trigger | `~/.agentwire/config.yaml` | Redundant with MCP speak() |
| `ChatterboxClient` | `agentwire/tts_router.py` | Never used, all paths via portal |
| Chatterbox path in TTSRouter | `agentwire/tts_router.py:speak()` | Never executes, remove branch |

### Keep But Document Clearly

| Component | File | Use Case |
|-----------|------|----------|
| `agentwire say` | `agentwire/__main__.py` | Shell scripts, manual testing, TTS parameter control |
| `remote-say` | Script | External voice input integration (Hammerspoon) |
| MCP `speak()` | `agentwire/mcp/server.py` | **Primary path for all Claude sessions** |

### Deprecation Strategy

1. **Remove daemon.py immediately** - never worked, adds confusion
2. **Remove say_command trigger** - MCP speak() replaces it
3. **Remove ChatterboxClient** - simplifies TTSRouter
4. **Document CLI commands** - clarify when to use vs MCP
5. **Update CLAUDE.md** - explain TTS architecture clearly

---

## Clean Architecture (Proposed)

### TTS Architecture After Cleanup

```
┌─────────────────────────────────────────────────────────────┐
│  Voice Input Sources                                         │
│  ├── MCP speak() tool (PRIMARY for Claude sessions)         │
│  ├── agentwire say (shell scripts, manual testing)          │
│  └── remote-say (external voice input integration)          │
└─────────────────────────────────────────────────────────────┘
                              │
                  ┌───────────┴───────────┐
                  │                       │
          MCP Server (stdio)       CLI Commands
          SessionDetector          (direct execution)
          TTSRouter
                  │                       │
                  └───────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
     PortalClient.speak()        PortalClient.speak_local()
     (browser playback)          (local speakers)
              │                               │
              └───────────────┬───────────────┘
                              │
                  Portal Endpoints
          ┌───────────────────┼───────────────────┐
          │                   │                   │
   /api/say/{room}   /api/local-tts/{room}  /api/rooms/{room}/connections
   (broadcast)       (local playback)       (check connections)
          │                   │
          └───────────────────┘
                    │
          Chatterbox TTS Backend
          (dotdev-pc, via tunnel)
```

### Key Principles

1. **MCP speak() is the primary path** - All Claude sessions use this
2. **Portal endpoints centralize TTS logic** - Browser and local playback
3. **CLI commands for edge cases** - Scripts, testing, external integration
4. **No daemon needed** - Claude Code manages MCP server lifecycle
5. **No triggers** - Direct tool calls replace pattern matching

---

## Migration Steps

### Step 1: Remove Dead Code

```bash
# Files to delete
rm agentwire/daemon.py

# Functions to remove from __main__.py
- cmd_daemon_start()
- cmd_daemon_stop()
- cmd_daemon_status()
- cmd_daemon_restart()
- cmd_daemon_logs()
- cmd_daemon_mcp() (keep this one - it's the MCP entry point, not daemon)

# Wait, cmd_daemon_mcp() is the MCP server entry point!
# Only remove:
- cmd_daemon_start/stop/status/restart/logs
- Leave cmd_daemon_mcp() (rename to cmd_mcp_server()?)

# Classes to remove from tts_router.py
- ChatterboxClient
- Remove "chatterbox" branch from TTSRouter.speak()
```

### Step 2: Update Config

```yaml
# Remove from ~/.agentwire/config.yaml
triggers:
  say_command:  # DELETE THIS ENTIRE BLOCK
```

### Step 3: Update Documentation

Update `CLAUDE.md` to document:
- MCP `speak()` as primary TTS path
- When to use CLI commands vs MCP
- Architecture diagram (clean version)
- No mention of daemon (it's gone)

### Step 4: Test Cleanup

- [ ] Verify MCP `speak()` still works
- [ ] Verify `agentwire say` still works
- [ ] Verify portal endpoints still work
- [ ] Confirm no regressions

---

## Best Practices (Lessons Learned)

### What Worked Well

1. **MCP Protocol Integration** - Clean, documented, works reliably
2. **Connection-Aware Routing** - Smart decision based on real user state
3. **Portal API Endpoints** - Centralized TTS logic, easy to debug
4. **Session Detection** - Auto-detection via process tree works well

### What Didn't Work

1. **Daemon Abstraction** - Added complexity, never successfully implemented
2. **Trigger Pattern Matching** - Fragile, magic behavior, hard to debug
3. **Multiple Overlapping Paths** - Confusion about which to use when
4. **Direct Chatterbox Access** - Unnecessary, portal handles it better

### Architecture Principles

1. **Prefer tool calls over pattern matching** - Explicit beats implicit
2. **Centralize backend communication** - Portal talks to chatterbox, clients talk to portal
3. **Don't abstract until you need it** - Daemon was premature abstraction
4. **One primary path, edge case alternatives** - MCP speak() primary, CLI for special cases
5. **Test early, remove what doesn't work** - Don't let broken code accumulate

---

## Summary

**Current state:** 7 TTS pathways, 2 broken, 2 redundant, 3 legitimate

**After cleanup:** 3 TTS pathways (MCP speak() primary, CLI for edge cases)

**Code reduction:**
- Delete: ~150 lines (daemon.py)
- Delete: ~100 lines (__main__.py daemon commands)
- Delete: ~50 lines (ChatterboxClient)
- Total: **~300 lines removed**

**Complexity reduction:**
- 1 fewer process type (no daemon)
- 1 fewer abstraction layer (no ChatterboxClient)
- 1 fewer trigger (say_command)
- Clearer mental model for developers

**Result:** Simpler, more maintainable system with clear responsibilities.
