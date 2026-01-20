# OpenCode Integration Guide

**Complete guide to using OpenCode with AgentWire.**

## Quick Start

### 1. Install OpenCode

```bash
npm install -g @opencode-ai/cli

# Verify installation
opencode --version
```

### 2. Configure AgentWire

```bash
# Update ~/.agentwire/config.yaml
agent:
  type: "opencode"
  command: "opencode"
  fallback:
    use_agentwire_hooks: true
    use_agentwire_permissions: true
```

### 3. Create OpenCode Agents

```bash
# Create agent directory
mkdir -p ~/.config/opencode/agents

# Create agentwire agent (orchestrator)
cat > ~/.config/opencode/agents/agentwire.md <<'EOF'
---
description: Main orchestrator for AgentWire voice interface
mode: primary
permission:
  "*": "allow"
tools:
  write: true
  edit: true
  bash: true
  question: true
---

You are AgentWire orchestrator. Coordinate tasks and delegate to workers as needed. Use voice to communicate with the user and delegate work to worker panes.
EOF

# Create worker agent
cat > ~/.config/opencode/agents/worker.md <<'EOF'
---
description: Worker pane (no voice, no questions)
mode: subagent
permission:
  question: deny
tools:
  write: true
  edit: true
  bash: true
  question: false
---

Worker agent. Execute tasks delegated by orchestrator without voice interaction or user questions. Focus on code execution and technical implementation.
EOF
```

### 4. Test Integration

```bash
# Create a new session
agentwire new -s test-opencode

# Verify output
agentwire output -s test-opencode -n 20

# Send a task
agentwire send -s test-opencode "Hello from AgentWire with OpenCode!"
```

---

## Session Types with OpenCode

### Standard (Full Access)

**Use:** Orchestrator sessions, voice-controlled automation

```yaml
# .agentwire.yml
type: "standard"
```

**Behavior:**
- Full tool access
- Voice enabled
- No permission prompts (via AgentWire damage control)
- Coordinates with workers

**Agent Config:**
- Mode: `primary`
- Permission: `{"*": "allow"}`
- Tools: All enabled

### Worker (Restricted)

**Use:** Parallel task execution, no voice/questions

```yaml
# .agentwire.yml
type: "worker"
```

**Behavior:**
- No AskUserQuestion tool
- No voice TTS
- Full file access
- Executes tasks delegated by orchestrator

**Agent Config:**
- Mode: `subagent`
- Permission: `{"question": "deny"}`
- Tools: Write, Edit, Bash enabled

### Voice (Prompted)

**Use:** Voice-controlled with safety checks

```yaml
# .agentwire.yml
type: "voice"
```

**Behavior:**
- Voice enabled with TTS
- Permission prompts via AgentWire portal
- Full tool access
- User approval for dangerous operations

**Agent Config:**
- Mode: `primary`
- Permission: `{"*": "ask"}` (for damage control)
- Tools: All enabled

---

## Configuration

### Minimal Config (Quick Start)

```yaml
# ~/.agentwire/config.yaml
agent:
  type: "opencode"
  command: "opencode"
```

### Complete Config (All Options)

```yaml
# ~/.agentwire/config.yaml
agent:
  # Agent type selection
  type: "opencode"  # "claude" | "opencode" | "auto"

  # Command to run
  command: "opencode"

  # OpenCode-specific settings
  opencode:
    model: "anthropic/claude-sonnet-4-20250514"  # Default model
    role: null  # Default role name

  # Fallback behavior for missing features
  fallback:
    # Use AgentWire hooks when OpenCode doesn't support them
    use_agentwire_hooks: true
    # Use AgentWire permission system
    use_agentwire_permissions: true
    # Implement role filtering in AgentWire CLI
    implement_role_filtering: true
    # Prepend role instructions to first message
    prepend_role_instructions: true
    # Warn when features are unavailable
    warn_on_missing: true
```

### Project Config

```yaml
# ~/projects/myproject/.agentwire.yml
type: "standard"  # Session type

roles:
  - agentwire
  - custom-role  # Additional role if needed

voice: "dotdev"  # TTS voice
```

---

## Roles with OpenCode

### Role Discovery Order

