# Research: Multi-Agent CLI Support

> Investigation into what changes are needed to support alternative agent CLIs (e.g., opencode) alongside Claude Code.

## Current State

AgentWire is tightly coupled to Claude Code. The integration points are documented below.

## High Coupling Areas

| Area | Files | Claude Code Specific |
|------|-------|---------------------|
| **Command invocation** | `agents/tmux.py`, `__main__.py` | `claude` binary, `--dangerously-skip-permissions`, `--allowedTools` |
| **Session types** | `project_config.py` | bypass/prompted/restricted modes map to Claude flags |
| **Role injection** | `__main__.py:65` | `--append-system-prompt` flag |
| **Session forking** | `agents/tmux.py:189-193` | `--session-id`, `--resume`, `--fork-session` |
| **Permission hooks** | `hooks/damage-control/*.py` | PreToolUse hook format, tool names (Bash, Edit, Write) |
| **Exit command** | `pane_manager.py`, `__main__.py` | `/exit` to cleanly stop |

## Detailed Integration Points

### 1. Direct Command Invocation

| File | Line | Description |
|------|------|-------------|
| `agents/tmux.py` | 15 | `DEFAULT_AGENT_COMMAND = "claude"` |
| `agents/tmux.py` | 44 | agent_command configuration loading |
| `agents/tmux.py` | 157-198 | `_format_agent_command()` method |
| `agents/tmux.py` | 200-239 | `create_session()` executes claude command |
| `__main__.py` | 27-71 | `_build_claude_cmd()` function |

### 2. CLI Flags

| File | Line | Description |
|------|------|-------------|
| `project_config.py` | 15-41 | `SessionType` enum with 4 modes |
| `project_config.py` | 31-41 | `to_cli_flags()` generates `--dangerously-skip-permissions`, `--allowedTools` |
| `__main__.py` | 46 | Session type to CLI flags |
| `__main__.py` | 54,58 | `--tools` and `--disallowedTools` flags |
| `__main__.py` | 65 | `--append-system-prompt` for roles |
| `server.py` | 1394-1430 | API converts session types to flags |

### 3. Session Forking & UUID Management

| File | Line | Description |
|------|------|-------------|
| `agents/tmux.py` | 165,174 | session_id and fork_from parameters |
| `agents/tmux.py` | 189 | `--session-id` flag |
| `agents/tmux.py` | 193 | `--resume` and `--fork-session` flags |
| `server.py` | 82 | `claude_session_id` field in SessionConfig |

### 4. Permission Hook System (PreToolUse)

| File | Line | Description |
|------|------|-------------|
| `hooks/damage-control/bash-tool-damage-control.py` | 10-18 | PreToolUse hook format |
| `hooks/damage-control/bash-tool-damage-control.py` | 318 | Hook output format |
| `hooks/damage-control/edit-tool-damage-control.py` | 10 | Edit tool PreToolUse hook |
| `hooks/damage-control/write-tool-damage-control.py` | 10 | Write tool PreToolUse hook |
| `server.py` | 40-70 | `_is_allowed_in_restricted_mode()` validates Claude tools |
| `server.py` | 2250-2350 | `api_permission_request()` handles permission requests |
| `server.py` | 2350-2390 | `api_permission_respond()` sends decisions back |

### 5. Role System & Tool Whitelisting

| File | Line | Description |
|------|------|-------------|
| `roles/agentwire.md` | 1-203 | Main orchestrator role (Claude Code specific) |
| `roles/worker.md` | 1-63 | Worker role (references Edit, Write, Read, Bash, Task, Glob, Grep, TodoWrite) |
| `roles/voice.md` | 1-63 | Voice role (uses say command) |
| `__main__.py` | 48-71 | Tool merging and `--append-system-prompt` injection |

### 6. Frontend Permission UI

| File | Line | Description |
|------|------|-------------|
| `static/js/session.js` | 40 | AWAITING_PERMISSION state |
| `static/js/session.js` | 210,212 | permission_request/resolved handlers |
| `static/js/session.js` | 435-446 | Permission modal rendering |
| `static/js/session.js` | 477 | POST to /api/permission respond |
| `static/js/dashboard.js` | 661-674 | Session type badge display |
| `static/js/dashboard.js` | 985 | Session type mapping |

### 7. Configuration

