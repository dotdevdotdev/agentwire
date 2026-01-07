# Mission: TTS Architecture Cleanup

> Living document. Update this, don't create new versions.

**Status:** Active
**Branch:** `mission/tts-architecture-cleanup`
**Created:** 2026-01-07

## Goal

Remove deprecated, broken, and redundant TTS code following the architecture review. Simplify the codebase by eliminating ~300 lines of dead code and leaving only the clean, modern pathways.

## Context

The connection-aware TTS routing (merged 2026-01-07) established the modern, clean architecture. Now we remove the legacy code that's no longer needed or never worked.

**Review document:** `docs/TTS-STT-ARCHITECTURE-REVIEW.md`

## Current State (Problems)

1. **daemon.py is completely broken** - Never successfully starts, import errors, not needed
2. **say_command trigger is redundant** - MCP `speak()` replaces terminal pattern matching
3. **ChatterboxClient is unused** - All TTS goes through portal endpoints
4. **Daemon CLI commands don't work** - Commands for broken daemon

## Desired State (Clean)

**3 TTS pathways (down from 7):**
- MCP `speak()` tool (primary for Claude sessions)
- `agentwire say` CLI (shell scripts, manual testing)
- `remote-say` script (external voice input integration)

**All paths route through portal endpoints:**
- `/api/say/{room}` - browser playback
- `/api/local-tts/{room}` - local speaker playback
- `/api/rooms/{room}/connections` - connection check

---

## Wave 1: Remove Broken Daemon

**No human actions required** - All code deletions.

### Tasks

- [ ] **1.1: Delete daemon.py**
  - File: `agentwire/daemon.py`
  - This file is completely broken and never successfully starts
  - Remove entire file (~78 lines)

- [ ] **1.2: Remove daemon CLI commands from __main__.py**
  - File: `agentwire/__main__.py`
  - Remove functions:
    - `cmd_daemon_start()` (~30 lines)
    - `cmd_daemon_stop()` (~15 lines)
    - `cmd_daemon_status()` (~20 lines)
    - `cmd_daemon_restart()` (~10 lines)
    - `cmd_daemon_logs()` (~15 lines)
  - **Keep** `cmd_daemon_mcp()` - this is the MCP server entry point (not daemon-related)
  - Remove argparse subcommands for daemon start/stop/status/restart/logs
  - Total: ~90 lines removed

- [ ] **1.3: Commit Wave 1**
  - Commit message: "cleanup: Remove broken daemon code"
  - Push to branch

---

## Wave 2: Remove Redundant Trigger System

**No human actions required** - Config and documentation updates.

### Tasks

- [ ] **2.1: Remove say_command trigger from default config**
  - File: `agentwire/config.py` (if default config exists there)
  - Or document in CLAUDE.md that users should remove it
  - This trigger is redundant - MCP `speak()` provides same functionality

- [ ] **2.2: Update config.yaml template/example**
  - File: Documentation showing config.yaml examples
  - Remove `say_command` trigger block from examples
  - Note: User's `~/.agentwire/config.yaml` not touched (they can clean manually)

- [ ] **2.3: Update documentation**
  - File: `CLAUDE.md` or relevant docs
  - Remove mentions of say_command trigger
  - Document that MCP `speak()` is the primary TTS pathway
  - Note that pattern matching triggers are not recommended for TTS

- [ ] **2.4: Commit Wave 2**
  - Commit message: "cleanup: Remove redundant say_command trigger from docs"
  - Push to branch

---

## Wave 3: Remove Unused ChatterboxClient

**No human actions required** - Code simplification.

### Tasks

- [ ] **3.1: Remove ChatterboxClient class**
  - File: `agentwire/tts_router.py`
  - Remove entire `ChatterboxClient` class (~35 lines)
  - Remove initialization in `TTSRouter.__init__`
  - Remove chatterbox branch from `TTSRouter.speak()` (the `else:` block)
  - Update docstring to reflect only portal routing

- [ ] **3.2: Simplify TTSRouter.speak() logic**
  - File: `agentwire/tts_router.py`
  - Remove the "no session" → chatterbox path (lines 212-220)
  - Routing should only be:
    ```python
    if session and await self._check_portal_connections(session):
        # Browser playback
    elif session:
        # Local speaker playback
    else:
        # Error: no session detected
        return TTSResult(success=False, method="none", error="No session detected")
    ```
  - Update `TTSResult` to remove `"chatterbox"` from method literal type

- [ ] **3.3: Commit Wave 3**
  - Commit message: "cleanup: Remove unused ChatterboxClient code"
  - Push to branch

---

## Wave 4: Documentation and Testing

### Tasks

- [ ] **4.1: Update CLAUDE.md**
  - File: `CLAUDE.md`
  - Update Voice Layer section
  - Document clean architecture:
    - MCP `speak()` as primary
    - CLI commands for edge cases
    - No daemon needed
    - No triggers for TTS
  - Add architecture diagram (text-based)

