# Mission: OpenCode Integration

**Make AgentWire work seamlessly with both Claude Code and OpenCode AI coding agents.**

## Background

AgentWire currently hardcodes Claude Code as the only AI agent. Users want flexibility to choose their preferred coding agent (Claude Code, OpenCode, or future alternatives). OpenCode offers compelling advantages:
- **Open source** (79k GitHub stars vs proprietary Claude Code)
- **Provider agnostic** (75+ LLM providers vs Anthropic-only)
- **Richer architecture** (client/server, HTTP API, TUI, web, mobile)
- **Plugin system** (30+ event hooks)
- **Better permission system** (allow/ask/deny with pattern matching)

## Current AgentWire → Claude Code Integration

### 1. Session Types (4 types)

| Type | CLI Flags | Tools | Permissions | Use Case |
|-------|-------------|--------|-------------|-----------|
| `bare` | (none) | N/A | N/A | Manual coding, terminal only |
| `claude-bypass` | `--dangerously-skip-permissions` | All | No prompts | Full automation, voice orchestrator |
| `claude-prompted` | (none) | All | Yes (via hook) | Semi-automated, approvals needed |
| `claude-restricted` | `--tools Bash` | Bash only | Auto-deny non-say | Voice-only, read-only access |

### 2. Claude Code CLI Flags Used

| Flag | Purpose | Session Types |
|-------|---------|---------------|
| `--dangerously-skip-permissions` | Bypass all permission prompts | claude-bypass |
| `--tools tool1,tool2` | Whitelist specific tools | All (except bare) |
| `--disallowedTools tool1` | Blacklist specific tools | All (except bare) |
| `--append-system-prompt "text"` | Add role instructions | All (except bare) |
| `--model sonnet/opus/haiku` | Override model | All (except bare) |
| `--resume <session-id>` | Resume from history | Fork sessions |
| `--fork-session` | Fork into new session | Fork sessions |

### 3. Roles System

**Format:**
```yaml
---
name: worker
description: Autonomous code execution, no user interaction
disallowedTools: AskUserQuestion
model: inherit
---

Worker agent instructions...
```

**Merging Logic:**
- **Tools:** Union of all role tools
- **Disallowed tools:** Intersection (only block if ALL agree)
- **Instructions:** Concatenated with newlines
- **Model:** Last non-None wins

### 4. Hooks Architecture

#### Permission Hooks (`agentwire-permission.sh`)
- **Hook type:** `PermissionRequest` (Claude Code)
- **Location:** `~/.claude/settings.json`
- **Flow:** Claude → Hook → Portal API → User → Portal API → Hook → Claude
- **Timeout:** 5 minutes
- **Keystroke mapping:** allow → "1", allow_always → "2", deny → "Escape", custom → "3" + message

#### Damage Control Hooks (3 Python hooks)
- **Hook type:** `PreToolUse` (Claude Code)
- **Location:** `~/.agentwire/hooks/damage-control/`
- **Checks:**
  - 100+ bash command patterns (destructive ops, cloud platforms, etc.)
  - 66 zero-access paths (secrets, SSH keys, credentials)
  - 30+ read-only paths (system dirs, lock files)
  - 20+ no-delete paths (agentwire config, git data, docs)
- **Exit codes:** 0 = allow, 2 = block

### 5. Permission Dialog Flow

```
Claude Code → Permission Hook → Portal API → User Decision → Portal API → Permission Hook → Claude Code
```

**Endpoints:**
- `POST /api/permission/{session}` - Hook posts request, waits for response
- `POST /api/permission/{session}/respond` - Portal posts user decision

**Auto-handling for claude-restricted:**
- Allow: `AskUserQuestion` tool
- Allow: `Bash` with `say` command only (regex: `^(?:agentwire\s+)?say\s+(?:-[sv]\s+\S+\s+)*(["\']).*\1\s*&?\s*$`)
- Deny: Everything else

### 6. History Integration

