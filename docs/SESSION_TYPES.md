# Session Types Reference

Complete reference of all session types in AgentWire, including Claude Code, OpenCode, and universal types.

## Universal Session Types (Recommended)

Universal session types work with both Claude Code and OpenCode. Use these for agent-agnostic configuration.

| Universal Type | Claude Code Maps To | OpenCode Maps To | Behavior |
|----------------|---------------------|-------------------|----------|
| **standard** | claude-bypass | opencode-bypass | Full agent capabilities, no permission prompts |
| **worker** | claude-restricted | opencode-restricted | No AskUserQuestion, no voice, focused execution |
| **voice** | claude-prompted | opencode-prompted | Voice with permission prompts, user approval |
| **bare** | bare | bare | No agent, tmux terminal only |

### Universal Type Examples

```yaml
# .agentwire.yml - works for both agents
type: "standard"      # Full automation
roles:
  - agentwire
```

```yaml
# Worker session
type: "worker"
roles:
  - worker
```

```yaml
# Voice session with approvals
type: "voice"
```

---

## Claude Code Session Types

### Overview

| Session Type | Permission Flag | Tools | Use Case |
|--------------|-----------------|-------|----------|
| **claude-bypass** | `--dangerously-skip-permissions` | Full (configurable via roles) | Full automation, orchestrator |
| **claude-prompted** | (none, default behavior) | Full (configurable via roles) | Semi-automated, user approval |
| **claude-restricted** | `--tools Bash` | Bash only | Worker, no AskUserQuestion |
| **bare** | N/A | N/A | Terminal only, no agent |

### Flag Mapping Table

| Session Type | Command | Permissions Flag | Tools Flag | Disallowed Tools | System Prompt | Model Flag |
|-------------|---------|------------------|------------|------------------|---------------|------------|
| **claude-bypass** | `claude` | `--dangerously-skip-permissions` | (from roles) | (from roles) | (from roles) | (from roles) |
| **claude-prompted** | `claude` | (empty) | (from roles) | (from roles) | (from roles) | (from roles) |
| **claude-restricted** | `claude` | `--tools Bash` | N/A | N/A | N/A | N/A |
| **bare** | (empty) | N/A | N/A | N/A | N/A | N/A |

### Role-Based Flags (Claude Code)

When roles are specified, additional flags are added:

| Role Setting | Flag | Example |
|--------------|------|---------|
| **tools** list | `--tools Bash,Edit,Write` | Whitelist specific tools |
| **disallowedTools** list | `--disallowedTools AskUserQuestion` | Blacklist specific tools |
| **instructions** text | `--append-system-prompt "text"` | Add role instructions to system prompt |
| **model** string | `--model sonnet` | Override default model |

### Complete Examples

```bash
# Full automation (orchestrator)
agentwire new -s orchestrator --type claude-bypass

# With custom role
agentwire new -s custom --type claude-bypass --roles agentwire
# Command: claude --dangerously-skip-permissions --append-system-prompt "AgentWire orchestrator instructions..."

# Voice with approvals
agentwire new -s voice-bot --type claude-prompted

# Worker (no voice, no questions)
agentwire new -s worker --type claude-restricted

# Terminal only
agentwire new -s terminal --type bare
```

---

## OpenCode Session Types

### Overview

| Session Type | Permission Config | Tools | Use Case |
|--------------|------------------|-------|----------|
| **opencode-bypass** | `{"*":"allow"}` | Full (via config/roles) | Full automation, orchestrator |
| **opencode-prompted** | `{"*":"ask"}` | Full (via config/roles) | Semi-automated, user approval |
| **opencode-restricted** | `{"bash":"allow","question":"deny"}` | Bash only | Worker, no AskUserQuestion |
| **bare** | N/A | N/A | Terminal only, no agent |

### Environment Variable Mapping

| Session Type | Command | OPENCODE_PERMISSION | Role Instructions | Model |
|-------------|---------|---------------------|-------------------|-------|
| **opencode-bypass** | `opencode` | `{"*":"allow"}` | Prepend to first message | (from roles) |
| **opencode-prompted** | `opencode` | `{"*":"ask"}` | Prepend to first message | (from roles) |
| **opencode-restricted** | `opencode` | `{"bash":"allow","question":"deny"}` | Prepend to first message | (from roles) |
| **bare** | (empty) | N/A | N/A | N/A |

**Key Differences from Claude Code:**
- No CLI flags for permissions, tools, or system prompts
- Permissions set via `OPENCODE_PERMISSION` environment variable
- Role instructions prepended to first message instead of using flag
- Tool control via agent config or AgentWire role filtering

### Role-Based Settings (OpenCode)

| Role Setting | Implementation | Example |
|--------------|---------------|---------|
| **tools** list | AgentWire-level filtering | Filtered by CLI before sending to agent |
| **disallowedTools** list | AgentWire-level filtering | Blocks tools from being used |
| **instructions** text | Prepend to first message | "Role instructions\n\n---\n\nActual message" |
| **model** string | Agent config | Set in OpenCode config or via CLI |

