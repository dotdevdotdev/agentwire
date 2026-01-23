# Mission: OpenCode Integration

**Make AgentWire work seamlessly with both Claude Code and OpenCode AI coding agents.**

## Background

AgentWire currently hardcodes Claude Code as only AI agent. Users want flexibility to choose their preferred coding agent (Claude Code, OpenCode, or future alternatives). OpenCode offers compelling advantages:
- **Open source** (79k GitHub stars vs proprietary Claude Code)
- **Provider agnostic** (75+ LLM providers vs Anthropic-only)
- **Richer architecture** (client/server, HTTP API, TUI, web, mobile)
- **Plugin system** (30+ event hooks)
- **Better permission system** (allow/ask/deny with pattern matching)

## Architecture: Environment Variable Command Building

Instead of complex `AgentInfo` classes and capability detection, we'll use **environment variables** for command building. This is simpler, more maintainable, and easier to extend.

### Key Principle

Each session type sets environment variables that determine the agent command:

```python
# Example: Claude Code bypass session
session_type = "claude-bypass"

# Set environment variables
os.environ["AGENT_NEW_SESSION_COMMAND"] = "claude"
os.environ["AGENT_PERMISSIONS_FLAG"] = "--dangerously-skip-permissions"
os.environ["AGENT_TOOLS_FLAG"] = "--tools Bash,Edit,Write"  # If roles specified
os.environ["AGENT_DISALLOWED_TOOLS_FLAG"] = "--disallowedTools AskUserQuestion"
os.environ["AGENT_SYSTEM_PROMPT_FLAG"] = '--append-system-prompt "Role instructions"'
os.environ["AGENT_MODEL_FLAG"] = "--model sonnet"  # If role specifies

# Build command
cmd = " ".join(filter(None, [
    os.environ.get("AGENT_NEW_SESSION_COMMAND"),
    os.environ.get("AGENT_PERMISSIONS_FLAG"),
    os.environ.get("AGENT_TOOLS_FLAG"),
    os.environ.get("AGENT_DISALLOWED_TOOLS_FLAG"),
    os.environ.get("AGENT_SYSTEM_PROMPT_FLAG"),
    os.environ.get("AGENT_MODEL_FLAG"),
]))

# Result: "claude --dangerously-skip-permissions --tools Bash,Edit,Write --disallowedTools AskUserQuestion --append-system-prompt 'Role instructions' --model sonnet"
```

### Benefits

- ✅ **Simpler codebase** - No AgentInfo classes, no capability detection
- ✅ **Easy to extend** - Add new agents by adding session type conditionals
- ✅ **Clear mapping** - Can see exactly what each agent needs
- ✅ **Less refactoring** - Don't need to change every function
- ✅ **Backward compatible** - Claude Code behavior unchanged

---

## Session Type → Flag Mapping

### Claude Code Session Types

| Session Type | AGENT_NEW_SESSION_COMMAND | AGENT_PERMISSIONS_FLAG | AGENT_TOOLS_FLAG | AGENT_DISALLOWED_TOOLS_FLAG | AGENT_SYSTEM_PROMPT_FLAG | AGENT_MODEL_FLAG | Use Case |
|-------------|-------------------------|------------------------|-------------------|-------------------------------|-------------------------|-----------------|-----------|
| **bare** | (empty) | N/A | N/A | N/A | N/A | N/A | No agent, tmux only |
| **claude-bypass** | `claude` | `--dangerously-skip-permissions` | (from roles) | (from roles) | (from roles) | (from roles) | Full automation, voice orchestrator |
| **claude-prompted** | `claude` | (empty) | (from roles) | (from roles) | (from roles) | (from roles) | Semi-automated, user approval required |
| **claude-restricted** | `claude` | `--tools Bash` | N/A | N/A | N/A | N/A | Voice-only, Bash/say only |