**Claude Data:**
- `~/.claude/history.jsonl` - User message history
- `~/.claude/projects/{encoded-path}/*.jsonl` - Session files

**Path Encoding:** `/home/user/projects/myapp` → `-home-user-projects-myapp`

**Commands:**
- `agentwire history list` - List sessions for project
- `agentwire history show <id>` - Show session details
- `agentwire history resume <id>` - Resume (always forks)

---

## OpenCode Capabilities Analysis

### 1. No Direct `--dangerously-skip-permissions` Equivalent

**Problem:** OpenCode lacks Claude's bypass flag.

**Solution:** Use permission config + env var:

```bash
# Global allow-all
export OPENCODE_PERMISSION='{"*":"allow"}'
opencode run "message"

# Per-agent allow-all
opencode --agent agentwire "message"  # agentwire agent configured with permission: {"*":"allow"}
```

### 2. Agent System (Primary vs Subagent)

| Type | Description | Tools | Permissions |
|------|-------------|--------|-------------|
| **Primary** | Main assistant users interact with | All | Per-agent config |
| **Subagent** | Specialized, invoked by primary | Configurable | Per-agent config |

**Agent Config (JSON):**
```json
{
  "agent": {
    "agentwire": {
      "mode": "primary",
      "tools": {
        "write": true,
        "edit": true,
        "bash": true,
        "question": true
      }
    },
    "worker": {
      "mode": "subagent",
      "permission": {
        "question": "deny"
      }
    }
  }
}
```

**Agent Config (Markdown):**
```yaml
# ~/.config/opencode/agents/worker.md
---
description: Worker pane (no voice, no questions)
mode: subagent
permission:
  question: deny
tools:
  write: true
  edit: true
  bash: true
  question: false
---

Worker agent instructions...
```

### 3. Permission System (Three States)

| State | Behavior |
|-------|----------|
| `allow` | Tool runs without approval |
| `ask` | User prompted (once/always/reject) |
| `deny` | Tool is blocked |

**Granular Rules:**
```json
{
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "rm *": "deny"
    }
  }
}
```

### 4. Plugin System (30+ Event Hooks)

**Plugin Structure:**
```javascript
.opencode/plugins/example.js

export const Plugin = async ({ project, client, $, directory, worktree }) => {
  return {
    "tool.execute.before": async (input, output) => {
      // Intercept before tool execution
    },
    "permission.updated": async (input, output) => {
      // React to permission changes
    }
  }
}
```

**Available Hooks:**
- **Tool events:** `tool.execute.before`, `tool.execute.after`
- **Permission events:** `permission.replied`, `permission.updated`
- **Session events:** `session.created`, `session.updated`, `session.deleted`
- **Message events:** `message.updated`, `message.removed`
- **File events:** `file.edited`, `file.watcher.updated`
- **Command events:** `command.executed`
- **Server events:** `server.connected`
- **Todo events:** `todo.updated`

### 5. HTTP Server API

**Command:** `opencode serve --port 8765`

**Key Endpoints:**
- `POST /session/{id}/message` - Send prompt to session
- `GET /session/{id}` - Get session info
- `POST /session/{id}/fork` - Fork session
- `POST /session` - Create new session
- WebSocket connection for real-time updates

**Benefits for AgentWire:**
- Single OpenCode instance handles all sessions
- No need to spawn multiple opencode processes
- Portal sends HTTP requests instead of managing subprocesses

### 6. Claude Code Compatibility

OpenCode reads Claude Code files as fallbacks:

| Claude Code Path | OpenCode Uses | Disable via |
|------------------|-----------------|---------------|
| `CLAUDE.md` (project) | If no `AGENTS.md` exists | `OPENCODE_DISABLE_CLAUDE_CODE` |
| `~/.claude/CLAUDE.md` | If no `~/.config/opencode/AGENTS.md` | `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT` |
| `~/.claude/skills/` | Loaded as skills | `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` |

**Migration path is smooth** - existing roles and skills work immediately.

---

## Architecture Design

### 1. Agent Detection Strategy

