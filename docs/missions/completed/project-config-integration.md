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

## Completion Criteria

- [x] `agentwire say "hello"` reads voice from `.agentwire.yml` in cwd
- [x] `say "hello"` (wrapper script) works without explicit room/voice flags
- [x] Portal startup scans tmux sessions and reads project configs
- [x] Portal shows sessions that exist in tmux even if not in sessions.json
- [x] Sessions without `.agentwire.yml` show with default type/roles
- [x] Remote sessions are scanned and included in cache
- [x] `POST /api/sessions/refresh` triggers cache rebuild
- [x] Dashboard displays all sessions correctly

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
