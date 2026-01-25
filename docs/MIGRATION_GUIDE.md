# Migration Guide: Claude Code to OpenCode

Complete guide for migrating from Claude Code to OpenCode in AgentWire.

## Overview

This guide helps you migrate your existing AgentWire setup from Claude Code to OpenCode while maintaining your workflows and configurations.

## What Changes

| Aspect | Claude Code | OpenCode |
|--------|-------------|----------|
| **CLI command** | `claude` | `opencode` |
| **Permissions** | CLI flags (`--dangerously-skip-permissions`) | Environment variable (`OPENCODE_PERMISSION`) |
| **Role instructions** | `--append-system-prompt` flag | Prepended to first message |
| **Tool control** | `--tools` flag | Agent config or AgentWire filtering |
| **Session types** | `claude-*` | `opencode-*` or universal types |
| **Model selection** | `--model` flag | Agent config |

## What Stays the Same

- ✅ **tmux session management** - No changes to session handling
- ✅ **Voice integration** - TTS/STT work identically
- ✅ **Role files** - Same role format and location
- ✅ **Portal interface** - Web UI unchanged
- ✅ **Configuration structure** - Same config files and format
- ✅ **CLI commands** - Same AgentWire commands work with both agents

## Migration Steps

### Step 1: Install OpenCode

```bash
# Install OpenCode CLI
npm install -g @opencode-ai/cli

# Verify installation
opencode --version
```

### Step 2: Initialize OpenCode Config

```bash
# Run OpenCode initialization
opencode init

# This creates ~/.config/opencode/config.json
# Configure your LLM provider here
```

### Step 3: Update AgentWire Config

Edit `~/.agentwire/config.yaml`:

```yaml
# Before
agent:
  command: "claude --dangerously-skip-permissions"

# After
agent:
  command: "opencode"
```

**Optional:** Add OpenCode-specific settings:

```yaml
agent:
  command: "opencode"

# OpenCode-specific
opencode:
  model: "claude-3-5-sonnet-20241022"
  permission: '{"*":"allow"}'  # Default permissions
```

### Step 4: Migrate Session Types

Update project `.agentwire.yml` files:

#### Option A: Use Universal Types (Recommended)

Universal types work with both agents:

```yaml
# Before (Claude Code specific)
type: "claude-bypass"

# After (universal)
type: "standard"
```

```yaml
# Before
type: "claude-restricted"

# After
type: "worker"
```

```yaml
# Before
type: "claude-prompted"

# After
type: "voice"
```

#### Option B: Use OpenCode-Specific Types

```yaml
# Before
type: "claude-bypass"

# After
type: "opencode-bypass"
```

### Step 5: Verify Role Files

Role files remain unchanged, but verify content:

```bash
# Check role files exist
ls ~/.agentwire/roles/

# Verify role content
cat ~/.agentwire/roles/agentwire.md
```

**No changes needed to role format!** Role instructions work automatically with OpenCode.

### Step 6: Test Migration

```bash
# Create test session
agentwire new -s test-opencode

# Send test message
agentwire send -s test-opencode "Hello, can you help me?"

# Verify output
agentwire output -s test-opencode

# Clean up
agentwire kill -s test-opencode
```

## Migration Examples

### Example 1: Simple Project

**Before (Claude Code):**

```yaml
# ~/projects/myapp/.agentwire.yml
type: "claude-bypass"
roles:
  - agentwire
```

**After (OpenCode):**

```yaml
# ~/projects/myapp/.agentwire.yml
type: "standard"  # Universal type
roles:
  - agentwire
```

**Config change:**

```yaml
# ~/.agentwire/config.yaml
agent:
  command: "opencode"  # Changed from claude --dangerously-skip-permissions
```

### Example 2: Orchestrator + Workers

**Before:**

```yaml
# ~/projects/myapp/.agentwire.yml
type: "claude-bypass"
roles:
  - agentwire
```

**After:**

```yaml
# ~/projects/myapp/.agentwire.yml
type: "standard"
roles:
  - agentwire
```

**Usage:**

```bash
# Same commands work!
agentwire new -s myapp
agentwire spawn --roles worker  # Worker uses universal "worker" type
```

### Example 3: Voice-First Workflow

**Before:**

```yaml
# ~/projects/myapp/.agentwire.yml
type: "claude-prompted"
```

**After:**

```yaml
# ~/projects/myapp/.agentwire.yml
type: "voice"
```

**Usage:**

```bash
# Same workflow!
agentwire portal start
agentwire new -s voice-dev
# Use push-to-talk in browser
```

### Example 4: Multiple Session Types

**Before:**

```yaml
# ~/projects/orchestrator/.agentwire.yml
type: "claude-bypass"

# ~/projects/worker/.agentwire.yml
type: "claude-restricted"
```

**After:**

```yaml
# ~/projects/orchestrator/.agentwire.yml
type: "standard"

# ~/projects/worker/.agentwire.yml
type: "worker"
```

## Advanced Migration

### Migrating Custom Roles with Tool Restrictions

**Claude Code (with --tools flag):**

```markdown
# ~/.agentwire/roles/custom.md
## Tools
Bash
Edit

## Model
sonnet
```

**OpenCode (AgentWire filtering):**

```markdown
# ~/.agentwire/roles/custom.md
## Tools
Bash
Edit

## Disallowed Tools
Write

## Model
claude-3-5-sonnet-20241022
```

