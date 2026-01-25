# AgentWire Multi-Agent Support Architecture

Design for making AgentWire work seamlessly with both Claude Code and OpenCode through conditional logic.

## Executive Summary

AgentWire currently assumes Claude Code as the sole AI agent. This architecture introduces an abstraction layer that:

1. **Detects** which AI agent the user is using
2. **Adapts** behavior based on agent capabilities
3. **Maps** Claude Code features to OpenCode equivalents
4. **Gracefully degrades** when features are unavailable
5. **Maintains** backward compatibility for existing users

## 1. Agent Detection Strategy

### 1.1 Configuration-Based Detection

**Primary Method:** Explicit configuration in `config.yaml`

```yaml
agent:
  type: "claude"  # or "opencode", "auto"
  command: "claude --dangerously-skip-permissions"
```

### 1.2 Auto-Detection Fallback

If `type: "auto"` or not specified:

```python
def detect_agent_type(command: str) -> str:
    """Auto-detect agent type from command string."""
    if "claude" in command.lower():
        return "claude"
    elif "opencode" in command.lower():
        return "opencode"
    # Fallback to checking which command exists
    if shutil.which("claude"):
        return "claude"
    if shutil.which("opencode"):
        return "opencode"
    return "claude"  # Default for backward compatibility
```

### 1.3 Runtime Capability Probing

For maximum compatibility, probe agent capabilities at runtime:

```python
@dataclass
class AgentCapabilities:
    """Capabilities discovered for an agent type."""
    supports_hooks: bool = False
    supports_permissions: bool = False
    supports_tools_flag: bool = False
    supports_disallowed_tools: bool = False
    supports_system_prompt: bool = False
    supports_session_id: bool = False
    supports_fork_session: bool = False
    has_builtin_roles: bool = False
    supports_model_flag: bool = False

# Predefined capability profiles
CLAUDE_CAPABILITIES = AgentCapabilities(
    supports_hooks=True,
    supports_permissions=True,
    supports_tools_flag=True,
    supports_disallowed_tools=True,
    supports_system_prompt=True,
    supports_session_id=True,
    supports_fork_session=True,
    has_builtin_roles=False,  # AgentWire provides roles
    supports_model_flag=True,
)

OPENCODE_CAPABILITIES = AgentCapabilities(
    supports_hooks=False,  # Unknown - assume false
    supports_permissions=False,  # No permission system
    supports_tools_flag=False,  # No --tools flag
    supports_disallowed_tools=False,
    supports_system_prompt=True,  # Assume supports system prompt
    supports_session_id=False,  # Unknown
    supports_fork_session=False,
    has_builtin_roles=True,  # OpenCode has its own role system
    supports_model_flag=True,  # Assume supports --model
)
```

### 1.4 Configuration File Structure

Updated `~/.agentwire/config.yaml`:

```yaml
agent:
  # Agent type: "claude", "opencode", or "auto" (detect from command)
  type: "auto"

  # Command to start agent (supports placeholders)
  command: "claude --dangerously-skip-permissions"

  # Agent-specific settings
  claude:
    # Claude Code specific settings
    permissions:
      mode: "prompted"  # "bypass" | "prompted" | "restricted"
      hooks_enabled: true
    session_id: null  # Auto-generated if null
    fork_session: false

  opencode:
    # OpenCode specific settings
    model: null  # Default model
    role: null  # Default role name

  # Fallback behavior for missing features
  fallback:
    # AgentWire implements hooks if agent doesn't support them
    agentwire_hooks: true
    # AgentWire implements permission dialogs if agent doesn't
    agentwire_permissions: true
    # Log warnings when features are unavailable
    warn_on_missing: true
```

## 2. Feature Gating Pattern

### 2.1 Capability Registry Pattern

```python
class AgentFeatureGate:
    """Context manager for feature gating based on agent capabilities."""

    def __init__(self, capabilities: AgentCapabilities):
        self.capabilities = capabilities
        self.warnings = []

    def has_feature(self, feature: str) -> bool:
        """Check if agent supports a feature."""
        return getattr(self.capabilities, f"supports_{feature}", False)

    def require_feature(self, feature: str, warning: str | None = None) -> bool:
        """Check and optionally warn about missing feature."""
        if not self.has_feature(feature):
            if warning:
                self.warnings.append(warning)
            return False
        return True

    def with_feature(self, feature: str, fallback_value=None):
        """Decorator for feature-specific code paths."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if self.has_feature(feature):
                    return func(*args, **kwargs)
                return fallback_value
            return wrapper
        return decorator
```

### 2.2 Usage Pattern