- [ ] **4.2: Update TTS-STT-ARCHITECTURE-REVIEW.md**
  - File: `docs/TTS-STT-ARCHITECTURE-REVIEW.md`
  - Mark cleanup as completed
  - Update "Proposed" sections to "Current" (after cleanup)
  - Document final line count reduction

- [ ] **4.3: Test TTS functionality**
  - Verify MCP `speak()` still works (browser + local paths)
  - Verify `agentwire say` still works
  - Verify `remote-say` still works
  - Confirm no regressions

- [ ] **4.4: Commit Wave 4**
  - Commit message: "docs: Update architecture documentation after cleanup"
  - Push to branch

---

## Completion Criteria

- [ ] daemon.py deleted (~78 lines)
- [ ] Daemon CLI commands removed (~90 lines)
- [ ] ChatterboxClient removed (~35 lines)
- [ ] Unused routing path removed (~15 lines)
- [ ] Documentation updated to reflect clean architecture
- [ ] Total code reduction: ~218 lines (conservative estimate, may be more)
- [ ] All TTS functionality still works (MCP, CLI, remote-say)
- [ ] No regressions in existing features

---

## Implementation Notes

### Files Modified

| File | Changes | Lines Removed |
|------|---------|---------------|
| `agentwire/daemon.py` | DELETE entire file | ~78 |
| `agentwire/__main__.py` | Remove daemon commands | ~90 |
| `agentwire/tts_router.py` | Remove ChatterboxClient + unused path | ~50 |
| `docs/*` | Update documentation | N/A |
| **Total** | | **~218 lines** |

### Architecture After Cleanup

```
TTS Pathways (3 total):

1. MCP speak() Tool (PRIMARY)
   MCP protocol → SessionDetector → TTSRouter → PortalClient
                                                 ├→ /api/say/{room} (browser)
                                                 └→ /api/local-tts/{room} (speakers)

2. CLI: agentwire say [--room ROOM] "text"
   Shell → cmd_say() → _local_say() or _remote_say()
                       ├→ chatterbox + afplay (local)
                       └→ POST /api/say/{room} (browser)

3. Script: remote-say "text"
   External → agentwire say --room $ROOM "text"
```

### What's Gone

- ❌ daemon.py (never worked)
- ❌ Daemon CLI commands (for broken daemon)
- ❌ say_command trigger (redundant pattern matching)
- ❌ ChatterboxClient (all paths via portal)
- ❌ Direct chatterbox routing (unused code path)

### What Remains

- ✅ MCP `speak()` tool (primary, connection-aware)
- ✅ `agentwire say` CLI (edge cases, shell scripts)
- ✅ `remote-say` script (external integration)
- ✅ Portal endpoints (centralized TTS logic)
- ✅ TTSRouter (simplified to portal-only routing)

---

## Testing Plan

### Functional Tests

**Test 1: MCP speak() with browser connection**
```bash
# In portal, open room for this session
speak("Testing browser playback after cleanup")
# Expected: Audio plays in browser
```

**Test 2: MCP speak() with no connection**
```bash
# Close browser tab
speak("Testing local playback after cleanup")
# Expected: Audio plays on local speakers
```

**Test 3: CLI say command (local)**
```bash
agentwire say "Testing CLI local playback"
# Expected: Audio plays on local speakers
```

**Test 4: CLI say command (remote)**
```bash
agentwire say --room test-room "Testing CLI browser playback"
# Expected: Audio broadcasts to portal
```

**Test 5: remote-say script**
```bash
remote-say "Testing external integration"
# Expected: Audio plays appropriately based on room
```

### Regression Tests

- [ ] Portal still starts correctly
- [ ] MCP server still registers correctly
- [ ] Session detection still works
- [ ] Connection checking still works
- [ ] TTS generation still works
- [ ] No import errors
- [ ] No broken references to removed code

---

## Migration Notes

**No breaking changes:**
- All user-facing functionality preserved
- MCP `speak()` tool unchanged
- CLI commands unchanged
- Portal endpoints unchanged

**User impact:**
- Cleaner codebase (easier to maintain)
- No more confusing daemon commands
- Clearer documentation
- Faster onboarding for new developers

**Manual user actions (optional):**
- Users can remove `say_command` trigger from `~/.agentwire/config.yaml` if present
- No action required - trigger just won't be used

---

## Related Issues

- Related to: TTS-STT-ARCHITECTURE-REVIEW.md (2026-01-07)
- Depends on: connection-aware-tts-routing (merged 2026-01-07)
- Closes: Architecture complexity issues

---

## Best Practices Applied

1. **Delete dead code aggressively** - Don't leave broken code "just in case"
2. **One primary path** - MCP speak() is the way, not multiple competing solutions
3. **Simplify abstractions** - Remove ChatterboxClient layer that added no value
4. **Document the "why"** - Architecture review explains reasoning for cleanup
5. **Test after cleanup** - Verify nothing breaks when removing code