**Role-based flags (for claude-bypass, claude-prompted):**
- If role specifies `tools`: `AGENT_TOOLS_FLAG = "--tools Bash,Edit,Write"`
- If role specifies `disallowedTools`: `AGENT_DISALLOWED_TOOLS_FLAG = "--disallowedTools AskUserQuestion"`
- If role has instructions: `AGENT_SYSTEM_PROMPT_FLAG = '--append-system-prompt "Role instructions"'`
- If role specifies model: `AGENT_MODEL_FLAG = "--model sonnet"`

### OpenCode Session Types

| Session Type | AGENT_NEW_SESSION_COMMAND | AGENT_PERMISSIONS_FLAG | OPENCODE_PERMISSION | AGENT_TOOLS_FLAG | AGENT_DISALLOWED_TOOLS_FLAG | AGENT_SYSTEM_PROMPT_FLAG | AGENT_MODEL_FLAG | Role Instructions | Use Case |
|-------------|-------------------------|------------------------|---------------------|-------------------|-------------------------------|-------------------------|-----------------|-------------------|-----------|
| **opencode-bypass** | `opencode` | (empty) | `{"*":"allow"}` | (empty) | (empty) | (empty) | (from roles) | Prepend to first message | Full automation |
| **opencode-prompted** | `opencode` | (empty) | `{"*":"ask"}` | (empty) | (empty) | (empty) | (from roles) | Prepend to first message | Permission prompts |
| **opencode-restricted** | `opencode` | (empty) | `{"bash":"allow","question":"deny"}` | (empty) | (empty) | (empty) | (from roles) | Prepend to first message | Worker, no questions |

**Key differences from Claude Code:**
- `AGENT_PERMISSIONS_FLAG` is always **empty** for OpenCode (no flag)
- Use `OPENCODE_PERMISSION` **environment variable** instead
- `AGENT_TOOLS_FLAG` and `AGENT_DISALLOWED_TOOLS_FLAG` are always **empty** (no flags)
- Tool control via **agent config** or **role filtering** in AgentWire CLI
- `AGENT_SYSTEM_PROMPT_FLAG` is always **empty** (no flag)
- Role instructions **prepended to first message** instead of using flag

### Universal Session Types (Agent-Agnostic)

To make things simpler for users, we'll also support universal types that work with both agents:

| Universal Type | Claude Code Maps To | OpenCode Maps To | Behavior |
|----------------|---------------------|-------------------|----------|
| **bare** | `bare` | `bare` | No agent, tmux only |
| **standard** | `claude-bypass` | `opencode-bypass` | Full agent capabilities |
| **worker** | `claude-restricted` | `opencode-restricted` | No AskUserQuestion, no voice |
| **voice** | `claude-prompted` | `opencode-prompted` | Voice with permission prompts |

**User experience:**
```yaml
# .agentwire.yml
type: "standard"  # Works for both Claude Code and OpenCode

# User sets agent preference in ~/.agentwire/config.yaml:
agent:
  command: "claude --dangerously-skip-permissions"  # or "opencode"
```

---

## Flag Reference

### Claude Code Flags

| Flag | Environment Variable | Description | Session Types |
|------|-------------------|-------------|---------------|
| `--dangerously-skip-permissions` | `AGENT_PERMISSIONS_FLAG` | Bypass all permission prompts | claude-bypass |
| `--tools tool1,tool2` | `AGENT_TOOLS_FLAG` | Whitelist specific tools | claude-bypass, claude-prompted |
| `--disallowedTools tool1` | `AGENT_DISALLOWED_TOOLS_FLAG` | Blacklist specific tools | claude-bypass, claude-prompted |
| `--append-system-prompt "text"` | `AGENT_SYSTEM_PROMPT_FLAG` | Add role instructions | claude-bypass, claude-prompted |
| `--model sonnet/opus/haiku` | `AGENT_MODEL_FLAG` | Override model | claude-bypass, claude-prompted |
| `--resume <session-id>` | (separate handling) | Resume from history | Fork sessions |
| `--fork-session` | (separate handling) | Fork into new session | Fork sessions |

