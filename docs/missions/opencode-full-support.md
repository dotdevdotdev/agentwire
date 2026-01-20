# Mission: Full OpenCode Support

> Wave-based mission for complete OpenCode parity with Claude Code across all AgentWire features.

**Branch:** `mission/opencode-full-support`
**Base:** `investigate-opencode`
**Status:** ✅ Implementation complete (pending manual testing)

**Completed commits:**
- `7b6ea5a` - project config defaults to STANDARD type (2.3)
- `9704b79` - agent-agnostic language in role files (5.1)
- `a9c1f6d` - init script detects agent type (3.2)
- `da43a3c` - add OpenCode mentions throughout docs (4.1-4.5)
- `cccd356` - config defaults detect agent type (2.2)
- `dfc858d` - OpenCode support in portal API (1.3, 6.1, 6.2)
- `e040a97` - onboarding supports OpenCode detection (3.1)
- Tasks 1.1, 1.2, 2.1 already implemented in earlier commit `3c06047`
- Task 1.4 already implemented with `parse_env_var_prefix()` function

---

## Context

The `build_agent_command()` refactor (commit 3c06047) established the pattern for supporting both Claude Code and OpenCode. This mission extends that pattern to all remaining areas of the codebase.

**Key Pattern:** Detect agent type via `detect_default_agent_type()`, then apply agent-specific flags/env vars.

---

## Wave 1: Critical Fixes (Broken Functionality)

These issues cause OpenCode sessions to fail completely.

### 1.1 Remote Session Creation Hardcodes "claude"
**File:** `agentwire/__main__.py`
**Lines:** 3182-3189
**Issue:** Remote `recreate` command builds command as `'claude{bypass_flag}'` instead of using `build_agent_command()`

```python
# WRONG (current)
bypass_flag = "" if (restricted or no_bypass) else " --dangerously-skip-permissions"
create_cmd = f"tmux send-keys -t ... 'claude{bypass_flag}' Enter"

# RIGHT (fix)
agent = build_agent_command(session_type_str, roles)
create_cmd = f"tmux send-keys -t ... {shlex.quote(agent.command)} Enter"
```

**Files to modify:** `agentwire/__main__.py`

### 1.2 History Resume Hardcodes "claude"
**File:** `agentwire/__main__.py`
**Lines:** 3808, 3828
**Issue:** `cmd_history_resume()` always uses "claude" command and defaults to `CLAUDE_BYPASS`

```python
# Line 3808 - WRONG default
project_config = ProjectConfig(type=SessionType.CLAUDE_BYPASS, ...)

# Line 3828 - WRONG hardcoded command
claude_parts = ["claude", "--resume", session_id, "--fork-session"]
```

**Fix approach:**
1. Detect agent type for default
2. OpenCode doesn't support `--resume` - need different approach or document limitation
3. If Claude: use existing logic; if OpenCode: either skip resume or implement alternative

**Files to modify:** `agentwire/__main__.py`

### 1.3 Portal API Missing OpenCode Type Mapping
**File:** `agentwire/portal/server.py`
**Lines:** 1559-1563, 2558-2562, 2621-2625, 2685-2689
**Issue:** Four API endpoints use conditional flags instead of `--type` flag

```python
# WRONG (current) - in 4 locations
if session_type == "claude-restricted":
    args.append("--restricted")
elif session_type == "claude-prompted":
    args.append("--no-bypass")

# RIGHT (fix) - use --type flag which handles all session types
args.extend(["--type", session_type])
```

**Affected endpoints:**
- `api_create_session` (line 1559)
- `api_recreate_session` (line 2558)
- `api_spawn_sibling` (line 2621)
- `api_fork_session` (line 2685)

**Files to modify:** `agentwire/portal/server.py`

### 1.4 Remote OpenCode Env Var Not Reaching tmux
**File:** `agentwire/agents/tmux.py`
**Lines:** 211-215
**Issue:** When creating remote sessions, `OPENCODE_PERMISSION='...'` is quoted and sent as literal text instead of being set as an env var

```python
# Current - env var gets quoted as text
cmd = f"tmux send-keys -t ... {shlex.quote(agent_cmd)} Enter"
# agent_cmd = "OPENCODE_PERMISSION='{...}' opencode"
# After quoting: "'OPENCODE_PERMISSION=...'"  <- broken

# Fix approach: Set env var in tmux session first
# tmux set-environment -t session OPENCODE_PERMISSION '{...}'
# Then send: opencode
```

**Files to modify:** `agentwire/agents/tmux.py`, possibly `agentwire/__main__.py`

---

## Wave 2: Default Value Fixes

These cause sessions to use Claude when OpenCode should be used.

### 2.1 Hardcoded "claude-bypass" Defaults in CLI
**File:** `agentwire/__main__.py`
**Lines:** 3271-3272, 3413-3414, 3505-3506, 3598-3599
**Issue:** Four locations default to `"claude-bypass"` instead of detecting agent

```python
# WRONG (in 4 locations)
session_type_str = "claude-bypass"

# RIGHT
agent_type = detect_default_agent_type()
session_type_str = f"{agent_type}-bypass"
```

**Affected functions:**
- `cmd_recreate()` local path (line 3271)
- `cmd_fork()` remote path (line 3413)
- `cmd_fork()` local same-dir (line 3505)
- `cmd_fork()` local worktree (line 3598)

**Files to modify:** `agentwire/__main__.py`

### 2.2 Config Defaults Hardcode Claude
**File:** `agentwire/config.py`
**Lines:** 109, 291
**Issue:** `AgentConfig.command` defaults to Claude

