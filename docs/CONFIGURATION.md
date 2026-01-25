# AgentWire Multi-Agent Configuration Reference

**Complete reference for configuring AgentWire with Claude Code or OpenCode.**

## Agent Detection

### Config-Based Detection

```yaml
# ~/.agentwire/config.yaml
agent:
  type: "opencode"  # "claude", "opencode", or "auto"
  command: "opencode"
```

### Auto-Detection Logic

When `type: "auto"` or not specified:

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

## Session Types

### Universal Session Types

| Type | Description | Claude Code Mode | OpenCode Mode | Voice |
|-------|-------------|-----------------|---------------|-------|
| `bare` | No agent, tmux only | N/A | N/A | ❌ |
| `standard` | Full agent capabilities | `claude-bypass` | Agent config | ✅ |
| `worker` | No AskUserQuestion, no voice | `claude-restricted` | Worker agent | ❌ |
| `voice` | Voice with permission prompts | `claude-prompted` | Permission config | ✅ |

### Legacy Session Types (Backward Compatible)

| Type | Description | Maps To |
|-------|-------------|----------|
| `claude-bypass` | Full automation (Claude) | `standard` |
| `claude-prompted` | Permission dialogs (Claude) | `voice` |
| `claude-restricted` | Say-only (Claude) | `worker` |
| `opencode-standard` | OpenCode full access | `standard` |
| `opencode-worker` | OpenCode worker | `worker` |
| `opencode-voice` | OpenCode voice | `voice` |

### Project Config

```yaml
# ~/projects/myproject/.agentwire.yml
type: "standard"  # Session type

roles:
  - agentwire
  - custom-role

voice: "dotdev"
```

## Claude Code Configuration

### CLI Flags

| Flag | Session Types | Purpose |
|-------|---------------|---------|
| `--dangerously-skip-permissions` | claude-bypass | Bypass all permission prompts |
| `--tools tool1,tool2` | All (except bare) | Whitelist specific tools |
| `--disallowedTools tool1` | All (except bare) | Blacklist specific tools |
| `--append-system-prompt "text"` | All (except bare) | Add role instructions |
| `--model sonnet/opus/haiku` | All (except bare) | Override model |
| `--resume <session-id>` | Fork sessions | Resume from history |
| `--fork-session` | Fork sessions | Fork into new session |

### Global Config

```yaml
# ~/.agentwire/config.yaml
agent:
  type: "claude"
  command: "claude --dangerously-skip-permissions"

  claude:
    permissions:
      mode: "bypass"  # "bypass" | "prompted" | "restricted"
      hooks_enabled: true
    session_id: null  # Auto-generated if null

  fallback:
    use_agentwire_hooks: false  # Not needed, Claude has hooks
    use_agentwire_permissions: false
    warn_on_missing: true
```

### Roles Format

```yaml
# agentwire/roles/custom-role.md
---
name: custom-role
description: Custom role description
disallowedTools: AskUserQuestion
model: sonnet
---

## Role instructions

You are a specialized agent for...
```

## OpenCode Configuration

### Permission States

| State | Behavior |
|-------|----------|
| `allow` | Tool runs without approval |
| `ask` | User prompted (once/always/reject) |
| `deny` | Tool is blocked |

### Permission Config

```yaml
# ~/.config/opencode/agents/agentwire.md
---
description: Main orchestrator
mode: primary
permission:
  "*": "allow"  # Global default

  # Tool-specific
  bash:
    "*": "ask"
    "git *": "allow"
    "rm *": "deny"

  question: "allow"
tools:
  write: true
  edit: true
  bash: true
  question: true
---
```

### Tool Control

```yaml
tools:
  write: true   # Write tool
  edit: true    # Edit tool
  bash: true    # Bash tool
  grep: true    # Grep tool
  glob: true    # Glob tool
  question: false  # AskUserQuestion
  task: true    # Task (subagents)
  webfetch: false  # WebFetch
  websearch: false  # WebSearch
```

