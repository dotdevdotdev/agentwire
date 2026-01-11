---
name: spawn
description: Smart session creation - checks if exists, offers options or recreates with --force.
---

# /spawn

Smart session creation with existence check. Unlike `/new` which fails if a session exists, `/spawn` checks first and offers options.

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
4. **If doesn't exist** - Create new session from room config (path, model, role)

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
Role: worker
Model: opus
```

### Session doesn't exist

```
/spawn api
```

Output:
```
Spawned session 'api' in ~/projects/api
Role: worker
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