```python
# In CLI commands
def cmd_new(args):
    config = load_config()
    agent_info = AgentInfo.from_config(config)

    feature_gate = AgentFeatureGate(agent_info.capabilities)

    # Conditional feature usage
    if feature_gate.has_feature("tools_flag"):
        # Add --tools flag
        cmd_parts.extend(["--tools", ",".join(tools)])

    # Required features with warning
    if not feature_gate.require_feature(
        "permissions",
        "OpenCode doesn't support permission dialogs - using AgentWire permission system"
    ):
        # Use AgentWire's permission system instead
        install_agentwire_permissions()

    # Execute with warnings
    for warning in feature_gate.warnings:
        print(f"⚠️  {warning}")
```

### 2.3 Command Builder Pattern

```python
class AgentCommandBuilder:
    """Build agent commands with conditional flags based on capabilities."""

    def __init__(self, agent_type: str, capabilities: AgentCapabilities):
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.parts = []

    def add_base(self, command: str):
        """Add base command."""
        self.parts = [command]
        return self

    def add_permissions(self, mode: str):
        """Add permission flags (agent-specific)."""
        if self.agent_type == "claude":
            if mode == "bypass":
                self.parts.append("--dangerously-skip-permissions")
            # "prompted" and "restricted" use no flag (hooks handle it)
        elif self.agent_type == "opencode":
            # OpenCode doesn't have permission flags
            pass  # Use AgentWire permission system
        return self

    def add_tools(self, tools: list[str]):
        """Add tools whitelist."""
        if self.capabilities.supports_tools_flag:
            self.parts.extend(["--tools", ",".join(tools)])
        return self

    def add_disallowed_tools(self, tools: list[str]):
        """Add tools blacklist."""
        if self.capabilities.supports_disallowed_tools:
            self.parts.extend(["--disallowedTools", ",".join(tools)])
        return self

    def add_system_prompt(self, prompt: str):
        """Add system prompt."""
        if self.capabilities.supports_system_prompt:
            escaped = prompt.replace('"', '\\"')
            self.parts.append(f'--append-system-prompt "{escaped}"')
        return self

    def add_model(self, model: str | None):
        """Add model flag."""
        if model and self.capabilities.supports_model_flag:
            self.parts.append(f"--model {model}")
        return self

    def add_session_id(self, session_id: str):
        """Add session ID."""
        if self.capabilities.supports_session_id:
            self.parts.extend(["--session-id", session_id])
        return self

    def add_fork_session(self, from_session: str):
        """Add fork session flags."""
        if self.capabilities.supports_fork_session:
            self.parts.extend(["--resume", from_session, "--fork-session"])
        return self

    def build(self) -> str:
        """Build final command string."""
        return " ".join(self.parts)
```

## 3. Feature Mapping Matrix

### 3.1 CLI Flag Mapping

| Feature | Claude Code | OpenCode | AgentWire Fallback |
|---------|-------------|----------|-------------------|
| **Permissions** | `--dangerously-skip-permissions` | No flag | AgentWire hooks + tmux hooks |
| **Tools Whitelist** | `--tools Bash,Edit,Write` | No flag | AgentWire role filtering in CLI |
| **Tools Blacklist** | `--disallowedTools AskUserQuestion` | No flag | AgentWire role filtering in CLI |
| **System Prompt** | `--append-system-prompt "text"` | Unknown flag | Prepend to initial prompt |
| **Model Selection** | `--model sonnet` | Unknown flag | Config file only |
| **Session ID** | `--session-id <uuid>` | No flag | Generate AgentWire ID only |
| **Fork Session** | `--resume <id> --fork-session` | No flag | Clone worktree only |
| **Hooks** | `~/.claude/hooks/` | No hooks | AgentWire hooks in `~/.agentwire/hooks/` |
| **Permission Dialogs** | Claude Code permission prompt | No dialogs | AgentWire portal dialogs |

### 3.2 Session Type Mapping

| Session Type | Claude Code Mode | OpenCode Mode | AgentWire Behavior |
|-------------|-----------------|---------------|-------------------|
| `bare` | No Claude | No agent | Pure tmux session |
| `claude-bypass` | `--dangerously-skip-permissions` | No flag + AgentWire hooks | Unrestricted with damage control |
| `claude-prompted` | No flag (uses hooks) | No flag + AgentWire hooks | Permission dialogs via hooks |
| `claude-restricted` | `--tools Bash` | No flag + AgentWire hooks | Say-only, all other tools blocked |
| `opencode-standard` | N/A | Default mode | Standard OpenCode session |
| `opencode-worker` | N/A | Worker mode | No AskUserQuestion, no voice |
| `opencode-voice` | N/A | Voice mode | Full voice integration |