### OpenCode Environment Variables

| Variable | Description | Session Types |
|-----------|-------------|---------------|
| `OPENCODE_PERMISSION` | Permission configuration (JSON) | opencode-bypass, opencode-prompted, opencode-restricted |
| `OPENCODE_MODEL` | Default model | All types |
| `OPENCODE_CONFIG_CONTENT` | Inline configuration JSON | All types |
| `OPENCODE_CONFIG_DIR` | Custom config directory | All types |
| `ROLE_INSTRUCTIONS_TO_PREPEND_<session>` | Role instructions for first message | All types |

---

## Implementation Plan

### Wave 1: Refactor `cmd_new` to Use Environment Variables (BLOCKING)

**Goal:** Refactor `agentwire new` command to build agent commands via environment variables.

**Tasks:**
- [ ] Create `_build_agent_command_env()` function to set environment variables based on session type
- [ ] Update `_build_claude_cmd()` to read from environment variables
- [ ] Add support for `opencode-bypass`, `opencode-prompted`, `opencode-restricted` session types
- [ ] Implement role instruction prepending for OpenCode (store in env for first message)
- [ ] Update `SessionType` enum to include OpenCode types
- [ ] Test all Claude Code session types still work
- [ ] Test all OpenCode session types

**Implementation Details:**

```python
# agentwire/__main__.py

def _build_agent_command_env(session_type: str, roles: list[RoleConfig] | None = None) -> dict[str, str]:
    """Build environment variables for agent command based on session type.

    Returns:
        Dictionary of environment variables to set
    """
    env = {}

    # Default: empty (bare session)
    if session_type == "bare":
        env["AGENT_NEW_SESSION_COMMAND"] = ""
        return env

    # === Claude Code Session Types ===
    if session_type in ["claude-bypass", "claude-prompted", "claude-restricted"]:
        env["AGENT_NEW_SESSION_COMMAND"] = "claude"

        # Permissions flag
        if session_type == "claude-bypass":
            env["AGENT_PERMISSIONS_FLAG"] = "--dangerously-skip-permissions"
        elif session_type == "claude-prompted":
            env["AGENT_PERMISSIONS_FLAG"] = ""
        elif session_type == "claude-restricted":
            env["AGENT_PERMISSIONS_FLAG"] = "--tools Bash"

        # Role-based flags
        if roles and session_type != "claude-restricted":
            merged = merge_roles(roles)

            if merged.tools:
                env["AGENT_TOOLS_FLAG"] = f"--tools {','.join(merged.tools)}"

            if merged.disallowed_tools:
                env["AGENT_DISALLOWED_TOOLS_FLAG"] = f"--disallowedTools {','.join(merged.disallowed_tools)}"

            if merged.instructions:
                escaped = merged.instructions.replace('"', '\\"')
                env["AGENT_SYSTEM_PROMPT_FLAG"] = f'--append-system-prompt "{escaped}"'

            if merged.model:
                env["AGENT_MODEL_FLAG"] = f"--model {merged.model}"

    # === OpenCode Session Types ===
    elif session_type in ["opencode-bypass", "opencode-prompted", "opencode-restricted"]:
        env["AGENT_NEW_SESSION_COMMAND"] = "opencode"

        # Permissions via environment variable (not a CLI flag)
        if session_type == "opencode-bypass":
            env["AGENT_PERMISSIONS_FLAG"] = ""
            env["OPENCODE_PERMISSION"] = '{"*":"allow"}'
        elif session_type == "opencode-prompted":
            env["AGENT_PERMISSIONS_FLAG"] = ""
            env["OPENCODE_PERMISSION"] = '{"*":"ask"}'
        elif session_type == "opencode-restricted":
            env["AGENT_PERMISSIONS_FLAG"] = ""
            env["OPENCODE_PERMISSION"] = '{"bash":"allow","question":"deny"}'

        # OpenCode doesn't support --tools or --disallowedTools flags
        env["AGENT_TOOLS_FLAG"] = ""
        env["AGENT_DISALLOWED_TOOLS_FLAG"] = ""
        env["AGENT_SYSTEM_PROMPT_FLAG"] = ""

        # Role-based settings
        if roles:
            merged = merge_roles(roles)

            # Store role instructions for prepending to first message
            if merged.instructions:
                env["ROLE_INSTRUCTIONS_TO_PREPEND"] = merged.instructions

            if merged.model:
                env["AGENT_MODEL_FLAG"] = f"--model {merged.model}"

    return env

def _build_agent_command_from_env() -> str:
    """Build agent command string from environment variables.

    Returns:
        The agent command string to execute
    """
    command = os.environ.get("AGENT_NEW_SESSION_COMMAND", "")
    if not command:
        return ""  # Bare session

    parts = [
        command,
        os.environ.get("AGENT_PERMISSIONS_FLAG", ""),
        os.environ.get("AGENT_TOOLS_FLAG", ""),
        os.environ.get("AGENT_DISALLOWED_TOOLS_FLAG", ""),
        os.environ.get("AGENT_SYSTEM_PROMPT_FLAG", ""),
        os.environ.get("AGENT_MODEL_FLAG", ""),
    ]

    return " ".join(filter(None, parts))

def cmd_new(args):
    """Create new session."""
    session_name = args.name or derive_session_name(args)
    session_type = args.type or load_session_type(args.path)
    roles = load_roles(args.roles)

    # Build environment variables based on session type
    env = _build_agent_command_env(session_type, roles)

    # Set environment variables
    for key, value in env.items():
        os.environ[key] = value

    # Build command from environment variables
    agent_cmd = _build_agent_command_from_env()

    # Create session with agent command
    create_session(session_name, agent_cmd)

    # Store role instructions for first message (OpenCode only)
    if "ROLE_INSTRUCTIONS_TO_PREPEND" in env:
        # Store in session metadata for first send
        store_session_metadata(session_name, {
            "role_instructions": env["ROLE_INSTRUCTIONS_TO_PREPEND"]
        })
```