### Agent Config Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Human-readable description (required) |
| `mode` | string | `primary` or `subagent` (required) |
| `permission` | object | Permission rules |
| `tools` | object | Enable/disable specific tools |
| `model` | string | Override model |
| `temperature` | number | LLM randomness (0.0-1.0) |
| `maxSteps` | number | Max agentic iterations |
| `prompt` | string/file | Custom system prompt |
| `hidden` | boolean | Hide from @ autocomplete |

### Global Config

```yaml
# ~/.agentwire/config.yaml
agent:
  type: "opencode"
  command: "opencode"

  opencode:
    model: "anthropic/claude-sonnet-4-20250514"  # Default model
    role: null  # Default role name
    use_http_api: false  # Use opencode serve instead of spawning

  fallback:
    use_agentwire_hooks: true  # Install tmux-level hooks
    use_agentwire_permissions: true  # Use portal permission dialogs
    implement_role_filtering: true  # Filter agent output
    prepend_role_instructions: true  # Add role instructions to prompts
    warn_on_missing: true
```

## Fallback System

### AgentWire Hooks

When agent doesn't support native hooks, AgentWire installs tmux-level hooks:

```bash
# Hook location
~/.agentwire/hooks/before-send-keys.sh

# Hook execution
tmux sends-keys → AgentWire hook → damage control check → allow/deny
```

### Damage Control

Applies to both Claude Code and OpenCode:

**Protected:**
- 100+ bash command patterns
- 66 zero-access paths
- 30+ read-only paths
- 20+ no-delete paths

**Checking:**
```bash
# Test command
agentwire safety check "rm -rf /"

# Check status
agentwire safety status

# Query logs
agentwire safety logs --tail 20
```

### Permission Dialogs

When agent doesn't have native permission dialogs:

```
Agent detects operation → Portal shows dialog → User clicks allow/deny → AgentWire returns decision to tmux
```

**Endpoints:**
- `POST /api/permissions/request` - Request permission
- `POST /api/permissions/respond` - User decision

## Role System

### Merging Logic

**Tools:** Union of all role tools
**Disallowed tools:** Intersection (only block if ALL agree)
**Instructions:** Concatenated with newlines
**Model:** Last non-None wins

### Example

```python
role1 = {
    "tools": ["Bash", "Edit"],
    "disallowed_tools": ["AskUserQuestion"],
    "model": "sonnet"
}

role2 = {
    "tools": ["Bash", "Write"],
    "instructions": "Additional context"
}

merged = merge_roles([role1, role2])
# Result:
#   tools = {"Bash", "Edit", "Write"}
#   disallowed_tools = {"AskUserQuestion"}
#   instructions = role1.instructions + "\n\n" + role2.instructions
#   model = "sonnet"
```

## Feature Capabilities

### Claude Code Capabilities

```python
CLAUDE_CAPABILITIES = {
    "supports_hooks": True,  # PreToolUse, PermissionRequest
    "supports_permissions": True,
    "supports_tools_flag": True,
    "supports_disallowed_tools": True,
    "supports_system_prompt": True,
    "supports_session_id": True,
    "supports_fork_session": True,
    "has_builtin_roles": False,  # AgentWire provides roles
    "supports_model_flag": True,
}
```

### OpenCode Capabilities

```python
OPENCODE_CAPABILITIES = {
    "supports_hooks": False,  # Plugin system exists, but no permission hooks
    "supports_permissions": False,  # Has permission config, not hook system
    "supports_tools_flag": False,  # No --tools flag
    "supports_disallowed_tools": False,
    "supports_system_prompt": True,  # Via config
    "supports_session_id": False,
    "supports_fork_session": False,
    "has_builtin_roles": True,  # OpenCode has agent system
    "supports_model_flag": True,
}
```

## Environment Variables

### OpenCode Variables