**Mapping Logic:**

```python
SESSION_TYPE_MAPPING = {
    # Claude types
    "bare": AgentType.CLAUDE,
    "claude-bypass": AgentType.CLAUDE,
    "claude-prompted": AgentType.CLAUDE,
    "claude-restricted": AgentType.CLAUDE,

    # OpenCode types (new)
    "opencode-standard": AgentType.OPENCODE,
    "opencode-worker": AgentType.OPENCODE,
    "opencode-voice": AgentType.OPENCODE,

    # Universal types (work with both)
    "standard": None,  # Use configured agent
    "worker": None,  # Worker mode (role-based)
    "voice": None,  # Voice mode (role-based)
}

def normalize_session_type(session_type: str, configured_agent: str) -> tuple[str, str]:
    """Normalize session type based on configured agent.

    Returns:
        (normalized_type, agent_type)
    """
    if session_type in SESSION_TYPE_MAPPING:
        mapped_agent = SESSION_TYPE_MAPPING[session_type]

        if mapped_agent is None:
            # Universal type - use configured agent
            return session_type, configured_agent
        elif mapped_agent != configured_agent:
            # Mismatch - warn and normalize
            print(f"⚠️  Session type '{session_type}' requires {mapped_agent}, but {configured_agent} is configured")
            print(f"   Mapping to equivalent {configured_agent} mode...")

            # Map to equivalent
            if session_type == "claude-bypass" and configured_agent == "opencode":
                return "opencode-standard", "opencode"
            elif session_type == "claude-restricted" and configured_agent == "opencode":
                return "opencode-worker", "opencode"
            # ... more mappings

        return session_type, mapped_agent

    # Unknown type - use as-is with configured agent
    return session_type, configured_agent
```

### 3.3 Role Mapping

| AgentWire Role | Claude Code | OpenCode | Compatibility |
|----------------|-------------|----------|---------------|
| `agentwire` | Full permissions | Full permissions | Both supported |
| `worker` | `--disallowedTools AskUserQuestion` | OpenCode worker role | Equivalent |
| `chatbot` | `--append-system-prompt` | OpenCode chatbot role | Map to system prompt |
| `voice` | TTS integration | TTS integration | Both supported |
| Custom roles | `--tools + --append-system-prompt` | OpenCode role file | Map flags to OpenCode roles |

## 4. Graceful Degradation Strategy

### 4.1 Hooks Scenario

**Problem:** User switches from Claude Code to OpenCode, Claude Code hooks in `~/.claude/hooks/` no longer work.

**Solution:** Multi-tier hook system

```python
class HookInstaller:
    """Install hooks for the appropriate agent type."""

    def __init__(self, agent_type: str):
        self.agent_type = agent_type

    def install_hooks(self, session_name: str):
        """Install hooks for the session."""
        if self.agent_type == "claude":
            self._install_claude_hooks(session_name)
        elif self.agent_type == "opencode":
            # OpenCode doesn't support hooks, use AgentWire hooks
            self._install_agentwire_hooks(session_name)

    def _install_claude_hooks(self, session_name: str):
        """Install Claude Code hooks in ~/.claude/hooks/."""
        claude_hooks_dir = Path.home() / ".claude" / "hooks"

        # Install pre-command hooks
        # Install permission hooks
        # Install damage control hooks
        pass

    def _install_agentwire_hooks(self, session_name: str):
        """Install AgentWire hooks in ~/.agentwire/hooks/."""
        agentwire_hooks_dir = Path.home() / ".agentwire" / "hooks"

        # Install tmux-level hooks
        # - Hook into tmux before-send-keys command
        # - Intercept and validate commands
        # - Use damage control patterns
        pass
```

**Implementation:**

1. **Claude Code:** Hooks in `~/.claude/hooks/` (PreToolUse, PreCommand)
2. **OpenCode:** Hooks at tmux level via `before-send-keys` hook
3. **AgentWire Universal:** Hooks in `~/.agentwire/hooks/` for cross-agent compatibility

### 4.2 Permissions Scenario

**Problem:** OpenCode doesn't have permission dialogs, AgentWire portal needs permission prompts for safety.

**Solution:** AgentWire permission system