**Files to Modify:**
- `agentwire/__main__.py` - Add new functions, update cmd_new
- `agentwire/project_config.py` - Update SessionType enum

**Testing:**
```bash
# Test Claude Code session types
agentwire new -s test-claude-bypass --type claude-bypass
agentwire new -s test-claude-prompted --type claude-prompted
agentwire new -s test-claude-restricted --type claude-restricted

# Test OpenCode session types
agentwire new -s test-opencode-bypass --type opencode-bypass
agentwire new -s test-opencode-prompted --type opencode-prompted
agentwire new -s test-opencode-restricted --type opencode-restricted

# Verify commands
tmux capture-pane -t test-opencode-bypass -p | head -5
# Should see: "opencode" (no flags)
```

**Success Criteria:**
- Claude Code sessions work exactly as before
- OpenCode sessions create with correct environment variables
- Role instructions prepended to first OpenCode message
- All session type flags map correctly

---

### Wave 2: Update `cmd_send` for Role Instructions (BLOCKING)

**Goal:** Handle role instruction prepending for OpenCode first messages.

**Tasks:**
- [ ] Update `cmd_send` to check for stored role instructions
- [ ] Prepend role instructions to first message if present
- [ ] Delete stored instructions after first send
- [ ] Test first message has role instructions
- [ ] Test subsequent messages don't have role instructions

**Implementation Details:**

```python
# agentwire/__main__.py

def cmd_send(args):
    """Send message to session."""
    session_name = args.session or get_session_from_env()

    # Check if we need to prepend role instructions (first message for OpenCode)
    role_instructions = load_session_metadata(session_name).get("role_instructions")
    if role_instructions:
        # Prepend instructions to message
        args.message = f"{role_instructions}\n\n---\n\n{args.message}"

        # Clear stored instructions after use
        store_session_metadata(session_name, {"role_instructions": None})

    # ... existing send logic ...
```

