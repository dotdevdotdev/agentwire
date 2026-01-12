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

- [x] Confirm approach

---

## Wave 2: Dynamic Session Config

### 2.1 Replace _get_session_config with Dynamic Lookup
**Files:** `agentwire/server.py`

- [x] Replace `_get_session_config()` with dynamic lookup from tmux + .agentwire.yml
- [x] Add `_get_session_cwd()`, `_read_agentwire_yaml()`, `_write_agentwire_yaml()` helpers
- [x] Remove `_load_session_configs()`, `_save_session_configs()`, `_get_sessions_file()`
- [x] Remove `_rebuild_session_cache()` and periodic refresh task

### 2.2 Update Voice Config API to Edit .agentwire.yml
**Files:** `agentwire/server.py`

- [x] Update `/api/session/{name}/config` POST to edit .agentwire.yml directly via SSH

---

## Wave 3: Update Sessions List API

### 3.1 Dynamic Session List
**Files:** `agentwire/server.py`

- [x] Update `/api/sessions` GET to use dynamic lookups (no cache)

---

## Wave 4: CLI Cleanup

### 4.1 Remove sessions.json Writes
**Files:** `agentwire/__main__.py`

- [x] Removed sessions.json writes from: `cmd_new`, `cmd_kill`, `cmd_fork`, `cmd_rename`, `cmd_agent`, `cmd_move`, `cmd_duplicate`, `cmd_gc`, `cmd_recreate`, `cmd_machine_remove`

---

## Wave 5: Final Cleanup

### 5.1 Remove Validation Check
**Files:** `agentwire/validation.py`

- [x] Removed sessions.json existence check
- [x] Removed sessions.json from "Files checked" output

### 5.2 Delete sessions.json
- [ ] User deletes `~/.agentwire/sessions.json` manually

### 5.3 Config Cleanup
**Files:** `agentwire/config.py`, `agentwire/onboarding.py`, `agentwire/project_config.py`

- [x] Removed `SessionsConfig` class from config.py
- [x] Removed sessions.json creation from onboarding.py (local + remote)
- [x] Removed outdated comment from project_config.py

---

## Completion Criteria

- [x] sessions.json no longer exists or is used
- [x] Session list comes from tmux dynamically
- [x] Session config comes from .agentwire.yml
- [x] Voice changes via portal edit .agentwire.yml directly
- [x] All CLI commands work without sessions.json