```python
class PermissionManager:
    """Manage permissions independently of agent capabilities."""

    def request_permission(
        self,
        session_name: str,
        operation: str,
        details: dict,
        timeout: int = 30
    ) -> bool:
        """Request permission from user via portal.

        Returns:
            True if permission granted, False otherwise
        """
        # Check if agent has built-in permissions
        if self._agent_has_native_permissions():
            # Let agent handle it
            return None  # Indicate to use native system

        # Use AgentWire permission system
        return self._request_via_portal(session_name, operation, details)

    def _agent_has_native_permissions(self) -> bool:
        """Check if current agent has native permission system."""
        return self.agent_type == "claude" and not self.bypass_permissions

    def _request_via_portal(self, session_name: str, operation: str, details: dict) -> bool:
        """Send permission request to portal for user approval."""
        portal_url = self.config.get("portal", {}).get("url", "https://localhost:8765")

        payload = {
            "session": session_name,
            "operation": operation,
            "details": details,
            "timeout": timeout,
        }

        response = requests.post(
            f"{portal_url}/api/permissions/request",
            json=payload,
            timeout=timeout,
        )

        return response.json().get("granted", False)
```

### 4.3 Roles Scenario

**Problem:** User creates custom role with tool whitelist, OpenCode doesn't support `--tools` flag.

**Solution:** Role filtering in AgentWire CLI

```python
class RoleFilter:
    """Filter agent outputs based on role restrictions."""

    def __init__(self, session_name: str, roles: list[RoleConfig]):
        self.session_name = session_name
        self.roles = roles
        self.merged = merge_roles(roles)

    def should_intercept_tool_use(self, tool_name: str) -> bool:
        """Check if tool use should be intercepted based on role."""

        # Check disallowed tools
        if tool_name in self.merged.disallowed_tools:
            return True

        # Check whitelist (if specified)
        if self.merged.tools and tool_name not in self.merged.tools:
            return True

        return False

    def filter_output(self, output: str) -> tuple[str, bool]:
        """Filter agent output, returning (filtered_output, blocked).

        If a tool use is blocked, replace with warning message.
        """
        # Parse tool uses from output
        # Check each against role restrictions
        # Replace blocked uses with warnings
        pass

    def apply_role_instructions(self, prompt: str) -> str:
        """Prepend role instructions to prompt if agent doesn't support --append-system-prompt."""
        if not self.capabilities.supports_system_prompt:
            # Prepend to user prompt
            role_instructions = "\n\n".join([r.instructions for r in self.roles])
            return f"{role_instructions}\n\n---\n\n{prompt}"
        return prompt
```

## 5. Configuration Design

### 5.1 Updated Agent Config Section

```yaml
agent:
  # Agent type: "claude", "opencode", or "auto"
  type: "auto"

  # Command template with placeholders
  # Placeholders: {name}, {path}, {model}, {session_id}
  command: "claude --dangerously-skip-permissions"

  # Agent-specific settings
  claude:
    # Claude Code specific
    permissions:
      mode: "bypass"  # "bypass" | "prompted" | "restricted"
      hooks_enabled: true
    session_id: null  # Auto-generated UUID if null
    fork_session: false  # Enable fork session flag

  opencode:
    # OpenCode specific
    model: null  # Default model (sonnet, opus, haiku)
    role: null  # Default role name
    config_path: null  # Path to opencode config file

  # Fallback behavior
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

### 5.2 Project-Level Config

`.agentwire.yml`:

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
  - developer

# Voice config
voice: "default"
```

## 6. Session Type Mapping

### 6.1 Universal Session Types

New agent-agnostic session types:

```python
class SessionType(str, Enum):
    """Universal session types that work with multiple agents."""

    BARE = "bare"  # No agent, just tmux
    STANDARD = "standard"  # Full agent with all capabilities
    WORKER = "worker"  # Restricted: no AskUserQuestion, no voice
    VOICE = "voice"  # Voice-enabled orchestrator

    # Legacy Claude types (mapped for backward compatibility)
    CLAUDE_BYPASS = "claude-bypass"
    CLAUDE_PROMPTED = "claude-prompted"
    CLAUDE_RESTRICTED = "claude-restricted"

    # OpenCode specific
    OPENCODE_STANDARD = "opencode-standard"
    OPENCODE_WORKER = "opencode-worker"
    OPENCODE_VOICE = "opencode-voice"

    def to_agent_type(self, configured_agent: str) -> str:
        """Convert universal type to agent-specific type."""
        if self.value in ["bare", "standard", "worker", "voice"]:
            # Universal types work with any agent
            return self.value

        # Agent-specific types
        if self.value.startswith("claude-"):
            if configured_agent != "claude":
                print(f"⚠️  Session type '{self.value}' requires Claude, but {configured_agent} is configured")
            return "standard"  # Map to universal equivalent

        if self.value.startswith("opencode-"):
            if configured_agent != "opencode":
                print(f"⚠️  Session type '{self.value}' requires OpenCode, but {configured_agent} is configured")
            return "standard"

        return self.value
```

