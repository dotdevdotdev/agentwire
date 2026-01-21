# OpenCode Quick Start

Get up and running with OpenCode in AgentWire in 5 minutes.

## Prerequisites

Before installing, ensure you have:

| Requirement | Minimum | Check |
|-------------|---------|-------|
| **OpenCode CLI** | Latest | `opencode --version` |
| **Python** | 3.10+ | `python3 --version` |
| **tmux** | Any recent | `tmux -V` |
| **ffmpeg** | Any recent | `ffmpeg -version` |
| **AgentWire** | 1.0.0+ | `agentwire --version` |

## Installation

### Step 1: Install OpenCode CLI

```bash
# Install via npm
npm install -g @opencode-ai/cli

# Verify installation
opencode --version
```

### Step 2: Configure OpenCode

OpenCode requires minimal configuration. Create a config:

```bash
# Initialize OpenCode config
opencode init

# This creates ~/.config/opencode/config.json
```

### Step 3: Configure AgentWire

Configure AgentWire to use OpenCode as the default agent:

```bash
# Run interactive setup
agentwire init

# Or manually edit ~/.agentwire/config.yaml
cat > ~/.agentwire/config.yaml << 'EOF'
agent:
  command: "opencode"
server:
  host: "0.0.0.0"
  port: 8765
tts:
  backend: "runpod"
EOF
```

### Step 4: Generate SSL Certificates (Required for Browser Access)

```bash
agentwire generate-certs
```

## First Session

Create your first OpenCode session:

```bash
# Create a new session
agentwire new -s myproject

# Send a task
agentwire send -s myproject "Create a simple Python web server"

# View output
agentwire output -s myproject
```

Or use the web interface:

```bash
# Start the portal
agentwire portal start

# Open in browser
# https://localhost:8765
```

## Project Configuration

For consistent session types per project, create `.agentwire.yml`:

```yaml
# ~/projects/myproject/.agentwire.yml
type: "standard"  # Universal type (maps to opencode-bypass)
roles:
  - agentwire
```

Now `agentwire new -s myproject` will automatically use the correct configuration.

## Session Types

OpenCode supports three main session types:

| Type | Command Equivalent | Use Case |
|------|-------------------|----------|
| **opencode-bypass** | `opencode` | Full automation, no permission prompts |
| **opencode-prompted** | `opencode` with permission checks | Semi-automated, user approval required |
| **opencode-restricted** | `opencode` with tool restrictions | Worker, no voice/AskUserQuestion |

Or use universal types (recommended):

| Universal Type | OpenCode Maps To |
|---------------|-----------------|
| **standard** | opencode-bypass |
| **voice** | opencode-prompted |
| **worker** | opencode-restricted |

## Voice Integration

OpenCode works seamlessly with AgentWire's voice features:

```bash
# Speak to your agent
agentwire say "Hello, can you help me debug?"

# Start listening (push-to-talk)
agentwire listen start
# ... speak ...
agentwire listen stop
```

## Roles

AgentWire roles work with OpenCode:

```bash
# Create session with role
agentwire new -s myproject --roles agentwire

# Or in project config
echo 'roles: [agentwire]' >> ~/projects/myproject/.agentwire.yml
```

## Troubleshooting

### "opencode: command not found"

**Solution:** Install OpenCode CLI:

```bash
npm install -g @opencode-ai/cli
```

### "Permission denied" when starting session

**Solution:** Check OpenCode configuration:

```bash
opencode init
opencode doctor
```

### No audio from agentwire say

**Solution:** Check TTS configuration and portal connection:

```bash
# Check TTS status
agentwire tts status

# Check portal status
agentwire portal status
```

### Session not responding

**Solution:** Check session output for errors:

```bash
agentwire output -s myproject
```

## Next Steps

- **Full session types reference:** See [SESSION_TYPES.md](SESSION_TYPES.md)
- **Configuration guide:** See [OpenCode Integration](opencode-integration.md)
- **Troubleshooting:** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Migration from Claude Code:** See [Migration Guide](MIGRATION_GUIDE.md)

## Example Workflows

### Basic Automation

```bash
# Create automated session
agentwire new -s automation --type opencode-bypass
agentwire send -s automation "Automate daily backup script"
```

### Voice-First Development

```bash
# Create voice-enabled session
agentwire new -s voice-work --type opencode-prompted
agentwire portal start
# Open browser, use push-to-talk
```

### Worker Session (No Voice)

```bash
# Spawn worker pane
agentwire spawn --roles worker
# Worker uses opencode-restricted type
```

## Common Questions

**Q: Can I use OpenCode and Claude Code together?**

A: Yes! Different sessions can use different agents. Configure per-project in `.agentwire.yml` or use `--type` flag.

**Q: Do I need to configure LLM providers for OpenCode?**

A: Yes, OpenCode needs LLM provider configuration. Run `opencode init` to configure.

**Q: Which session type should I use?**

A: Use **standard** for most automation workflows, **voice** for voice-first development, and **worker** for background tasks.

**Q: How do I switch from Claude Code to OpenCode?**

A: Update `agent.command` in `~/.agentwire/config.yaml` from `claude --dangerously-skip-permissions` to `opencode`. See [Migration Guide](MIGRATION_GUIDE.md) for details.
