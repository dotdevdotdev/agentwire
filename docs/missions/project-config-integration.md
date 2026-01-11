# Mission: Project Config Integration

Complete the `.agentwire.yml` integration by having commands read from it and having the portal rebuild its cache from project configs.

## Context

The composable-roles mission introduced `.agentwire.yml` as the source of truth for session config. Two pieces remain:

1. **Commands reading project config**: The `say` command (and potentially others) should read voice settings from `.agentwire.yml` in the current directory instead of requiring env vars or CLI flags.

2. **Portal cache rebuild**: The portal's `sessions.json` should be rebuilt by scanning tmux sessions and reading their corresponding `.agentwire.yml` files, rather than relying on the CLI to update it.

## Wave 1: Human Actions (BLOCKING)

None - this is pure implementation work.

## Wave 2: Say Command Integration

**Task 2.1: Update say command to read project config**
- Files: `agentwire/__main__.py` (cmd_say function)
- Read `.agentwire.yml` from cwd using `load_project_config()`
- Get voice from project config if not specified on CLI
- Fallback order: CLI `--voice` → `.agentwire.yml` → global config default

**Task 2.2: Update say script wrapper**
- Files: Check if there's a standalone `say` script in `~/.local/bin/` or similar
- Ensure it passes through to `agentwire say` correctly
- May need to read `.agentwire.yml` at bash level for room detection

## Wave 3: Portal Cache Rebuild

**Task 3.1: Add session scanning logic**
- Files: `agentwire/server.py`
- New method: `_rebuild_session_cache()`
- Scan all local tmux sessions via `tmux list-sessions`
- For each session, get working directory via `tmux display-message -p -t {session} '#{pane_current_path}'`

**Task 3.2: Read project configs for sessions**
- Files: `agentwire/server.py`
- For each session's working directory, try to load `.agentwire.yml`
- Build session config from yaml (type, roles, voice)
- Sessions without yaml get defaults

**Task 3.3: Remote session scanning**
- Files: `agentwire/server.py`
- For each machine in machines.json, SSH and list tmux sessions
- Get working directories and read remote `.agentwire.yml` files
- Handle SSH failures gracefully (mark machine offline)

**Task 3.4: Cache refresh triggers**
- Files: `agentwire/server.py`
- Rebuild cache on portal startup
- Add periodic refresh (every 30s or configurable)
- Add manual refresh endpoint: `POST /api/sessions/refresh`

**Task 3.5: Update dashboard to use new cache format**
- Files: `agentwire/static/js/dashboard.js`
- Ensure dashboard correctly displays data from rebuilt cache
- Handle sessions that exist in tmux but have no yaml (show with defaults)

## Wave 4: Room → Session Terminology Cleanup

Consolidate on "session" terminology throughout the codebase. "Room" is legacy from voice chat room concept but we're really dealing with tmux sessions.

**Task 4.1: Rename RoomConfig class**
- Files: `agentwire/server.py`
- Rename `RoomConfig` → `SessionConfig`
- Update all references

**Task 4.2: Remove AGENTWIRE_ROOM env var**
- Files: `agentwire/__main__.py`, `scripts/say`
- Remove `AGENTWIRE_ROOM` checks entirely
- Project yaml is now the source of truth for session identity
- Fallback: CLI flag → `.agentwire.yml` → path inference → tmux session name

**Task 4.3: Rename API endpoints**
- Files: `agentwire/server.py`
- `/api/rooms/{name}/connections` → `/api/sessions/{name}/connections`
- Keep old endpoint as alias for backwards compat

**Task 4.4: Rename functions and variables**
- Files: `agentwire/server.py`, `agentwire/__main__.py`, `scripts/say`
- `get_room_from_config()` → `get_session_from_config()`
- `_get_room_from_yml()` → `_get_session_from_yml()`
- `_get_room_config()` → `_get_session_config()`
- `_load_room_configs()` → remove (use `_load_session_configs()`)
- `_save_room_configs()` → remove (use `_save_session_configs()`)
- Local variables: `room` → `session_name` where appropriate

**Task 4.5: Update comments and docstrings**
- All files with "room" terminology in comments
- Update to use "session" consistently

## Completion Criteria

- [x] `agentwire say "hello"` reads voice from `.agentwire.yml` in cwd
- [x] `say "hello"` (wrapper script) works without explicit session/voice flags
- [x] Portal startup scans tmux sessions and reads project configs
- [x] Portal shows sessions that exist in tmux even if not in sessions.json
- [x] Sessions without `.agentwire.yml` show with default type/roles
- [x] Remote sessions are scanned and included in cache
- [x] `POST /api/sessions/refresh` triggers cache rebuild
- [x] Dashboard displays all sessions correctly
- [ ] `RoomConfig` renamed to `SessionConfig`
- [ ] `AGENTWIRE_ROOM` env var removed
- [ ] API uses `/api/sessions/` consistently
- [ ] No "room" terminology in function names (except backwards compat aliases)
- [ ] Comments use "session" terminology

## Technical Notes

**Session scanning approach:**
```bash
# Get all local sessions with their working directories
tmux list-sessions -F '#{session_name}' | while read session; do
  path=$(tmux display-message -p -t "$session" '#{pane_current_path}')
  echo "$session:$path"
done
```

**Cache structure (sessions.json):**
```json
{
  "myproject": {
    "type": "claude-bypass",
    "roles": ["agentwire"],
    "voice": "dotdev",
    "path": "/Users/dotdev/projects/myproject",
    "source": "yaml"  // or "default" if no yaml found
  }
}
```

**Fallback chain for voice:**
1. CLI `--voice` flag (highest priority)
2. `.agentwire.yml` in cwd
3. Session's voice in sessions.json cache
4. Global config `tts.default_voice`