### 6.2 Type Mapping Matrix

| Universal Type | Claude | OpenCode | Notes |
|----------------|---------|----------|-------|
| `bare` | `bare` | `bare` | No agent |
| `standard` | `claude-bypass` | `opencode-standard` | Full capabilities |
| `worker` | `claude-restricted` | `opencode-worker` | No AskUserQuestion |
| `voice` | `claude-prompted` | `opencode-voice` | Voice orchestrator |

### 6.3 Migration Path for Existing Users

```python
def migrate_legacy_config(config_path: Path) -> dict:
    """Migrate legacy config to new agent-agnostic format."""
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    agent_section = data.get("agent", {})

    # Detect agent type from command
    command = agent_section.get("command", "claude --dangerously-skip-permissions")
    detected_type = detect_agent_type(command)

    # Add type field if missing
    if "type" not in agent_section:
        agent_section["type"] = detected_type

    # Add claude/opencode subsections
    if "claude" not in agent_section:
        agent_section["claude"] = {
            "permissions": {
                "mode": "bypass" if "--dangerously-skip-permissions" in command else "prompted",
                "hooks_enabled": True,
            }
        }

    if "opencode" not in agent_section:
        agent_section["opencode"] = {}

    # Add fallback section if missing
    if "fallback" not in agent_section:
        agent_section["fallback"] = {
            "use_agentwire_hooks": True,
            "use_agentwire_permissions": True,
        }

    data["agent"] = agent_section

    # Save migrated config
    with open(config_path, "w") as f:
        yaml.safe_dump(data, f)

    return data
```

## 7. Implementation Plan

### Phase 1: Agent Detection & Configuration (Week 1)

**Tasks:**
1. Add `AgentInfo` class to hold agent type and capabilities
2. Update `config.py` with new agent section structure
3. Implement auto-detection from command string
4. Create capability profiles for Claude and OpenCode
5. Add config migration utility for existing users

**Files to Modify:**
- `agentwire/config.py` - Add AgentInfo class
- `agentwire/__init__.py` - Export AgentInfo
- `agentwire/utils/migration.py` - New file for config migration

**Commands to Update:**
- `agentwire init` - Add agent type selection
- `agentwire doctor` - Check agent configuration

### Phase 2: Command Builder & Feature Gating (Week 2)

**Tasks:**
1. Implement `AgentCommandBuilder` class
2. Implement `AgentFeatureGate` class
3. Update `_build_claude_cmd()` to use builder pattern
4. Add feature checks in all CLI commands
5. Add warning system for missing features

**Files to Modify:**
- `agentwire/__main__.py` - Update command building
- `agentwire/agents/base.py` - Add AgentInfo integration
- `agentwire/agents/tmux.py` - Update command formatting

**Commands to Update:**
- `agentwire new`
- `agentwire recreate`
- `agentwire fork`
- `agentwire dev`

### Phase 3: Session Type Normalization (Week 3)

**Tasks:**
1. Implement universal session types
2. Add type normalization logic
3. Update `SessionType` enum
4. Update `.agentwire.yml` handling
5. Add backward compatibility layer for legacy types

**Files to Modify:**
- `agentwire/project_config.py` - Update SessionType enum
- `agentwire/__main__.py` - Add type normalization
- `agentwire/server.py` - Update session creation API

**Commands to Update:**
- All session creation commands

### Phase 4: Hook & Permission Fallbacks (Week 4)

**Tasks:**
1. Implement `HookInstaller` class
2. Implement `PermissionManager` class
3. Create AgentWire hooks in `~/.agentwire/hooks/`
4. Implement tmux-level command interception
5. Add portal permission dialog API

**Files to Modify:**
- `agentwire/hooks/__init__.py` - Expand hooks system
- `agentwire/server.py` - Add permission API endpoints
- `agentwire/agents/tmux.py` - Integrate hook installation

**New Files:**
- `agentwire/hooks/agentwire-hooks.py`
- `agentwire/permissions.py`

### Phase 5: Role Filtering (Week 5)

**Tasks:**
1. Implement `RoleFilter` class
2. Add output filtering logic
3. Implement role instruction prepending
4. Update role loading to work with both agents
5. Test role system with OpenCode

**Files to Modify:**
- `agentwire/roles/__init__.py` - Add RoleFilter
- `agentwire/__main__.py` - Integrate role filtering
- `agentwire/server.py` - Update role management API