**Configuration-First:**
```yaml
# ~/.agentwire/config.yaml
agent:
  type: "auto"  # "claude", "opencode", or "auto"
  command: "claude --dangerously-skip-permissions"

  claude:
    permissions:
      mode: "bypass"  # "bypass" | "prompted" | "restricted"
      hooks_enabled: true

  opencode:
    model: null  # Default model
    role: null  # Default role name

  fallback:
    use_agentwire_hooks: true
    use_agentwire_permissions: true
    warn_on_missing: true
```

**Auto-Detection Fallback:**
```python
def detect_agent_type(command: str) -> str:
    if "claude" in command.lower():
        return "claude"
    elif "opencode" in command.lower():
        return "opencode"
    # Check which command exists
    if shutil.which("claude"):
        return "claude"
    if shutil.which("opencode"):
        return "opencode"
    return "claude"  # Default for backward compatibility
```

### 2. Capability Profiles

```python
@dataclass
class AgentCapabilities:
    """Capabilities discovered for an agent type."""
    supports_hooks: bool
    supports_permissions: bool
    supports_tools_flag: bool
    supports_disallowed_tools: bool
    supports_system_prompt: bool
    supports_session_id: bool
    supports_fork_session: bool
    has_builtin_roles: bool
    supports_model_flag: bool

CLAUDE_CAPABILITIES = AgentCapabilities(
    supports_hooks=True,
    supports_permissions=True,
    supports_tools_flag=True,
    supports_disallowed_tools=True,
    supports_system_prompt=True,
    supports_session_id=True,
    supports_fork_session=True,
    has_builtin_roles=False,
    supports_model_flag=True,
)

OPENCODE_CAPABILITIES = AgentCapabilities(
    supports_hooks=False,  # Plugin system exists, but no permission hooks
    supports_permissions=False,  # Has permission config, but not hook system
    supports_tools_flag=False,  # No --tools flag
    supports_disallowed_tools=False,
    supports_system_prompt=True,  # Via config
    supports_session_id=False,
    supports_fork_session=False,
    has_builtin_roles=True,  # OpenCode has agent system
    supports_model_flag=True,
)
```

### 3. Command Builder Pattern

```python
class AgentCommandBuilder:
    """Build agent commands with conditional flags based on capabilities."""

    def __init__(self, agent_type: str, capabilities: AgentCapabilities):
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.parts = []

    def add_permissions(self, mode: str):
        if self.agent_type == "claude":
            if mode == "bypass":
                self.parts.append("--dangerously-skip-permissions")
        elif self.agent_type == "opencode":
            # OpenCode doesn't have permission flags
            pass  # Use AgentWire permission system

    def add_tools(self, tools: list[str]):
        if self.capabilities.supports_tools_flag:
            self.parts.extend(["--tools", ",".join(tools)])

    def add_disallowed_tools(self, tools: list[str]):
        if self.capabilities.supports_disallowed_tools:
            self.parts.extend(["--disallowedTools", ",".join(tools)])

    def add_system_prompt(self, prompt: str):
        if self.capabilities.supports_system_prompt:
            escaped = prompt.replace('"', '\\"')
            self.parts.append(f'--append-system-prompt "{escaped}"')
```

### 4. Session Type Mapping

| AgentWire Type | Claude Code Mode | OpenCode Mode | Implementation |
|----------------|-----------------|---------------|----------------|
| `bare` | N/A | N/A | No agent, tmux only |
| `standard` | `claude-bypass` | AgentWire permission system | Universal type |
| `worker` | `claude-restricted` | OpenCode worker agent | Universal type |
| `voice` | `claude-prompted` | OpenCode voice agent | Universal type |
| `claude-bypass` | `--dangerously-skip-permissions` | AgentWire hooks + allow-all | Legacy (maps to standard) |
| `claude-prompted` | Permission hooks | AgentWire hooks | Legacy (maps to voice) |
| `claude-restricted` | `--tools Bash` | OpenCode worker | Legacy (maps to worker) |

