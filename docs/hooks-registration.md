# Claude Code Hooks Registration

This document explains how to register the orchestrator and worker PreToolUse hooks in your Claude Code settings.

## Hook Scripts

Two hook scripts enforce the orchestrator-worker separation:

| Hook | Location | Purpose |
|------|----------|---------|
| `orchestrator-blocks.sh` | `~/.claude/hooks/` | Blocks file operations (Edit, Write, Read, Glob, Grep) for orchestrator sessions |
| `worker-blocks.sh` | `~/.claude/hooks/` | Blocks user interaction (AskUserQuestion, remote-say, say) for worker sessions |

## Registration Steps

### Manual Registration

Edit `~/.claude/settings.json` to add the hooks under the `hooks` section:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/orchestrator-blocks.sh",
            "timeout": 5,
            "description": "Block Edit in orchestrator sessions"
          }
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/orchestrator-blocks.sh",
            "timeout": 5,
            "description": "Block Write in orchestrator sessions"
          }
        ]
      },
      {
        "matcher": "Read",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/orchestrator-blocks.sh",
            "timeout": 5,
            "description": "Block Read in orchestrator sessions"
          }
        ]
      },
      {
        "matcher": "Glob",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/orchestrator-blocks.sh",
            "timeout": 5,
            "description": "Block Glob in orchestrator sessions"
          }
        ]
      },
      {
        "matcher": "Grep",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/orchestrator-blocks.sh",
            "timeout": 5,
            "description": "Block Grep in orchestrator sessions"
          }
        ]
      },
      {
        "matcher": "AskUserQuestion",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/worker-blocks.sh",
            "timeout": 5,
            "description": "Block AskUserQuestion in worker sessions"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/worker-blocks.sh",
            "timeout": 5,
            "description": "Block voice commands in worker sessions"
          }
        ]
      }
    ]
  }
}
```

### Automated Registration (Future)

An `agentwire hooks install` command could be added to automate hook registration:

```bash
# Future command
agentwire hooks install
```

This would:
1. Read existing `~/.claude/settings.json`
2. Merge hook definitions
3. Write updated settings
4. Validate JSON structure

## How Hooks Work

### Orchestrator Hooks

When an orchestrator session attempts a file operation:

1. Claude Code calls `orchestrator-blocks.sh` before executing the tool
2. Script receives tool use JSON via stdin
3. Script checks if tool is in `BLOCKED_TOOLS` array (Edit, Write, Read, Glob, Grep)
4. If blocked: returns `{"decision": "deny", "message": "..."}`
5. If allowed: returns `{"decision": "allow"}`

**Blocked tools:**
- Edit - Cannot modify files
- Write - Cannot create files
- Read - Cannot read files
- Glob - Cannot search file patterns
- Grep - Cannot search file contents

**Allowed tools:**
- Task - Spawn worker subagents
- Bash - Only for agentwire commands and remote-say
- AskUserQuestion - Clarify with user

### Worker Hooks

When a worker session attempts user interaction:

1. Claude Code calls `worker-blocks.sh` before executing the tool
2. Script receives tool use JSON via stdin
3. Script checks:
   - If tool is `AskUserQuestion` → DENY
   - If tool is `Bash` and command contains `remote-say` or `say` → DENY
4. Returns appropriate decision

**Blocked tools:**
- AskUserQuestion - Cannot ask user questions
- Bash(remote-say) - Cannot speak to user
- Bash(say) - Cannot speak locally

**Allowed tools:**
- Edit, Write, Read - Full file operations
- Bash - Commands, tests, builds (except voice)
- Task - Spawn subagents for parallel work
- Glob, Grep - Search and explore
- TodoWrite - Track complex work

## Hook Behavior

### Global vs Role-Specific

Currently, these hooks apply **globally** to all Claude Code sessions. The hooks check the tool name but don't distinguish between orchestrator and worker sessions.

**Future improvement**: Hooks could check session context to apply rules only to appropriate roles:

```bash
# Future: Check if session is orchestrator
ROLE=$(cat ~/.agentwire/rooms.json | jq -r ".\"$SESSION_NAME\".role // \"\"")

if [[ "$ROLE" == "orchestrator" ]] && [[ "$TOOL_NAME" == "Edit" ]]; then
  # Block Edit for orchestrator
  ...
fi
```

For now, hooks apply to all sessions. This is acceptable because:
- Orchestrator sessions are marked in `rooms.json` and started with role file
- Worker sessions are Task subagents (ephemeral, don't have persistent names)
- Hooks provide helpful messages indicating proper separation

### Testing Hooks

Test hooks in a Claude Code session:

**Test orchestrator blocks:**
```
# Start Claude Code session
claude

# Try to edit a file (should be blocked)
/edit test.txt

# Expected: "Orchestrator cannot modify files. Spawn worker via Task tool."
```

**Test worker blocks:**
```
# Start Claude Code session
claude

# Try AskUserQuestion (should be blocked)
# (in session, attempt to use the tool)

# Expected: "Workers cannot interact with user. Orchestrator handles that."
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Hook not firing | Not registered in settings.json | Check `~/.claude/settings.json` has hook entries |
| Permission denied | Script not executable | `chmod +x ~/.claude/hooks/*.sh` |
| JSON parse error | Invalid settings.json | Validate JSON with `jq . ~/.claude/settings.json` |
| Hook returns wrong decision | Logic error in script | Test script manually: `echo '{"tool":"Edit"}' \| ~/.claude/hooks/orchestrator-blocks.sh` |
| Timeout errors | Hook takes too long | Increase `timeout` value in settings.json |

## Manual Testing

Test hooks directly from command line:

```bash
# Test orchestrator hook blocking Edit
echo '{"tool":"Edit","params":{"file_path":"/tmp/test.txt"}}' | ~/.claude/hooks/orchestrator-blocks.sh
# Expected output: {"decision":"deny", "message":"..."}

# Test orchestrator hook allowing Task
echo '{"tool":"Task","params":{}}' | ~/.claude/hooks/orchestrator-blocks.sh
# Expected output: {"decision":"allow"}

# Test worker hook blocking AskUserQuestion
echo '{"tool":"AskUserQuestion","params":{}}' | ~/.claude/hooks/worker-blocks.sh
# Expected output: {"decision":"deny", "message":"..."}

# Test worker hook blocking remote-say in Bash
echo '{"tool":"Bash","params":{"command":"remote-say \"hello\""}}' | ~/.claude/hooks/worker-blocks.sh
# Expected output: {"decision":"deny", "message":"..."}

# Test worker hook allowing normal Bash
echo '{"tool":"Bash","params":{"command":"npm test"}}' | ~/.claude/hooks/worker-blocks.sh
# Expected output: {"decision":"allow"}
```

## Hook Dependencies

Hooks require:
- `bash` - Shell interpreter
- `jq` - JSON parser (install: `brew install jq` on macOS)

If `jq` is not available, hooks will fail silently. Ensure `jq` is installed:

```bash
which jq
# Should output: /usr/local/bin/jq or similar
```

## Next Steps

After registering hooks:

1. Test in a Claude Code session (manual testing above)
2. Create orchestrator session: `agentwire new myproject`
3. Verify orchestrator blocks file operations (wave completed when confirmed)
4. Test worker spawning via Task tool
5. Verify worker blocks user interaction (wave completed when confirmed)

## References

- Claude Code Hooks Documentation: https://docs.claudecode.com/hooks
- `~/.agentwire/roles/orchestrator.md` - Orchestrator role definition
- `~/.agentwire/roles/worker.md` - Worker role definition
- Mission: `docs/missions/orchestrator-worker-pairing.md`