| File | Line | Description |
|------|------|-------------|
| `.agentwire.yml` | 2 | `type: claude-bypass` (default) |
| `config.py` | 164 | Default session type "claude-bypass" |
| `examples/config.yaml` | 44-47 | Agent command config with `{name}`, `{path}`, `{model}` placeholders |

## Already Abstracted

- `agents/tmux.py:15` has `DEFAULT_AGENT_COMMAND = "claude"` (configurable via config)
- `config.yaml` supports `agent_command` with `{name}`, `{path}`, `{model}` placeholders

## Would Need Abstraction

### 1. CLI Flag Mapper

Translate session types to agent-specific flags:

```python
# Current (Claude Code)
--dangerously-skip-permissions
--allowedTools "Bash,Edit,Write"
--append-system-prompt "..."

# Opencode equivalent (TBD)
# Need to research opencode's CLI flags
```

### 2. Tool Names

Map between agent tool names:

| Claude Code | Opencode (TBD) |
|-------------|----------------|
| Bash | ? |
| Edit | ? |
| Write | ? |
| Read | ? |
| Glob | ? |
| Grep | ? |
| Task | ? |

### 3. Hook Format

Claude Code uses PreToolUse hooks with specific JSON structure:

```json
{
  "tool_name": "Bash",
  "tool_input": {"command": "rm -rf /"}
}
```

Other agents may have different hook mechanisms or none at all.

### 4. System Prompt Injection

How roles get appended varies by agent:

| Agent | Method |
|-------|--------|
| Claude Code | `--append-system-prompt "..."` |
| Opencode | TBD |

### 5. Session Management

Fork/resume semantics differ:

| Feature | Claude Code | Opencode (TBD) |
|---------|-------------|----------------|
| Session ID | `--session-id UUID` | ? |
| Resume | `--resume` | ? |
| Fork | `--fork-session UUID` | ? |

## Proposed Architecture

### Agent Adapter Interface

```python
class AgentAdapter(ABC):
    """Abstract interface for agent CLI integration."""

    @abstractmethod
    def get_command(self, session_name: str, cwd: str, model: str | None) -> list[str]:
        """Build the base command to start the agent."""
        pass

    @abstractmethod
    def get_permission_flags(self, session_type: SessionType) -> list[str]:
        """Get CLI flags for permission mode."""
        pass

    @abstractmethod
    def get_role_injection_flags(self, role_content: str) -> list[str]:
        """Get CLI flags to inject role instructions."""
        pass

    @abstractmethod
    def get_session_flags(self, session_id: str | None, fork_from: str | None) -> list[str]:
        """Get CLI flags for session management."""
        pass

    @abstractmethod
    def get_exit_command(self) -> str:
        """Get command to cleanly exit the agent."""
        pass

    @abstractmethod
    def map_tool_name(self, tool: str) -> str:
        """Map generic tool name to agent-specific name."""
        pass
```

### Implementation

```python
class ClaudeCodeAdapter(AgentAdapter):
    def get_command(self, session_name, cwd, model):
        cmd = ["claude"]
        if model:
            cmd.extend(["--model", model])
        return cmd

    def get_permission_flags(self, session_type):
        if session_type == SessionType.CLAUDE_BYPASS:
            return ["--dangerously-skip-permissions"]
        # ... etc

    def get_exit_command(self):
        return "/exit"

class OpencodeAdapter(AgentAdapter):
    # TBD - need to research opencode CLI
    pass
```

## Effort Estimate

| Task | Effort | Notes |
|------|--------|-------|
| Create `AgentAdapter` interface | Small | New file in `agents/` |
| Implement `ClaudeCodeAdapter` | Small | Extract existing logic |
| Refactor `_build_claude_cmd()` | Medium | Use adapter pattern |
| Refactor `SessionType.to_cli_flags()` | Medium | Delegate to adapter |
| Abstract hook format | Medium | Or make hooks agent-specific |
| Update role files per agent | Low | May need agent-specific roles |
| Research opencode CLI | Small | Before implementing adapter |

## Next Steps

1. Research opencode CLI flags and capabilities
2. Create `AgentAdapter` interface
3. Implement `ClaudeCodeAdapter` (extract existing code)
4. Implement `OpencodeAdapter`
5. Update configuration to select adapter
6. Test with both agents

## References

- Claude Code CLI: `claude --help`
- Opencode: https://github.com/opencode-ai/opencode (TBD)
