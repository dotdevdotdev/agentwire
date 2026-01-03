---
name: new
description: Create a new Claude Code session in tmux.
---

# /new

Create a new Claude Code session in a tmux session, either locally or on a remote machine.

## Usage

```
/new <name> [path] [@machine]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Becomes the tmux session name |
| `path` | No | Working directory. Defaults to `~/projects/<name>` (local) or `{projects_dir}/<name>` (remote) |
| `@machine` | No | Target machine from `~/.agentwire/machines.json`. Omit for local |

## Configuration Files

| File | Purpose |
|------|---------|
| `~/.agentwire/rooms.json` | Session definitions with roles |
| `~/.agentwire/roles/{role}.md` | Role context files |
| `~/.agentwire/machines.json` | Remote machine config |

## Behavior

1. **Parse arguments** - Extract name, optional path, optional @machine
2. **Look up role in rooms.json** - Get role for this session name (defaults to "worker")
3. **Enforce orchestrator singleton** - If role is "orchestrator", check if tmux session "agentwire" already exists
4. **Check if session exists** - Fail early if tmux session with that name already exists
5. **Resolve path** - Use provided path or default to projects directory
6. **Create tmux session** - Start detached session in the target directory
7. **Start Claude Code with role context** - Send `claude` command with `--context` pointing to role file
8. **Confirm creation** - Report success with session details

## Implementation

### Reading Room Config

```bash
ROOMS_FILE=~/.agentwire/rooms.json
ROLES_DIR=~/.agentwire/roles

# Get role for session (default to "worker" if not defined)
ROLE=$(jq -r --arg name "<name>" '.[$name].role // "worker"' "$ROOMS_FILE")

# Build context file path
ROLE_FILE="$ROLES_DIR/$ROLE.md"
```

### Orchestrator Singleton Check

```bash
# If creating orchestrator session, check for existing agentwire session
if [ "$ROLE" = "orchestrator" ]; then
  if tmux has-session -t agentwire 2>/dev/null; then
    echo "Orchestrator session 'agentwire' already exists. Use /jump agentwire to attach."
    exit 1
  fi
fi
```

### Local Session

```bash
# Check if session exists
tmux has-session -t <name> 2>/dev/null && echo "Session already exists" && exit 1

# Create session in directory
tmux new-session -d -s <name> -c <path>

# Start Claude Code with role context
if [ -f "$ROLE_FILE" ]; then
  tmux send-keys -t <name> "claude --context $ROLE_FILE" Enter
else
  tmux send-keys -t <name> "claude" Enter
fi
```

### Remote Session

```bash
# Get machine config from machines.json
# Check if session exists on remote
ssh <host> "tmux has-session -t <name> 2>/dev/null" && echo "Session already exists on <host>" && exit 1

# Create session and start Claude with role context
ssh <host> "tmux new-session -d -s <name> -c <path> && tmux send-keys -t <name> 'claude' Enter"
```

## Examples

### Local session with default path

```
/new api
```

Creates:
- Session: `api`
- Directory: `~/projects/api`
- Location: local machine

### Local session with custom path

```
/new experiment ~/projects/ml-experiment
```

Creates:
- Session: `experiment`
- Directory: `~/projects/ml-experiment`
- Location: local machine

### Remote session

```
/new ml @gpu-server
```

Creates:
- Session: `ml`
- Directory: `{projects_dir}/ml` on gpu-server
- Location: gpu-server

## Error Handling

| Error | Message |
|-------|---------|
| Orchestrator exists | "Orchestrator session 'agentwire' already exists. Use /jump agentwire to attach." |
| Session exists (local) | "Session 'name' already exists locally. Use `/jump name` to attach." |
| Session exists (remote) | "Session 'name' already exists on machine. Use `/jump name@machine` to attach." |
| Machine not found | "Machine 'machine' not found in ~/.agentwire/machines.json" |

## Related Skills

- `/jump` - Get attach instructions for a tmux session
- `/sessions` - List all Claude Code sessions
- `/kill` - Kill a tmux session
- `/spawn` - Smart create with existence check
