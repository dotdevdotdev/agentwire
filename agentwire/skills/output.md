---
name: output
description: Read recent output from a tmux session. Use when reviewing command output, checking logs, or debugging what happened in a session.
---

# /output

Read and display recent output from a tmux session.

## Usage

```
/output <session> [lines]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| session | Yes | - | Session name, optionally with @machine suffix |
| lines | No | 50 | Number of lines to capture |

## Behavior

1. **Parse session argument**
   - Simple name: `api` → local session
   - With suffix: `ml@devbox-1` → remote session on devbox-1

2. **Capture output**
   - Use `agentwire output` to get scrollback
   - Returns last N lines from buffer

3. **Return formatted output**
   - Display with session context
   - Handle empty output gracefully

## Implementation

Use the `agentwire output` CLI command:

```bash
# Local session
agentwire output -s <session>

# With custom line count
agentwire output -s <session> -n <lines>

# Remote session (via SSH)
ssh <host> "agentwire output -s <session> -n <lines>"
```

### Flags

| Flag | Purpose |
|------|---------|
| `-s <session>` | Target session name (required) |
| `-n <lines>` | Number of lines to capture (default: 50) |

## Examples

```bash
# Local session, default 50 lines
/output api
→ Shows last 50 lines from local "api" session

# Local session, custom line count
/output api 100
→ Shows last 100 lines from local "api" session

# Remote session on devbox-1
/output ml@devbox-1
→ Shows last 50 lines from "ml" session on devbox-1

# Remote session with custom lines
/output worker@devbox-1 200
→ Shows last 200 lines from "worker" session on devbox-1
```

## Error Cases

| Error | Cause | Response |
|-------|-------|----------|
| Session not found | Invalid session name | List available sessions |
| SSH connection failed | Host unreachable | Show connection error |
| Empty output | Session has no scrollback | Indicate empty buffer |

## Integration with AgentWire

This skill is part of the AgentWire orchestration system. The session names align with:
- Agent sessions spawned by AgentWire
- Terminal sessions created via the AgentWire portal
- Remote sessions on machines in the machine registry