**Files to Modify:**
- `agentwire/__main__.py` - Update cmd_send

**Testing:**
```bash
# Create OpenCode session with role
agentwire new -s test-opencode --type opencode-bypass --roles worker

# Send first message
agentwire send -s test-opencode "Hello"
# Check tmux: should see worker role instructions before "Hello"

# Send second message
agentwire send -s test-opencode "Second message"
# Check tmux: should NOT see worker role instructions
```

**Success Criteria:**
- Role instructions prepended to first OpenCode message
- Role instructions not prepended to subsequent messages
- Claude Code sessions unaffected

---

### Wave 3: Update Other Session Creation Commands

**Goal:** Apply environment variable pattern to all session creation commands.

**Commands to Update:**
- `agentwire recreate`
- `agentwire fork`
- `agentwire spawn`

**Implementation Details:**

```python
# agentwire/__main__.py

def cmd_recreate(args):
    """Recreate session (destroy and create fresh)."""
    session_name = args.session
    session_config = load_session_config(session_name)

    # Use existing session type
    session_type = session_config.get("type", "claude-bypass")
    roles = session_config.get("roles")

    # Build environment variables
    env = _build_agent_command_env(session_type, roles)
    for key, value in env.items():
        os.environ[key] = value

    # Build command
    agent_cmd = _build_agent_command_from_env()

    # ... existing recreate logic ...

def cmd_fork(args):
    """Fork session into new worktree."""
    from_session = args.session
    session_config = load_session_config(from_session)

    # Use same session type
    session_type = session_config.get("type", "claude-bypass")
    roles = session_config.get("roles")

    # Build environment variables
    env = _build_agent_command_env(session_type, roles)
    for key, value in env.items():
        os.environ[key] = value

    # ... existing fork logic ...

def cmd_spawn(args):
    """Spawn worker pane."""
    parent_session = get_parent_session()

    # Workers always use worker session type
    if opencode_installed():
        session_type = "opencode-restricted"
    else:
        session_type = "claude-restricted"

    roles = [load_role("worker")]

    # Build environment variables
    env = _build_agent_command_env(session_type, roles)
    for key, value in env.items():
        os.environ[key] = value

    # Build command
    agent_cmd = _build_agent_command_from_env()

    # ... existing spawn logic ...
```

**Files to Modify:**
- `agentwire/__main__.py` - Update cmd_recreate, cmd_fork, cmd_spawn

**Testing:**
```bash
# Test fork preserves session type
agentwire new -s test-opencode --type opencode-bypass
agentwire fork -s test-opencode -b feature-test
# Verify feature-test uses opencode-bypass type

# Test spawn uses worker type
agentwire spawn
# Verify new pane uses opencode-restricted or claude-restricted
```

**Success Criteria:**
- All session creation commands use environment variable pattern
- Fork preserves session type
- Spawn uses correct worker type based on agent installed

---

### Wave 4: Add Universal Session Types (NICE-TO-HAVE)

**Goal:** Add agent-agnostic session types for better user experience.

**Tasks:**
- [ ] Add `standard`, `worker`, `voice` to SessionType enum
- [ ] Implement session type detection from config (`agent.command`)
- [ ] Map universal types to agent-specific types
- [ ] Update docs to recommend universal types

**Implementation Details:**