**Note:** For OpenCode, AgentWire filters tools before sending to the agent.

### Migrating Session History

Session history is preserved, but sessions need to be recreated:

```bash
# List history
agentwire history list

# Resume session (this forks into new worktree)
agentwire history resume <session-id>

# New session will use OpenCode (configured in config.yaml)
```

### Migrating Worktrees

Worktrees work identically, no changes needed:

```bash
# Same commands work!
agentwire fork -s myproject -b feature-xyz

# Fork preserves session type and config
```

## Troubleshooting Migration Issues

### Issue: Session creation fails

**Symptom:** `agentwire new -s test` fails with errors

**Solution:**

```bash
# Verify OpenCode is installed
opencode --version

# Check OpenCode config
opencode doctor

# Verify AgentWire config
cat ~/.agentwire/config.yaml
```

### Issue: Role instructions not applied

**Symptom:** Role instructions not visible in first message

**Solution:**

```bash
# Test role loading
agentwire roles list
agentwire roles show agentwire

# Create fresh session
agentwire new -s test --roles agentwire
agentwire send -s test "Test"
agentwire output -s test | head -20
```

### Issue: Tools not restricted

**Symptom:** Agent can use disallowed tools

**Solution:**

```bash
# For OpenCode, tool filtering is done by AgentWire
# Verify role has disallowedTools
agentwire roles show worker

# Check if AgentWire filtering is working
# (Look for filtering logs in output)
```

### Issue: Permissions different from Claude Code

**Symptom:** Permission prompts behave differently

**Solution:**

```bash
# OpenCode uses permission environment variable
# Check your session type mapping

# claude-prompted -> opencode-prompted (voice type)
# claude-bypass -> opencode-bypass (standard type)

# Verify in project config
cat ~/projects/myproject/.agentwire.yml
```

### Issue: Model not recognized

**Symptom:** Agent uses wrong model

**Solution:**

```bash
# Update role to use OpenCode model names
cat ~/.agentwire/roles/agentwire.md

# Or set in config.yaml
opencode:
  model: "claude-3-5-sonnet-20241022"
```

## Rollback to Claude Code

If you need to rollback, simply reverse the config change:

```bash
# Update ~/.agentwire/config.yaml
agent:
  command: "claude --dangerously-skip-permissions"

# Update project .agentwire.yml files back to claude-* types
# Or keep universal types (they work with Claude Code too!)
```

## Migration Checklist

- [ ] Install OpenCode CLI (`npm install -g @opencode-ai/cli`)
- [ ] Initialize OpenCode config (`opencode init`)
- [ ] Update `~/.agentwire/config.yaml` to use `opencode`
- [ ] Update project `.agentwire.yml` to use universal types (optional)
- [ ] Verify role files in `~/.agentwire/roles/`
- [ ] Test with new session (`agentwire new -s test`)
- [ ] Verify role instructions in first message
- [ ] Test voice integration (`agentwire portal start`)
- [ ] Test worker spawning (`agentwire spawn`)
- [ ] Update any scripts/documentation that reference Claude Code

## Post-Migration Best Practices

### Use Universal Types

Universal types make it easy to switch between agents:

```yaml
# Recommended
type: "standard"  # Works with both Claude Code and OpenCode

# Not recommended (agent-specific)
type: "claude-bypass"  # Only works with Claude Code
```

### Document Your Agent Choice

Keep a record of which agent you're using:

```yaml
# ~/projects/myproject/.agentwire.yml
# Agent: OpenCode
# Date: 2025-01-20

type: "standard"
roles:
  - agentwire
```

### Test Critical Workflows

After migration, test your most common workflows:

```bash
# 1. Basic task execution
agentwire new -s test
agentwire send -s test "Create a simple script"

# 2. Voice interaction
agentwire portal start
# Use push-to-talk

# 3. Worker coordination
agentwire spawn --roles worker

# 4. Worktree operations
agentwire fork -s test -b feature-xyz
```

## Advanced: Using Both Agents

You can use both Claude Code and OpenCode in parallel:

```yaml
# ~/projects/claude-project/.agentwire.yml
type: "claude-bypass"
```

```yaml
# ~/projects/opencode-project/.agentwire.yml
type: "standard"  # Maps to opencode-bypass with OpenCode configured
```

```bash
# Switch agents in config.yaml as needed
# Or use --type flag to override
agentwire new -s claude-session --type claude-bypass
agentwire new -s opencode-session --type opencode-bypass
```

## Resources

- [OpenCode Quick Start](OPENCODE_QUICKSTART.md) - Getting started with OpenCode
- [Session Types Reference](SESSION_TYPES.md) - Understanding session types
- [OpenCode Role Guide](OPENCODE_ROLES.md) - Using roles with OpenCode
- [OpenCode Documentation](https://docs.opencode.ai) - Official OpenCode docs

## Support

If you encounter issues during migration:

1. Check the troubleshooting section above
2. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
3. Report bugs at https://github.com/dotdevdotdev/agentwire-dev/issues

## Summary

Migrating from Claude Code to OpenCode is straightforward:

1. ✅ Install OpenCode CLI
2. ✅ Update `agent.command` in config.yaml
3. ✅ Optionally migrate to universal session types
4. ✅ Test with a new session
5. ✅ Update any scripts/docs

Most things stay the same: tmux, voice, roles, and CLI commands. The main changes are in how permissions and role instructions are handled.
