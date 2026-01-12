# Mission: Remove sessions.json Cache

> Simplify session config by removing the redundant sessions.json cache. Derive everything dynamically from tmux + .agentwire.yml files.

## Problem

sessions.json is a cache that causes sync issues:
- Stores data that's already in .agentwire.yml (type, roles, voice)
- Gets overwritten by cache rebuilds, losing user settings
- Creates confusion about source of truth

## Solution

Remove sessions.json entirely. Use dynamic data:
- **Session list** → `tmux list-sessions` (already works via `agentwire list`)
- **Session config** → read .agentwire.yml from session's working directory
- **Voice changes** → edit .agentwire.yml directly via SSH

No separate cache or prefs file needed. `.agentwire.yml` is the single source of truth.

## Already Done

- [x] Removed exaggeration/cfg_weight sliders from portal UI
- [x] Voice is the only configurable setting in session page

---

## Wave 1: Human Actions (BLOCKING)

- [ ] Confirm approach

---

## Wave 2: Dynamic Session Config

### 2.1 Replace _get_session_config with Dynamic Lookup
**Files:** `agentwire/server.py`

Replace `_get_session_config()`:
- Get session's working directory from tmux (or active_sessions cache)
- Read .agentwire.yml from that path via SSH if remote
- Return SessionConfig with type, roles, voice from yaml
- Fall back to defaults if no yaml found

Remove:
- `_load_session_configs()`
- `_save_session_configs()`
- `_get_sessions_file()`
- `_rebuild_session_cache()` and periodic refresh task

### 2.2 Update Voice Config API to Edit .agentwire.yml
**Files:** `agentwire/server.py`

Update `/api/session/{name}/config` POST handler:
- Parse session name to get machine
- Get session's working directory
- Read .agentwire.yml via SSH (if remote)
- Update voice field
- Write back via SSH

---

## Wave 3: Update Sessions List API

### 3.1 Dynamic Session List
**Files:** `agentwire/server.py`

Update `/api/sessions` GET handler:
- Call `agentwire list --json` or scan tmux directly
- For each session, read .agentwire.yml to get type/roles/voice
- Return combined data
- No cache involved

---

## Wave 4: CLI Cleanup

### 4.1 Remove sessions.json Writes
**Files:** `agentwire/__main__.py`

Commands to update:
- `cmd_new` - stop writing to sessions.json (yaml is written already)
- `cmd_kill` - stop removing from sessions.json
- `cmd_fork` - stop copying sessions.json entries

---

## Wave 5: Final Cleanup

### 5.1 Remove Validation Check
**Files:** `agentwire/validation.py`

Remove sessions.json existence check.

### 5.2 Delete sessions.json
User deletes `~/.agentwire/sessions.json` manually.

---

## Completion Criteria

- [ ] sessions.json no longer exists or is used
- [ ] Session list comes from tmux dynamically
- [ ] Session config comes from .agentwire.yml
- [ ] Voice changes via portal edit .agentwire.yml directly
- [ ] All CLI commands work without sessions.json