```python
# agentwire/project_config.py

class SessionType(str, Enum):
    """Session types."""

    # Agent-specific types
    BARE = "bare"
    CLAUDE_BYPASS = "claude-bypass"
    CLAUDE_PROMPTED = "claude-prompted"
    CLAUDE_RESTRICTED = "claude-restricted"
    OPENCODE_BYPASS = "opencode-bypass"
    OPENCODE_PROMPTED = "opencode-prompted"
    OPENCODE_RESTRICTED = "opencode-restricted"

    # Universal types (agent-agnostic)
    STANDARD = "standard"
    WORKER = "worker"
    VOICE = "voice"

# agentwire/__main__.py

def detect_default_agent_type() -> str:
    """Detect which AI agent is installed."""
    if shutil.which("claude"):
        return "claude"
    elif shutil.which("opencode"):
        return "opencode"
    return "claude"  # Default for backward compatibility

def normalize_session_type(session_type: str, agent_type: str) -> str:
    """Map universal session types to agent-specific types.

    Args:
        session_type: "standard", "worker", "voice", or agent-specific type
        agent_type: "claude" or "opencode"

    Returns:
        Agent-specific session type
    """
    # If already agent-specific, return as-is
    if session_type in [
        "claude-bypass", "claude-prompted", "claude-restricted",
        "opencode-bypass", "opencode-prompted", "opencode-restricted",
    ]:
        return session_type

    # Map universal types
    if session_type == "standard":
        return f"{agent_type}-bypass"
    elif session_type == "worker":
        return f"{agent_type}-restricted"
    elif session_type == "voice":
        return f"{agent_type}-prompted"

    # Unknown type, default to standard
    return f"{agent_type}-bypass"
```

**Files to Modify:**
- `agentwire/project_config.py` - Add universal session types
- `agentwire/__main__.py` - Add detection and normalization

**Testing:**
```bash
# Test universal types with Claude Code
echo "agent:\n  command: claude" > ~/.agentwire/config.yaml
agentwire new -s test-standard --type standard
# Should use claude-bypass internally

agentwire new -s test-worker --type worker
# Should use claude-restricted internally

# Test universal types with OpenCode
echo "agent:\n  command: opencode" > ~/.agentwire/config.yaml
agentwire new -s test-standard --type standard
# Should use opencode-bypass internally

agentwire new -s test-worker --type worker
# Should use opencode-restricted internally
```

**Success Criteria:**
- Users can use `--type standard` regardless of agent
- Universal types map correctly to agent-specific types
- Backward compatible with agent-specific types

---

### Wave 5: Documentation & Examples

**Goal:** Complete documentation for OpenCode integration.

**Tasks:**
- [ ] Update README with OpenCode requirements
- [ ] Create OpenCode setup guide
- [ ] Document all session types (agent-specific and universal)
- [ ] Add examples for OpenCode with roles
- [ ] Update troubleshooting guide

**Documentation Structure:**

```
docs/
├── opencode-integration.md          # Complete guide
├── opencode-quickstart.md          # 5-minute setup
├── session-types.md                 # All session types reference
├── examples/
│   ├── claude-workflow.md         # Claude Code examples
│   ├── opencode-workflow.md        # OpenCode examples
│   └── multi-agent-workflow.md    # Using both agents
└── troubleshooting/
    ├── opencode-issues.md         # OpenCode-specific issues
    └── migration.md              # Migrating from Claude to OpenCode
```

**Content:**

1. **opencode-integration.md**
   - Quick start
   - Installation
   - Session types (both agent-specific and universal)
   - Configuration
   - Roles with OpenCode
   - Migration guide

2. **opencode-quickstart.md**
   ```bash
   # 1. Install OpenCode
   npm install -g @opencode-ai/cli

   # 2. Create session
   agentwire new -s myproject --type standard

   # 3. Use it
   agentwire send -s myproject "Build a REST API"
   ```

3. **session-types.md**
   - Table of all session types (agent-specific and universal)
   - Flag mappings
   - Use cases
   - Examples

**Success Criteria:**
- Users can set up OpenCode in 5 minutes
- All session types documented
- Migration guide complete
- Examples for common workflows

---

## Configuration

### Minimal Config

```yaml
# ~/.agentwire/config.yaml
agent:
  command: "claude --dangerously-skip-permissions"  # or "opencode"
```