```python
# Line 109 - class default
command: str = "claude --dangerously-skip-permissions"

# Line 291 - fallback during load
command=agent_data.get("command", "claude --dangerously-skip-permissions")
```

**Fix:** Use `detect_default_agent_type()` to build appropriate default

**Files to modify:** `agentwire/config.py`

### 2.3 ProjectConfig Default Type
**File:** `agentwire/project_config.py`
**Lines:** 38, 134
**Issue:** Defaults to `CLAUDE_BYPASS` for unknown types and class default

```python
# Line 38 - from_str fallback
return cls.CLAUDE_BYPASS  # Should detect or use STANDARD

# Line 134 - class default
type: SessionType = SessionType.CLAUDE_BYPASS
```

**Fix:** Use `SessionType.STANDARD` (agent-agnostic) which gets normalized at runtime

**Files to modify:** `agentwire/project_config.py`

---

## Wave 3: Onboarding Fixes

These affect new user experience with OpenCode.

### 3.1 Onboarding Only Checks for Claude
**File:** `agentwire/onboarding.py`
**Lines:** 545, 757-770, 854-862, 877, 923, 986-1002
**Issues:**
- Sample config hardcodes Claude command (545)
- Only has `check_claude()`, no `check_opencode()` (757-770)
- Warning if Claude not found but OpenCode may be present (854-862)
- User prompts only offer Claude options (986-1002)

**Fix approach:**
1. Add `check_opencode()` function
2. Detect which agent(s) are installed
3. Update prompts to show appropriate options
4. Generate config based on detected agent

**Files to modify:** `agentwire/onboarding.py`

### 3.2 Init Script Hardcodes Claude
**File:** `agentwire/init_agentwire.py`
**Lines:** 151-154
**Issue:** Directly runs `claude --dangerously-skip-permissions`

**Fix:** Use detected agent or config setting

**Files to modify:** `agentwire/init_agentwire.py`

---

## Wave 4: Documentation Updates

### 4.1 CLAUDE.md Project Description
**File:** `CLAUDE.md`
**Line:** 3
**Current:** "...tmux sessions running Claude Code"
**Update to:** "...tmux sessions running Claude Code or OpenCode"

Also update:
- Line 108: Hooks documentation (mention both agents)
- Line 168: Sample config (show both options)

**Files to modify:** `CLAUDE.md`

### 4.2 Remote Machines Documentation
**File:** `docs/remote-machines.md`
**Line:** Opening
**Current:** "AgentWire can manage Claude Code sessions on remote machines"
**Update to:** "AgentWire can manage AI agent sessions (Claude Code or OpenCode) on remote machines"

**Files to modify:** `docs/remote-machines.md`

### 4.3 Portal Documentation
**File:** `docs/PORTAL.md`
**Lines:** ~140, ~170
**Issues:**
- Fork sessions documented as Claude Code only (needs limitation note)
- "Claude (or users)" should be "Agent (or users)"

**Files to modify:** `docs/PORTAL.md`

### 4.4 Troubleshooting Agent-Specific Sections
**File:** `docs/TROUBLESHOOTING.md`
**Issue:** Shell escaping section is Claude Code specific but not marked as such

**Fix:** Add "Claude Code Specific" heading or note

**Files to modify:** `docs/TROUBLESHOOTING.md`

### 4.5 Architecture Examples
**File:** `docs/architecture.md`
**Issue:** Examples only show Claude Code flows

**Fix:** Add OpenCode flow examples or clarify architecture applies to both

**Files to modify:** `docs/architecture.md`

---

## Wave 5: Role File Updates

### 5.1 Agent-Agnostic Language in Roles
**Files:** `agentwire/roles/*.md`
**Issue:** References to "Claude Code", "Claude agent" should be generic

**Examples:**
- `worker.md`: "You have full Claude Code access" -> "You have full agent access"
- `agentwire.md`: Architecture advice assumes Claude-specific capabilities

**Fix:** Review and update language to be agent-agnostic where appropriate

**Files to modify:**
- `agentwire/roles/agentwire.md`
- `agentwire/roles/worker.md`
- `agentwire/roles/chatbot.md`
- `agentwire/roles/voice.md`

---

## Wave 6: Portal API Enhancements (Optional)

### 6.1 Add Roles Parameter to Create Session API
**File:** `agentwire/portal/server.py`
**Lines:** 1509-1564
**Issue:** API doesn't support `--roles` parameter

**Enhancement:**
```python
roles = data.get("roles")
if roles:
    args.extend(["--roles", roles])
```

**Files to modify:** `agentwire/portal/server.py`

### 6.2 Update API Docstrings
**File:** `agentwire/portal/server.py`
**Lines:** 1516, 2548, 2598, 2652
**Issue:** Docstrings only list Claude types

**Update to include:** `opencode-bypass | opencode-prompted | opencode-restricted | bare`

**Files to modify:** `agentwire/portal/server.py`

---

## Completion Criteria

- [x] All session creation paths detect agent type correctly
- [x] Remote sessions work with OpenCode (env vars properly set)
- [x] Portal API handles all session types via `--type` flag
- [x] Onboarding detects and supports OpenCode
- [x] Documentation mentions both agents where appropriate
- [x] No hardcoded "claude" strings in command building paths
- [ ] `agentwire new -s test --type opencode-bypass` creates working OpenCode session (manual test needed)
- [ ] `agentwire new -s test --type claude-bypass` still works - no regression (manual test needed)

---

## Notes

- OpenCode doesn't support `--resume` flag - session resumption may need alternative approach
- OpenCode doesn't support `--tools`/`--disallowedTools` - tool restrictions via role instructions only
- The `build_agent_command()` function in `__main__.py:77-162` is the reference implementation