**Universal Types:**
New types that work with both agents:
- `standard` - Full agent capabilities (orchestrator mode)
- `worker` - No AskUserQuestion, no voice
- `voice` - Voice-enabled orchestrator with permissions

Legacy `claude-*` types still work for backward compatibility but are mapped to universal equivalents.

### 5. Role System Adaptation

**For Claude Code:**
```python
# Build command with flags
merged = merge_roles(roles)
if merged.tools:
    cmd_parts.append(f"--tools {','.join(merged.tools)}")
if merged.disallowed_tools:
    cmd_parts.append(f"--disallowedTools {','.join(merged.disallowed_tools)}")
if merged.instructions:
    cmd_parts.append(f'--append-system-prompt "{merged.instructions}"')
```

**For OpenCode:**
```python
# Create agent config file
agent_config = {
    "mode": "primary",
    "permission": {
        "question": "deny" if "AskUserQuestion" in merged.disallowed_tools else "allow"
    },
    "tools": {
        tool.lower(): True for tool in merged.tools
    }
}

# Prepend instructions to first message
if merged.instructions:
    first_message = f"{merged.instructions}\n\n---\n\n{user_message}"
```

### 6. Hook Fallback System

**Problem:** OpenCode doesn't have Claude Code's permission hooks.

**Solution:** Multi-tier hook system

```python
class HookInstaller:
    """Install hooks for appropriate agent type."""

    def install_session_hooks(self, session_name: str):
        if self.agent_type == "claude":
            self._install_claude_hooks(session_name)
        else:
            # Use AgentWire hooks at tmux level
            self._install_agentwire_hooks(session_name)

    def _install_agentwire_hooks(self, session_name: str):
        # Install tmux hooks that intercept before-send-keys
        subprocess.run([
            "tmux", "set-hook", "-t", session_name,
            "before-send-keys",
            f"run-shell '{agentwire} validate-command \"#{{command}}\"'"
        ])
```

**Hook Locations:**
1. **Claude Code:** `~/.claude/hooks/` (PreToolUse, PermissionRequest)
2. **OpenCode:** `~/.agentwire/hooks/` (tmux-level via `before-send-keys`)
3. **AgentWire Universal:** Cross-agent safety system

### 7. Permission System Fallback

```python
class PermissionManager:
    """Manage permissions independently of agent capabilities."""

    def request_permission(self, session_name: str, operation: str) -> bool | None:
        """Request permission for an operation.

        Returns:
            - None: Use agent's native permission system
            - True: Permission granted
            - False: Permission denied
        """
        # Use native system if available (Claude Code with permissions)
        if self.agent_type == "claude" and not self.bypass_permissions:
            return None  # Let Claude Code handle it

        # Use AgentWire permission system via portal
        portal_url = self.config.portal.url
        response = requests.post(
            f"{portal_url}/api/permissions/request",
            json={"session": session_name, "operation": operation},
            timeout=30
        )
        return response.json().get("granted", False)
```

---

## Implementation Plan

### Wave 1: Agent Detection & Configuration (BLOCKING)

**Goal:** Detect which AI agent is configured and load appropriate capabilities.

**Tasks:**
- [ ] Create `AgentInfo` class with type, capabilities, and config
- [ ] Update `config.py` to support new agent section structure
- [ ] Implement `detect_agent_type()` function with auto-detection
- [ ] Create capability profiles for Claude and OpenCode
- [ ] Add config migration utility (`agentwire migrate-config`)
- [ ] Update `agentwire init` to select agent type
- [ ] Update `agentwire doctor` to check agent configuration

**Files:**
- `agentwire/config.py` - Add AgentInfo class, parse new agent section
- `agentwire/utils/migration.py` - New file for config migration
- `agentwire/__main__.py` - Update init/doctor commands

**Testing:**
- [ ] Test auto-detection from command string
- [ ] Test config migration from legacy format
- [ ] Test manual agent type selection