### Session Type in Project

```yaml
# ~/projects/myproject/.agentwire.yml
type: "standard"  # or "claude-bypass", "opencode-bypass", etc.
roles:
  - agentwire
  - custom-role
```

## Testing Strategy

### Unit Tests

```python
# tests/test_agent_command_env.py

def test_build_claude_bypass_env():
    env = _build_agent_command_env("claude-bypass", None)
    assert env["AGENT_NEW_SESSION_COMMAND"] == "claude"
    assert env["AGENT_PERMISSIONS_FLAG"] == "--dangerously-skip-permissions"

def test_build_claude_with_roles():
    roles = [load_role("worker")]
    env = _build_agent_command_env("claude-bypass", roles)
    assert "AskUserQuestion" in env["AGENT_DISALLOWED_TOOLS_FLAG"]

def test_build_opencode_bypass_env():
    env = _build_agent_command_env("opencode-bypass", None)
    assert env["AGENT_NEW_SESSION_COMMAND"] == "opencode"
    assert env["OPENCODE_PERMISSION"] == '{"*":"allow"}'
    assert env["AGENT_TOOLS_FLAG"] == ""

def test_role_instructions_stored():
    roles = [load_role("agentwire")]
    env = _build_agent_command_env("opencode-bypass", roles)
    assert "ROLE_INSTRUCTIONS_TO_PREPEND" in env
```

### Integration Tests

```python
# tests/integration/test_session_types.py

@pytest.mark.parametrize("session_type", [
    "claude-bypass", "claude-prompted", "claude-restricted",
    "opencode-bypass", "opencode-prompted", "opencode-restricted",
])
def test_create_session(session_type):
    """Test session creation for all session types."""
    agentwire new -s f"test-{session_type}" --type session_type
    assert session_exists(f"test-{session_type}")

    # Verify correct command started
    output = tmux_capture_pane(f"test-{session_type}")
    if session_type.startswith("claude-"):
        assert "claude" in output
    elif session_type.startswith("opencode-"):
        assert "opencode" in output

def test_opencode_role_instructions():
    """Test role instructions prepended to first message."""
    agentwire new -s test-opencode --type opencode-bypass --roles worker
    agentwire send -s test-opencode "Hello"

    output = tmux_capture_pane("test-opencode")
    assert "Worker agent" in output  # Role instructions
    assert "Hello" in output

    # Second message should not have role instructions
    agentwire send -s test-opencode "Second"
    output = tmux_capture_pane("test-opencode")
    assert "Second" in output
    # Role instructions only appear once
    assert output.count("Worker agent") == 1
```

## Success Criteria

- [ ] Claude Code sessions work exactly as before (no regressions)
- [ ] OpenCode sessions can be created with all types
- [ ] Environment variables correctly map to flags for each agent
- [ ] Role instructions work for both agents (prepend for OpenCode, flag for Claude)
- [ ] Universal session types work seamlessly
- [ ] Documentation complete for both agents
- [ ] All tests pass (unit + integration)

## Known Limitations

1. **OpenCode hooks** - No native permission hooks, rely on AgentWire damage control
2. **OpenCode tool flags** - No `--tools` flag, use agent config or role filtering
3. **OpenCode system prompt** - No flag, prepend to first message
4. **Mixed sessions** - Can't have Claude and OpenCode sessions in same project (different .agentwire.yml)
5. **Runtime switching** - Can't switch agents mid-session (need to recreate)

## Future Enhancements

1. **Agent detection** - Auto-detect which agent is installed
2. **Config migration** - Auto-migrate from Claude to OpenCode
3. **Role filtering** - Implement AgentWire-level tool filtering for OpenCode
4. **Permission fallbacks** - AgentWire permission dialogs for OpenCode
5. **Mixed sessions** - Support both agents in same project
6. **Runtime switching** - Switch agents mid-session