### Phase 6: Documentation & Testing (Week 6)

**Tasks:**
1. Update documentation for multi-agent support
2. Write integration tests for both agents
3. Test migration from Claude to OpenCode
4. Test all feature fallback paths
5. Update troubleshooting guide

**Files to Modify:**
- `README.md` - Update agent requirements
- `docs/ARCHITECTURE.md` - Document agent abstractions
- `docs/MULTI-AGENT.md` - New documentation file
- `docs/TROUBLESHOOTING.md` - Add agent-specific issues

## 8. Code Examples

### 8.1 Agent Detection

```python
# agentwire/config.py

@dataclass
class AgentInfo:
    """Information about the configured AI agent."""

    type: str  # "claude" or "opencode"
    command: str
    capabilities: AgentCapabilities
    config: dict  # Agent-specific config section

    @classmethod
    def from_config(cls, config: Config) -> "AgentInfo":
        """Create AgentInfo from Config object."""
        agent_config = config.agent

        # Determine agent type
        agent_type = agent_config.get("type", "auto")
        if agent_type == "auto":
            agent_type = detect_agent_type(agent_config.command)

        # Get capabilities
        if agent_type == "claude":
            capabilities = CLAUDE_CAPABILITIES
            agent_specific = agent_config.get("claude", {})
        elif agent_type == "opencode":
            capabilities = OPENCODE_CAPABILITIES
            agent_specific = agent_config.get("opencode", {})
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

        return cls(
            type=agent_type,
            command=agent_config.command,
            capabilities=capabilities,
            config=agent_specific,
        )

def detect_agent_type(command: str) -> str:
    """Detect agent type from command string."""
    command_lower = command.lower()

    if "claude" in command_lower:
        return "claude"
    elif "opencode" in command_lower:
        return "opencode"

    # Check which command exists
    if shutil.which("claude"):
        return "claude"
    if shutil.which("opencode"):
        return "opencode"

    # Default to claude for backward compatibility
    return "claude"
```

### 8.2 Command Building

```python
# agentwire/__main__.py (updated _build_claude_cmd)

def _build_agent_command(
    agent_info: AgentInfo,
    session_type: SessionType,
    roles: list[RoleConfig] | None = None,
) -> str:
    """Build the agent command with appropriate flags.

    Args:
        agent_info: Agent information including type and capabilities
        session_type: Session execution mode
        roles: List of RoleConfig objects to apply

    Returns:
        The agent command string to execute, or empty string for bare sessions
    """
    if session_type == SessionType.BARE:
        return ""

    # Use command builder
    builder = AgentCommandBuilder(
        agent_info.type,
        agent_info.capabilities,
    )

    # Add base command
    base_cmd = agent_info.command
    builder.add_base(base_cmd)

    # Add permission flags
    if agent_info.type == "claude":
        mode = session_type.to_claude_permission_mode()
        builder.add_permissions(mode)

    # Apply roles
    if roles:
        merged = merge_roles(roles)

        # Add tools whitelist
        if merged.tools:
            builder.add_tools(merged.tools)

        # Add disallowed tools
        if merged.disallowed_tools:
            builder.add_disallowed_tools(merged.disallowed_tools)

        # Add system prompt
        if merged.instructions:
            builder.add_system_prompt(merged.instructions)

        # Add model
        if merged.model:
            builder.add_model(merged.model)

    return builder.build()
```

### 8.3 Feature Gating

```python
# agentwire/__main__.py (updated cmd_new)

def cmd_new(args):
    # Load config
    config = load_config()
    agent_info = AgentInfo.from_config(config)

    # Create feature gate
    feature_gate = AgentFeatureGate(agent_info.capabilities)

    # Check for required features
    if args.roles and not feature_gate.require_feature(
        "tools_flag",
        f"{agent_info.type} doesn't support --tools flag - using AgentWire role filtering"
    ):
        # Install AgentWire role filtering
        install_role_filtering(session_name, args.roles)

    if session_type == SessionType.CLAUDE_PROMPTED and not feature_gate.require_feature(
        "permissions",
        f"{agent_info.type} doesn't support permission dialogs - using AgentWire permission system"
    ):
        # Install AgentWire permission system
        install_agentwire_permissions(session_name)

    # Build agent command
    agent_cmd = _build_agent_command(
        agent_info,
        session_type,
        roles,
    )

    # Execute
    create_session(session_name, agent_cmd)

    # Show warnings
    for warning in feature_gate.warnings:
        print(f"⚠️  {warning}")
```