**Success Criteria:**
- AgentWire can detect whether user is using Claude or OpenCode
- Config includes agent type and capabilities
- Migration command converts legacy configs without data loss

---

### Wave 2: Command Builder & Feature Gating

**Goal:** Build agent commands with conditional flags based on capabilities.

**Tasks:**
- [ ] Implement `AgentCommandBuilder` class
- [ ] Implement `AgentFeatureGate` class
- [ ] Update `_build_claude_cmd()` to use builder pattern
- [ ] Add feature checks in all session creation commands
- [ ] Add warning system for missing features

**Files:**
- `agentwire/__main__.py` - Replace `_build_claude_cmd()` with `_build_agent_command()`
- `agentwire/agents/base.py` - Add AgentInfo integration

**Testing:**
- [ ] Test building Claude commands with all flags
- [ ] Test building OpenCode commands (no unsupported flags)
- [ ] Test warning messages when features are missing

**Success Criteria:**
- AgentWire correctly adds flags only when agent supports them
- Warnings shown when using features not supported by current agent

---

### Wave 3: Session Type Normalization

**Goal:** Create universal session types that work with both agents.

**Tasks:**
- [ ] Add universal session types (standard, worker, voice) to SessionType enum
- [ ] Implement type normalization logic (legacy types → universal)
- [ ] Update `.agentwire.yml` parsing to support universal types
- [ ] Add backward compatibility layer for legacy `claude-*` types
- [ ] Update session creation API to handle universal types

**Files:**
- `agentwire/project_config.py` - Update SessionType enum
- `agentwire/__main__.py` - Add `normalize_session_type()` function

**Testing:**
- [ ] Test creating sessions with universal types
- [ ] Test legacy `claude-bypass` sessions still work
- [ ] Test OpenCode sessions with `standard` type

**Success Criteria:**
- Users can use universal types regardless of agent
- Legacy types continue to work for backward compatibility

---

### Wave 4: Hook & Permission Fallbacks

**Goal:** Implement AgentWire-level hooks when agent doesn't support them.

**Tasks:**
- [ ] Implement `HookInstaller` class with agent-specific logic
- [ ] Implement `PermissionManager` class
- [ ] Create AgentWire hooks in `~/.agentwire/hooks/`
- [ ] Implement tmux-level command interception (`before-send-keys`)
- [ ] Add portal permission API for AgentWire permission system

**Files:**
- `agentwire/hooks/__init__.py` - Expand to support AgentWire hooks
- `agentwire/server.py` - Add permission API endpoints
- `agentwire/agents/tmux.py` - Integrate hook installation
- New: `agentwire/permissions.py` - Permission manager

**Testing:**
- [ ] Test Claude Code hooks still install correctly
- [ ] Test AgentWire hooks install for OpenCode sessions
- [ ] Test permission requests via portal for OpenCode

**Success Criteria:**
- Damage control works with both Claude Code and OpenCode
- Permission dialogs work via AgentWire portal for OpenCode

---

### Wave 5: Role Filtering for OpenCode

**Goal:** Implement role-based restrictions when agent doesn't support `--tools` flag.

**Tasks:**
- [ ] Implement `RoleFilter` class for output filtering
- [ ] Add role instruction prepending to first message
- [ ] Update role loading to work with both agents
- [ ] Create OpenCode agent configs for agentwire and worker roles

**Files:**
- `agentwire/roles/__init__.py` - Add RoleFilter class
- `agentwire/__main__.py` - Integrate role filtering into message sending
- `agentwire/agents/opencode.py` - New file for OpenCode agent configs

**Testing:**
- [ ] Test worker role with OpenCode (no AskUserQuestion)
- [ ] Test role instructions are prepended correctly
- [ ] Test tool whitelist with Claude Code

**Success Criteria:**
- Workers obey role restrictions regardless of agent type
- Role instructions are applied to both Claude Code and OpenCode

---

### Wave 6: Documentation & Testing

**Goal:** Comprehensive docs and tests for multi-agent support.

