# Mission: Remove sessions.json Cache

> Simplify session config by removing the redundant sessions.json cache. Derive everything dynamically from tmux + .agentwire.yml files.

## Problem

sessions.json is a cache that causes sync issues:
- Stores data that's already in .agentwire.yml (type, roles, voice)
- Gets overwritten by cache rebuilds, losing user settings
- Creates confusion about source of truth
- Contains stale entries for deleted sessions

## Solution

Remove sessions.json entirely. Use dynamic data:
- **Session list** → `tmux list-sessions`
- **Session config** → read .agentwire.yml from session's working directory
- **User TTS prefs** → new lightweight `~/.agentwire/tts-prefs.json` (voice, exaggeration, cfg_weight per session)

## Design Decisions

### TTS Preferences Storage

User-set TTS values (voice, exaggeration, cfg_weight) need persistence separate from .agentwire.yml because:
- .agentwire.yml is project-level, checked into git
- TTS prefs are user-specific, shouldn't be in git

Create `~/.agentwire/tts-prefs.json`:
```json
{
  "anna": { "voice": "tiny-tina", "exaggeration": 0.5, "cfg_weight": 0.5 },
  "agentwire": { "voice": "bashbunni" }
}
```

Simple key-value, never rebuilt/overwritten - only updated when user changes via portal.

### Dynamic Session Config

Replace `_get_session_config()` with:
1. Get session's working directory from tmux
2. Read .agentwire.yml from that directory
3. Merge with TTS prefs from tts-prefs.json
4. Fall back to global defaults

---

## Wave 1: Human Actions (BLOCKING)

- [ ] Confirm design approach (tts-prefs.json vs alternative)

---

## Wave 2: Core Refactor

### 2.1 Create TTS Preferences Module
**Files:** `agentwire/tts_prefs.py` (new)

Create simple module for TTS preferences:
- `load_tts_prefs()` → read ~/.agentwire/tts-prefs.json
- `save_tts_pref(session, voice=None, exaggeration=None, cfg_weight=None)`
- `get_tts_pref(session)` → returns dict with voice/exaggeration/cfg_weight

### 2.2 Add Dynamic Session Config
**Files:** `agentwire/server.py`

Replace `_get_session_config()`:
- Query tmux for session's working directory
- Read .agentwire.yml from that path
- Merge with TTS prefs
- Return SessionConfig

Remove:
- `_load_session_configs()`
- `_save_session_configs()`
- `_get_sessions_file()`
- `_rebuild_session_cache()` and related rebuild logic

---

## Wave 3: Update Portal APIs

### 3.1 Update Session Config API
**Files:** `agentwire/server.py`

Update `/api/session/{name}/config` POST handler:
- Write to tts-prefs.json instead of sessions.json
- Update in-memory session if active

### 3.2 Update Sessions List API
**Files:** `agentwire/server.py`

Update `/api/sessions` GET handler:
- Build list dynamically from tmux
- Read .agentwire.yml for each session
- Merge with TTS prefs
- No cache read/write

---

## Wave 4: Update CLI Commands

### 4.1 Remove sessions.json Writes from CLI
**Files:** `agentwire/__main__.py`

Commands to update:
- `cmd_new` - stop writing to sessions.json
- `cmd_kill` - stop removing from sessions.json
- `cmd_fork` - stop copying sessions.json entries

The .agentwire.yml is already written by these commands - that's sufficient.

---

## Wave 5: Cleanup

### 5.1 Remove Validation Check
**Files:** `agentwire/validation.py`

Remove sessions.json existence check from config validation.

### 5.2 Remove Onboarding Init
**Files:** `agentwire/onboarding.py`

Remove code that creates empty sessions.json during init.

### 5.3 Update Config Types
**Files:** `agentwire/config.py`

Remove or deprecate SessionsConfig if no longer needed.

---

## Completion Criteria

- [ ] sessions.json no longer exists or is used
- [ ] TTS prefs persist correctly in tts-prefs.json
- [ ] Session list/config derived dynamically from tmux + .agentwire.yml
- [ ] Voice changes via portal persist across restarts
- [ ] All CLI commands work without sessions.json
- [ ] Tests pass