### 8.4 Hook Installation

```python
# agentwire/hooks/__init__.py (expanded)

class HookInstaller:
    """Install hooks for the appropriate agent type."""

    def __init__(self, agent_info: AgentInfo):
        self.agent_info = agent_info

    def install_session_hooks(self, session_name: str):
        """Install hooks for a specific session."""

        if self.agent_info.type == "claude":
            self._install_claude_hooks(session_name)
        else:
            # Use AgentWire hooks for all other agents
            self._install_agentwire_hooks(session_name)

    def _install_claude_hooks(self, session_name: str):
        """Install Claude Code hooks."""
        claude_hooks_dir = Path.home() / ".claude" / "hooks"

        # Install permission hook
        permission_hook = claude_hooks_dir / "agentwire-permission.sh"
        if not permission_hook.exists():
            self._install_permission_hook(permission_hook)

        # Install damage control hooks
        self._install_damage_control_hooks(claude_hooks_dir)

    def _install_agentwire_hooks(self, session_name: str):
        """Install AgentWire hooks (tmux-level)."""
        agentwire_hooks_dir = Path.home() / ".agentwire" / "hooks"
        agentwire_hooks_dir.mkdir(parents=True, exist_ok=True)

        # Install before-send-keys hook (tmux-level)
        hook_script = agentwire_hooks_dir / "before-send-keys.sh"
        if not hook_script.exists():
            hook_script.write_text("""#!/bin/bash
# AgentWire command interception hook
# Validates commands before they're sent to the agent

command="$1"
session="$2"

# Run through damage control
agentwire safety check "$command"
if [ $? -eq 1 ]; then
    # Command blocked
    echo "⚠️  Command blocked by safety system"
    exit 1
fi

exit 0
""")

        # Install tmux hook
        subprocess.run([
            "tmux",
            "set-hook",
            "-t", session_name,
            "before-send-keys",
            f"run-shell '{hook_script} \"#{{command}}\" \"#{{session_name}}\"'",
        ])
```

### 8.5 Permission Management

```python
# agentwire/permissions.py (new file)

import requests
from pathlib import Path

class PermissionManager:
    """Manage permissions for agents without native permission systems."""

    def __init__(self, config: Config):
        self.config = config
        self.agent_info = AgentInfo.from_config(config)

    def should_use_native_permissions(self) -> bool:
        """Check if we should use the agent's native permission system."""
        return (
            self.agent_info.type == "claude"
            and not self.agent_info.config.get("bypass_permissions", True)
        )

    def request_permission(
        self,
        session_name: str,
        operation: str,
        details: dict,
        timeout: int = 30
    ) -> bool | None:
        """Request permission for an operation.

        Returns:
            - None: Use agent's native permission system
            - True: Permission granted
            - False: Permission denied
        """
        # Use native system if available
        if self.should_use_native_permissions():
            return None

        # Use AgentWire permission system
        if not self.config.agent.fallback.get("use_agentwire_permissions", True):
            # Fallback disabled, auto-approve
            return True

        return self._request_via_portal(session_name, operation, details, timeout)

    def _request_via_portal(
        self,
        session_name: str,
        operation: str,
        details: dict,
        timeout: int
    ) -> bool:
        """Send permission request to AgentWire portal."""
        portal_url = self.config.portal.url

        try:
            response = requests.post(
                f"{portal_url}/api/permissions/request",
                json={
                    "session": session_name,
                    "operation": operation,
                    "details": details,
                },
                timeout=timeout,
                verify=False,  # Self-signed cert
            )

            data = response.json()
            return data.get("granted", False)

        except Exception as e:
            # Fallback to auto-approve on error
            print(f"⚠️  Failed to request permission: {e}")
            return True
```

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# tests/test_agent_info.py

def test_detect_claude_from_command():
    assert detect_agent_type("claude --dangerously-skip-permissions") == "claude"
    assert detect_agent_type("claude") == "claude"

def test_detect_opencode_from_command():
    assert detect_agent_type("opencode") == "opencode"
    assert detect_agent_type("opencode --model sonnet") == "opencode"

def test_auto_detection():
    # When command contains both, detect from first
    assert detect_agent_type("claude with opencode mention") == "claude"

def test_capability_profiles():
    claude_caps = CLAUDE_CAPABILITIES
    assert claude_caps.supports_hooks is True
    assert claude_caps.supports_permissions is True

    opencode_caps = OPENCODE_CAPABILITIES
    assert opencode_caps.supports_hooks is False
    assert opencode_caps.supports_permissions is False

# tests/test_command_builder.py