OpenCode discovers agents in this order:
1. Project: `.opencode/agents/{name}.md`
2. Global: `~/.config/opencode/agents/{name}.md`
3. Built-in: (none - OpenCode doesn't have bundled agents)

### Creating Custom Roles

**Format (Markdown with frontmatter):**

```markdown
# ~/.config/opencode/agents/custom-role.md
---
description: Role description
mode: primary  # or "subagent"
permission:
  bash:
    "*": "ask"
    "git *": "allow"
  question: deny
tools:
  write: true
  edit: true
  bash: true
  question: false
model: anthropic/claude-sonnet-4-20250514
temperature: 0.3
---

## Role instructions here

You are a specialized agent for...
```

### Frontmatter Fields

| Field | Type | Description |
|--------|-------|-------------|
| `description` | string | Human-readable description (required) |
| `mode` | string | `primary` or `subagent` (required) |
| `permission` | object | Permission rules (optional) |
| `tools` | object | Enable/disable specific tools |
| `model` | string | Override model |
| `temperature` | number | LLM randomness (0.0-1.0) |
| `maxSteps` | number | Max agentic iterations |
| `prompt` | string/file | Custom system prompt |
| `hidden` | boolean | Hide from @ autocomplete |

### Permission Syntax

```yaml
permission:
  # Global default
  "*": "ask"  # "allow" | "ask" | "deny"

  # Tool-specific
  bash:
    "*": "ask"
    "git *": "allow"
    "rm *": "deny"

  # Other tools
  edit:
    "*": "allow"
  question: "deny"
  webfetch: "deny"
```

### Tool Control

```yaml
tools:
  write: true   # Enable Write tool
  edit: true    # Enable Edit tool
  bash: true    # Enable Bash tool
  grep: true    # Enable Grep tool
  glob: true    # Enable Glob tool
  question: false  # Disable AskUserQuestion
  task: true    # Enable Task tool (subagents)
  webfetch: false  # Disable WebFetch
```

---

## Permission System

### AgentWire Permission Dialogs

OpenCode doesn't have native permission dialogs like Claude Code. AgentWire implements permission dialogs at the tmux level.

**Flow:**
```
OpenCode → AgentWire Hook → Portal → User → Portal → AgentWire Hook → OpenCode
```

**What Gets Prompted:**
- Dangerous commands (blocked by damage control)
- Operations matching "ask" patterns
- File operations on protected paths

**Permission States:**
- `allow` - Proceed with operation
- `allow_always` - Allow this type of operation going forward
- `deny` - Block operation
- `custom` - Block with custom message

### Damage Control

AgentWire's damage control system works identically for both Claude Code and OpenCode.

**Protected Operations:**
- 100+ bash command patterns (rm -rf, git push --force, terraform destroy, etc.)
- 66 zero-access paths (secrets, SSH keys, credentials)
- 30+ read-only paths (system dirs, lock files)
- 20+ no-delete paths (agentwire config, git data)

**Checking:**
```bash
# Test if command would be blocked
agentwire safety check "rm -rf /tmp"
# → ✗ Decision: BLOCK (rm with recursive/force flags)

# Check safety status
agentwire safety status
```

---

## Migration from Claude Code

### Automatic Migration

When upgrading AgentWire, existing Claude Code configs are auto-migrated:

```bash
$ agentwire migrate-config
✓ Detected agent: claude
✓ Migrated config to multi-agent format
✓ Old config backed up to ~/.agentwire/config.yaml.backup

Changes:
  - Added agent.type: "claude"
  - Added agent.claude.permissions section
  - Added agent.fallback section

Your existing sessions continue to work.
```

### Manual Migration

If you want to switch to OpenCode:

**Step 1: Install OpenCode**
```bash
npm install -g @opencode-ai/cli
```

**Step 2: Update AgentWire Config**
```bash
cat > ~/.agentwire/config.yaml <<EOF
agent:
  type: "opencode"
  command: "opencode"
  fallback:
    use_agentwire_hooks: true
    use_agentwire_permissions: true
EOF
```

**Step 3: Create OpenCode Agents**
```bash
# Copy agentwire role to OpenCode format
cp agentwire/roles/agentwire.md ~/.config/opencode/agents/

# Convert to OpenCode agent format (add frontmatter)
cat >> ~/.config/opencode/agents/agentwire.md <<'EOF'
---
description: Main orchestrator for AgentWire
mode: primary
permission:
  "*": "allow"
tools:
  write: true
  edit: true
  bash: true
  question: true
---
EOF
```

**Step 4: Test**
```bash
agentwire new -s test-opencode
agentwire send -s test-opencode "Hello from OpenCode!"
```

**Step 5: Update Project Config**
```bash
# For new projects
echo 'type: "standard"' > ~/projects/myproject/.agentwire.yml

# For existing projects, change session type if needed
# claude-bypass → standard
# claude-prompted → voice
# claude-restricted → worker
```

### What Changes

| Feature | Claude Code | OpenCode | Migration Path |
|---------|-------------|----------|----------------|
| Permissions | `--dangerously-skip-permissions` | `permission: {"*": "allow"}` | Config file |
| Tool whitelist | `--tools Bash,Edit` | Agent config tools section | Config file |
| System prompt | `--append-system-prompt` | Prepend to first message | Role file |
| Session types | CLI flags | AgentWire role types | Universal types |

---

## Troubleshooting

### Issue: "OpenCode doesn't support --tools flag"

**Symptom:** Warning message when using roles with OpenCode.

**Solution:** This is expected. AgentWire implements role filtering for you.

**What happens:**
- OpenCode receives all tools enabled
- AgentWire CLI filters output to match role restrictions
- Functionally equivalent to Claude Code's `--tools` flag

### Issue: "OpenCode doesn't support permission dialogs"

**Symptom:** Warning message when using voice sessions with OpenCode.

**Solution:** AgentWire uses portal-based permission dialogs.

**What happens:**
- Damage control hooks block dangerous commands
- Portal shows permission dialogs for "ask" patterns
- Same safety as Claude Code, but implemented at AgentWire level

### Issue: OpenCode sessions not responding

**Symptom:** OpenCode starts but no output in AgentWire.

**Checklist:**
```bash
# 1. Verify OpenCode is installed
opencode --version

# 2. Check agent config exists
ls -la ~/.config/opencode/agents/agentwire.md

# 3. Verify AgentWire config
cat ~/.agentwire/config.yaml | grep agent.type

# 4. Test OpenCode directly
opencode run "test"

# 5. Check AgentWire logs
tail -f ~/.agentwire/logs/portal.log
```

### Issue: Permission dialog not appearing

**Symptom:** Operation should prompt but doesn't show in portal.

**Checklist:**
```bash
# 1. Verify hooks installed
agentwire hooks status

# 2. Check fallback is enabled
cat ~/.agentwire/config.yaml | grep use_agentwire_permissions

# 3. Check portal is running
agentwire portal status

# 4. Test permission API
curl http://localhost:8765/api/permissions/test
```

### Issue: Role restrictions not working

**Symptom:** Worker using tools it shouldn't.

**Checklist:**
```bash
# 1. Verify agent config
cat ~/.config/opencode/agents/worker.md | grep tools

# 2. Check role filtering is enabled
cat ~/.agentwire/config.yaml | grep implement_role_filtering

# 3. Check worker is using correct agent
tmux capture-pane -t mysession-worker -p
# Should see "Worker agent..." in first line

# 4. Test safety directly
agentwire safety check "AskUserQuestion('test')"
```

---

## Advanced Topics

### Using OpenCode HTTP API

For better session management, use OpenCode's HTTP server instead of spawning CLI processes:

```yaml
# ~/.agentwire/config.yaml
agent:
  type: "opencode"
  command: "opencode serve --port 8766"  # Run as server

  opencode:
    use_http_api: true
    port: 8766
```

**Benefits:**
- Single OpenCode instance handles all sessions
- Better resource usage
- Programmatic access to session management
- Real-time updates via WebSocket

### Custom OpenCode Plugins

Create plugins for advanced customization:

```javascript
// ~/.config/opencode/plugins/agentwire-integration.js
import type { Plugin } from "@opencode-ai/plugin"

export const AgentWirePlugin: Plugin = async ({ project, client, $ }) => {
  return {
    "session.created": async (input, output) => {
      // Notify AgentWire when session starts
      await fetch("http://localhost:8765/api/session-created", {
        method: "POST",
        body: JSON.stringify({ sessionId: output.sessionID })
      })
    }
  }
}
```

**Install:**
```bash
mkdir -p ~/.config/opencode/plugins
# Copy plugin file to ~/.config/opencode/plugins/
```

### Multiple Providers

OpenCode supports 75+ LLM providers:

```yaml
# ~/.config/opencode/agents/gemini-orchestrator.md
---
description: Orchestrator using Google Gemini
mode: primary
model: google/gemini-1.5-pro
---

You are orchestrator using Google Gemini for responses.
```

**Switch providers per session:**
```yaml
# .agentwire.yml
agent:
  opencode:
    role: "gemini-orchestrator"
```

---

## FAQ

**Q: Can I use Claude Code and OpenCode simultaneously?**

A: Yes. Set `agent.type: "auto"` and AgentWire will detect from the command string. You can also create session-specific overrides in `.agentwire.yml`.

**Q: Do I need to migrate my roles?**

A: Not directly. OpenCode can read `~/.claude/skills/` as fallback. However, converting to OpenCode agent format gives you more control.

**Q: What happens to my Claude Code hooks when switching to OpenCode?**

A: They're ignored (not harmful). AgentWire installs its own hooks at the tmux level when using OpenCode.

**Q: Is OpenCode faster/slower than Claude Code?**

A: Similar performance. OpenCode has the advantage of server mode, which can reduce startup time for multiple sessions.

**Q: Can I use OpenCode's web interface instead of AgentWire portal?**

A: Yes. Run `opencode web` and connect to `http://localhost:8766`. However, you lose AgentWire's voice integration and multi-session management.

**Q: How do I switch back to Claude Code?**

A: Change `agent.type: "claude"` in config and ensure Claude is installed: `npm install -g @anthropic-ai/claude-code`

**Q: Does OpenCode work with remote machines?**

A: Yes. AgentWire's remote machine support works regardless of the AI agent. OpenCode runs on the remote machine just like Claude Code would.

**Q: What about OpenCode's TUI?**

A: You can use OpenCode's TUI directly via `opencode`, but AgentWire provides its own portal interface with voice integration and session management.

---

## Resources

- **OpenCode Docs:** https://opencode.ai
- **OpenCode GitHub:** https://github.com/opencode-ai/opencode
- **AgentWire Docs:** https://www.agentwire.dev
- **AgentWire GitHub:** https://github.com/dotdevdotdev/agentwire-dev