**Tasks:**
- [ ] Update README with OpenCode requirements and setup
- [ ] Create OPENCODE_INTEGRATION.md guide
- [ ] Write unit tests for all new components
- [ ] Write integration tests for both agents
- [ ] Test migration from Claude to OpenCode
- [ ] Update troubleshooting guide

**Files:**
- `README.md` - Update agent requirements section
- `docs/OPENCODE_INTEGRATION.md` - New guide
- `docs/CONFIGURATION.md` - New config reference
- `tests/test_agent_info.py` - New test file
- `tests/test_command_builder.py` - New test file
- `tests/test_multi_agent.py` - Integration tests

**Testing:**
- [ ] All unit tests pass
- [ ] Integration tests pass for both Claude and OpenCode
- [ ] Manual testing of all session types with both agents
- [ ] Migration test from existing Claude Code setup to OpenCode

**Success Criteria:**
- Users can switch between Claude Code and OpenCode by changing one config value
- All features work seamlessly with both agents
- Clear documentation for OpenCode setup

---

## Configuration Reference

### Global Config (`~/.agentwire/config.yaml`)

```yaml
agent:
  # Agent type: "claude", "opencode", or "auto"
  type: "auto"

  # Command template (supports placeholders: {name}, {path}, {model})
  command: "claude --dangerously-skip-permissions"

  claude:
    # Claude Code specific settings
    permissions:
      mode: "bypass"  # "bypass" | "prompted" | "restricted"
      hooks_enabled: true
    session_id: null  # Auto-generated if null

  opencode:
    # OpenCode specific settings
    model: null  # Default model (sonnet, opus, haiku)
    role: null  # Default role name
    config_path: null  # Path to opencode config file

  fallback:
    # Use AgentWire hooks when agent doesn't support them
    use_agentwire_hooks: true
    # Use AgentWire permission system when agent doesn't have one
    use_agentwire_permissions: true
    # Implement role filtering in AgentWire CLI when agent doesn't support --tools
    implement_role_filtering: true
    # Prepend role instructions to prompts when agent doesn't support system prompts
    prepend_role_instructions: true
    # Log warnings when features are unavailable
    warn_on_missing: true
```

### Project Config (`.agentwire.yml`)

```yaml
# Session type (agent-agnostic)
type: "standard"  # "bare" | "standard" | "worker" | "voice"

# Agent-specific overrides (optional)
agent:
  claude:
    permissions:
      mode: "bypass"  # Override global setting
  opencode:
    role: "developer"  # Use specific OpenCode role

# Roles (composable, work with both agents)
roles:
  - agentwire
  - custom-role

# Voice config
voice: "dotdev"
```

---

## Migration Guide

### For Existing Claude Code Users

When upgrading, AgentWire will auto-migrate:

```bash
$ agentwire doctor
⚠️  Configuration migration needed

Your configuration uses legacy Claude Code-specific settings.
AgentWire now supports multiple AI agents.

Run: agentwire migrate-config
```

```bash
$ agentwire migrate-config
✓ Detected agent: claude
✓ Migrated config to multi-agent format
✓ Old config backed up to ~/.agentwire/config.yaml.backup
✓ You can still use Claude Code exactly as before

Changes made:
- Added agent.type: "claude"
- Added agent.claude.permissions section
- Added agent.fallback section

Your existing sessions will continue to work without changes.
```

### Switching to OpenCode