def test_build_claude_command_with_tools():
    builder = AgentCommandBuilder("claude", CLAUDE_CAPABILITIES)
    cmd = builder.add_base("claude").add_tools(["Bash", "Edit"]).build()
    assert "--tools Bash,Edit" in cmd

def test_build_opencode_command_ignores_tools():
    builder = AgentCommandBuilder("opencode", OPENCODE_CAPABILITIES)
    cmd = builder.add_base("opencode").add_tools(["Bash", "Edit"]).build()
    assert "--tools" not in cmd  # OpenCode doesn't support it

# tests/test_session_type.py

def test_normalize_session_types():
    # Universal types work with any agent
    assert normalize_session_type("standard", "claude") == ("standard", "claude")
    assert normalize_session_type("standard", "opencode") == ("standard", "opencode")

    # Claude-specific types map to standard with OpenCode
    result = normalize_session_type("claude-bypass", "opencode")
    assert result == ("opencode-standard", "opencode")
```

### 9.2 Integration Tests

```python
# tests/integration/test_multi_agent.py

@pytest.mark.parametrize("agent_type", ["claude", "opencode"])
def test_create_session_with_agent(agent_type):
    """Test session creation works with both agents."""
    config = load_test_config(agent_type=agent_type)
    agent_info = AgentInfo.from_config(config)

    result = cmd_new_with_agent(agent_info, session_name="test")

    assert result.success is True
    assert session_exists("test")

def test_role_filtering_with_opencode():
    """Test that role filtering works when OpenCode doesn't support --tools."""
    config = load_test_config(agent_type="opencode")
    agent_info = AgentInfo.from_config(config)

    # Create session with restricted role
    roles = [load_role("worker")]
    cmd_new_with_agent(agent_info, session_name="test", roles=roles)

    # Try to use disallowed tool
    output = send_input("test", "AskUserQuestion('Should I do this?')")

    # Should be filtered
    assert "AskUserQuestion" not in output
    assert "tool blocked" in output.lower()

def test_permission_system_fallback():
    """Test that AgentWire permission system is used when agent doesn't have one."""
    config = load_test_config(agent_type="opencode", fallback_permissions=True)

    session_name = "test"
    create_session(session_name, config)

    # Mock permission approval
    with mock_portal_response(granted=True):
        result = request_permission(session_name, "git push --force")

    assert result is True
```

## 10. Migration Guide

### For Existing Users

When upgrading AgentWire, users will see:

```bash
$ agentwire doctor
⚠️  Configuration migration needed

Your configuration uses legacy Claude Code-specific settings.
AgentWire now supports multiple AI agents.

Run: agentwire migrate-config
```

Migration command:

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

### Switching Agents

To switch from Claude Code to OpenCode:

```bash
# 1. Uninstall Claude Code hooks
$ agentwire hooks uninstall

# 2. Update config
$ cat >> ~/.agentwire/config.yaml <<EOF
agent:
  type: "opencode"
  command: "opencode"
  opencode:
    model: "sonnet"
EOF

# 3. Test with a new session
$ agentwire new -s test-opencode
ℹ️  Using agent: opencode
ℹ️  OpenCode doesn't support --tools flag - using AgentWire role filtering
ℹ️  OpenCode doesn't support permission dialogs - using AgentWire permission system
✓ Created session 'test-opencode'

# 4. If happy, update default session type in .agentwire.yml
$ echo 'type: "opencode-standard"' >> ~/projects/myproject/.agentwire.yml
```

## 11. Summary

This architecture provides:

1. **Seamless experience** - Users switch agents by changing one config value
2. **Feature adaptation** - CLI flags and behaviors automatically adjust to agent capabilities
3. **Graceful degradation** - Missing features are replaced with AgentWire implementations
4. **Backward compatibility** - Existing Claude Code users continue without changes
5. **Clean abstraction** - Agent-specific code isolated, easy to add new agents in the future
6. **Clear warnings** - Users are informed when features are unavailable
7. **Flexible fallbacks** - Users can opt-in/opt-out of AgentWire replacements

**Key Design Principles:**

- **Configuration-driven** - Agent type and capabilities in config, not hardcoded
- **Capability-based** - Check what agent supports, don't assume
- **Feature-gated** - All agent-specific features behind capability checks
- **Fallback-ready** - AgentWire provides implementations for missing features
- **Migration-safe** - Existing users upgrade without breaking changes
- **Testable** - Each component can be tested independently
- **Extensible** - New agents can be added by defining capability profiles

This design ensures AgentWire provides a "just works" experience regardless of which AI coding agent the user prefers.