### Complete Examples

```bash
# Full automation (orchestrator)
agentwire new -s orchestrator --type opencode-bypass

# With custom role
agentwire new -s custom --type opencode-bypass --roles agentwire
# First message prepended with role instructions

# Voice with approvals
agentwire new -s voice-bot --type opencode-prompted

# Worker (no voice, no questions)
agentwire new -s worker --type opencode-restricted

# Terminal only
agentwire new -s terminal --type bare
```

---

## Session Type Selection Guide

### By Use Case

| Use Case | Recommended Type | Why |
|----------|------------------|-----|
| **Orchestrator** (coordinates workers) | `standard` / `claude-bypass` / `opencode-bypass` | Full capabilities, no permission prompts for automation |
| **Worker** (executes tasks) | `worker` / `claude-restricted` / `opencode-restricted` | Focused on code execution, no voice interruptions |
| **Voice-first** (push-to-talk) | `voice` / `claude-prompted` / `opencode-prompted` | Permission prompts provide safety for voice input |
| **Terminal only** (no AI) | `bare` | Pure tmux terminal |
| **Testing** | `standard` | Full capabilities for testing workflows |

### By Agent

| Agent | Recommended Types | When to Use |
|-------|-------------------|-------------|
| **Claude Code** | `claude-bypass`, `claude-prompted`, `claude-restricted` | Fine-grained control over Claude's permission system |
| **OpenCode** | `opencode-bypass`, `opencode-prompted`, `opencode-restricted` | OpenCode's flexible permission system |
| **Both** | `standard`, `worker`, `voice` | Agent-agnostic configuration |

### By Permission Model

| Permission Model | Session Type | Description |
|----------------|--------------|-------------|
| **No prompts** | `standard`, `claude-bypass`, `opencode-bypass` | Agent executes everything without asking |
| **Ask for everything** | `voice`, `claude-prompted`, `opencode-prompted` | Agent asks before executing tools |
| **Minimal permissions** | `worker`, `claude-restricted`, `opencode-restricted` | Agent can only use Bash, no AskUserQuestion |
| **No AI** | `bare` | Terminal only, no AI assistance |

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
| `ROLE_INSTRUCTIONS_TO_PREPEND` | Role instructions for first message | All types |

---

## Common Workflows

### Orchestrator + Workers

```bash
# Create orchestrator session
agentwire new -s orchestrator --type standard --roles agentwire

# Spawn worker panes
agentwire spawn --roles worker  # Worker uses "worker" type

# Result:
# - Pane 0: Orchestrator (standard) - coordinates via voice
# - Pane 1+: Workers (worker) - execute focused tasks
```

### Multi-Agent Parallel Work

```bash
# Session 1: Feature development
agentwire new -s feature-auth --type standard

# Session 2: Bug fixes (different worktree)
agentwire new -s feature-auth/bugfix

# Session 3: Testing
agentwire new -s testing --type worker
```

### Voice Development Loop

```bash
# Create voice-enabled session
agentwire new -s voice-dev --type voice

# Start portal
agentwire portal start

# Open browser, use push-to-talk for development
```

---

## Configuration Examples

### Project Config (.agentwire.yml)

```yaml
# Orchestrator project
type: "standard"
roles:
  - agentwire
```

```yaml
# Worker project
type: "worker"
roles:
  - worker
```

```yaml
# Voice project
type: "voice"
```

### CLI Flags

```bash
# Override project type
agentwire new -s myproject --type opencode-bypass

# Specify roles
agentwire new -s myproject --roles agentwire,custom

# Combine type and roles
agentwire new -s myproject --type worker --roles worker
```

---

## Migration Notes

### Claude Code to OpenCode

| Claude Code Type | OpenCode Type | Changes |
|------------------|---------------|---------|
| `claude-bypass` | `opencode-bypass` | Permission system changes |
| `claude-prompted` | `opencode-prompted` | Permission prompts |
| `claude-restricted` | `opencode-restricted` | Tool restrictions |

**Key differences:**
- OpenCode uses `OPENCODE_PERMISSION` env var instead of CLI flags
- Role instructions prepended to first message
- Tool control via agent config or AgentWire filtering

### Universal Types

Switch to universal types for agent-agnostic config:

```yaml
# Before (agent-specific)
type: "claude-bypass"

# After (universal)
type: "standard"
```

See [Migration Guide](migration-guide.md) for complete migration steps.

---

## Summary

- **Use universal types** (`standard`, `worker`, `voice`) for agent-agnostic configuration
- **Claude Code** uses CLI flags for fine-grained control
- **OpenCode** uses environment variables for permissions
- **Role instructions** differ: flags for Claude Code, message prepend for OpenCode
- **Worker sessions** should use restricted types to prevent voice interruptions
- **Voice sessions** should use prompted types for safety

For more information:
- [OpenCode Quick Start](OPENCODE_QUICKSTART.md)
- [OpenCode Integration Guide](opencode-integration.md)
- [Migration Guide](migration-guide.md)