| Variable | Purpose | Example |
|-----------|---------|---------|
| `OPENCODE` | Set when running in OpenCode | `1` |
| `OPENCODE_CONFIG` | Custom config file path | `~/.config/opencode/config.json` |
| `OPENCODE_CONFIG_DIR` | Custom config directory | `~/.config/opencode` |
| `OPENCODE_CONFIG_CONTENT` | Inline JSON config | `{"agent": {...}}` |
| `OPENCODE_PERMISSION` | Inline permissions | `{"bash":"allow","edit":"deny"}` |
| `OPENCODE_DISABLE_CLAUDE_CODE` | Disable Claude Code file reading | `1` |
| `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT` | Disable CLAUDE.md fallback | `1` |
| `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` | Disable skills fallback | `1` |
| `OPENCODE_SERVER_PASSWORD` | HTTP basic auth password | `secret` |
| `OPENCODE_SERVER_USERNAME` | HTTP basic auth username | `opencode` |
| `OPENCODE_CLIENT` | Client identifier | `cli` |

### Claude Code Variables

| Variable | Purpose |
|-----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `CLAUDE_MODEL` | Default model |

## Command Mapping

| AgentWire Command | Claude Code | OpenCode |
|-----------------|-------------|----------|
| `agentwire new -s name` | `claude --dangerously-skip-permissions` | `opencode --agent agentwire` |
| `agentwire spawn` | `claude --dangerously-skip-permissions --roles worker` | `opencode --agent worker` |
| `agentwire history resume <id>` | `claude --resume <id> --fork-session` | `POST /session/<id>/fork` |
| `agentwire send -s name "msg"` | Send to tmux session | `POST /session/<id>/message` |

## Migration

### Config Migration

```bash
# Auto-migrate legacy config
agentwire migrate-config

# Manual migration steps
# 1. Backup config
cp ~/.agentwire/config.yaml ~/.agentwire/config.yaml.backup

# 2. Add agent section
# See "Claude Code Configuration" or "OpenCode Configuration" above

# 3. Test
agentwire new -s test
```

### Role Migration

```bash
# Claude Code roles work with OpenCode as-is
# No changes needed for basic roles

# For advanced control, convert to OpenCode format:
cp agentwire/roles/worker.md ~/.config/opencode/agents/
# Then add frontmatter:
---
description: Worker pane
mode: subagent
permission:
  question: deny
tools:
  write: true
  edit: true
  bash: true
  question: false
---
```

## Troubleshooting

### Agent Detection Issues

```bash
# Check which agent is detected
agentwire doctor | grep "Agent type"

# Manually set agent
cat ~/.agentwire/config.yaml | grep "agent.type"

# Verify command works
claude --version  # or opencode --version
```

### Permission Dialog Not Appearing

```bash
# Check hooks are installed
agentwire hooks status

# Verify fallback is enabled
cat ~/.agentwire/config.yaml | grep use_agentwire_permissions

# Check portal is running
agentwire portal status
```

### Role Restrictions Not Working

```bash
# Verify role config exists
ls ~/.config/opencode/agents/

# Check role filtering is enabled
cat ~/.agentwire/config.yaml | grep implement_role_filtering

# Test safety directly
agentwire safety check "operation-to-test"
```

## Best Practices

### 1. Use Universal Session Types

Prefer `standard`, `worker`, `voice` over `claude-*` types for agent-agnostic behavior.

### 2. Enable AgentWire Fallbacks

```yaml
agent:
  fallback:
    use_agentwire_hooks: true
    use_agentwire_permissions: true
    implement_role_filtering: true
```

### 3. Configure Agents Properly

For Claude Code: Ensure hooks are installed via `agentwire hooks install`

For OpenCode: Create agent configs with appropriate permissions

### 4. Test After Changes

Always test after switching agents:
```bash
agentwire new -s test
agentwire send -s test "Hello!"
agentwire output -s test -n 20
```

### 5. Use `agent.type: "auto"` During Development

Lets AgentWire auto-detect, useful when testing both agents.