```bash
# 1. Install OpenCode
npm install -g @opencode-ai/cli

# 2. Update AgentWire config
$ cat > ~/.agentwire/config.yaml <<EOF
agent:
  type: "opencode"
  command: "opencode"
  opencode:
    model: "sonnet"
  fallback:
    use_agentwire_hooks: true
    use_agentwire_permissions: true
EOF

# 3. Create OpenCode agent configs
$ mkdir -p ~/.config/opencode/agents

# Create agentwire agent
$ cat > ~/.config/opencode/agents/agentwire.md <<'EOF'
---
description: Main orchestrator for AgentWire voice interface
mode: primary
permission:
  "*": "allow"
tools:
  write: true
  edit: true
  bash: true
  question: true
---

You are AgentWire orchestrator. Coordinate tasks and delegate to workers as needed.
EOF

# Create worker agent
$ cat > ~/.config/opencode/agents/worker.md <<'EOF'
---
description: Worker pane (no voice, no questions)
mode: subagent
permission:
  question: deny
tools:
  write: true
  edit: true
  bash: true
  question: false
---

Worker agent. Execute tasks delegated by orchestrator without voice or user questions.
EOF

# 4. Test with a new session
$ agentwire new -s test-opencode
ℹ️  Using agent: opencode
ℹ️  OpenCode doesn't support --tools flag - using AgentWire role filtering
ℹ️  OpenCode doesn't support permission dialogs - using AgentWire permission system
✓ Created session 'test-opencode'

# 5. Verify it works
$ agentwire output -s test-opencode -n 20
# Should see OpenCode responding

# 6. If happy, update default session type in project
$ echo 'type: "standard"' >> ~/projects/myproject/.agentwire.yml
```

---

## Feature Comparison

| Feature | Claude Code | OpenCode | AgentWire Support |
|---------|-------------|----------|-------------------|
| **CLI** | ✅ | ✅ | Both via agent.type |
| **Permissions** | Ask/deny | Allow/ask/deny | Both via hooks/config |
| **Tool Control** | `--tools`, `--disallowedTools` | Agent config | AgentWire role filtering |
| **System Prompt** | `--append-system-prompt` | Config | Both (prepend or flag) |
| **Session Types** | Hardcoded | Agent system | Universal types |
| **Hooks** | PreToolUse, PermissionRequest | Plugin system | Fallbacks + AgentWire hooks |
| **Permission Dialogs** | Built-in | No | AgentWire portal |
| **Damage Control** | ✅ (300+ patterns) | ✅ (plugins) | Both via AgentWire hooks |
| **History** | `~/.claude/history.jsonl` | Session API | Both via AgentWire wrapper |
| **Fork Session** | `--resume --fork-session` | API call | Both (fork worktree) |
| **Multiple Agents** | No | Yes (primary/subagent) | Via AgentWire roles |
| **HTTP API** | No | Yes | Only for OpenCode |
| **Open Source** | No | Yes (MIT) | N/A |

---

## Success Criteria

- [ ] Users can switch between Claude Code and OpenCode by changing `agent.type` in config
- [ ] Session types work identically for both agents (standard, worker, voice)
- [ ] Role system works for both agents (tool restrictions, instructions)
- [ ] Permission dialogs work via AgentWire portal for OpenCode
- [ ] Damage control works for both agents (via AgentWire hooks)
- [ ] History/fork works for both agents
- [ ] Clear warnings shown when using features not supported by current agent
- [ ] Existing Claude Code users can migrate without breaking changes
- [ ] OpenCode users get full feature parity with Claude Code
- [ ] Documentation covers both Claude Code and OpenCode setup
- [ ] All tests pass (unit + integration)

---

## Known Limitations

1. **No OpenCode permission hooks** - Permission dialogs will be AgentWire-managed, not native to OpenCode
2. **No OpenCode `--tools` flag** - Role filtering implemented in AgentWire CLI
3. **HTTP API only for OpenCode** - Claude Code still uses CLI spawning
4. **OpenCode server required for best experience** - Can use CLI, but loses session management
5. **AgentWire hooks limited to tmux-level** - Can't inspect OpenCode internal state like Claude Code hooks

---

## Future Enhancements

1. **OpenCode plugin for native permission integration** - Use plugin system instead of AgentWire hooks
2. **OpenCode HTTP API for all agents** - Unify portal communication
3. **AgentWire hooks system** - Create independent hook system that works with any agent
4. **Multi-agent session mixing** - Allow Claude Code sessions and OpenCode sessions to coexist
5. **Runtime agent switching** - Switch agents mid-session (e.g., use Claude for one task, OpenCode for another)
