---
name: spawn
description: Smart orchestrator session creation - checks if exists, offers options or recreates with --force.
agent: orchestrator
allowed-tools:
  - Task
  - Bash(agentwire *)
  - Bash(remote-say *)
  - AskUserQuestion
---

# /spawn

Smart orchestrator session creation with existence check. Creates sessions with `--context ~/.agentwire/roles/orchestrator.md` loaded. Unlike `/new` which fails if a session exists, `/spawn` checks first and offers options.

## Usage

```
/spawn <name> [--force]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Session name to spawn |
| `--force` | No | Kill existing session and recreate fresh |

## Configuration Files

| File | Purpose |
|------|---------|
| `~/.agentwire/rooms.json` | Session definitions with roles, models, paths |

## Behavior

1. **Check if session exists** - Look for running tmux session with that name
2. **If exists without --force** - Show helpful options (attach or recreate)
3. **If exists with --force** - Cleanly kill existing (send /exit first), then create fresh
4. **If doesn't exist** - Create new orchestrator session with role loaded via `--context`

Sessions created with `/spawn` are orchestrators that:
- Load `~/.agentwire/roles/orchestrator.md` via `--context` flag
- Use voice (remote-say) for user communication
- Spawn worker agents via Task tool for execution
- Cannot edit files directly (blocked via allowed-tools)

## Examples

### Session exists (no --force)

```
/spawn assistant
```

Output:
```
Session 'assistant' already exists.

Options:
  /jump assistant          # Get attach instructions
  /spawn assistant --force # Kill and recreate
```

### Session exists (with --force)

```
/spawn assistant --force
```

Output:
```
Killing existing session 'assistant'...
Creating fresh session 'assistant'...
Spawned session 'assistant' in ~/projects/assistant
Role: chatbot
Model: opus
```

### Session doesn't exist

```
/spawn api
```

Output:
```
Spawned orchestrator session 'api' in ~/projects/api
Role: orchestrator
```

## Why Use /spawn Instead of /new

| Scenario | /new | /spawn |
|----------|------|--------|
| Session exists | Fails with error | Shows options |
| Want to restart fresh | Must `/kill` then `/new` | Just `--force` |
| Unsure if running | Check first manually | Just run it |

`/spawn` is the "smart" version - it handles the common case of "I want this session running, create or restart as needed."

## Related Skills

- `/new` - Create session (fails if exists)
- `/kill` - Cleanly kill a session
- `/jump` - Get attach instructions
- `/sessions` - List all sessions
