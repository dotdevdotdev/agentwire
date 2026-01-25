# OpenCode Role Guide

How to use AgentWire roles with OpenCode, including role creation, configuration, and examples.

## Overview

AgentWire roles work seamlessly with OpenCode, but there are key differences in how role instructions are applied:

| Aspect | Claude Code | OpenCode |
|--------|-------------|----------|
| **Role instructions** | Added via `--append-system-prompt` flag | Prepended to first message |
| **Tool control** | Via `--tools` flag | Via agent config or AgentWire filtering |
| **Model override** | Via `--model` flag | Via agent config or model field |
| **Execution** | Instant (system prompt modified) | First message only (instructions prepended) |

## Built-in Roles

AgentWire includes built-in roles in `agentwire/roles/`:

### agentwire

**Purpose:** Main orchestrator role for voice-first development

**Features:**
- Voice input handling
- Worker coordination
- Project management

**Use with:** `--type standard` or `--type opencode-bypass`

```bash
agentwire new -s orchestrator --roles agentwire
```

### worker

**Purpose:** Worker pane role for focused task execution

**Features:**
- No voice input
- No AskUserQuestion
- Focused on code execution

**Use with:** `--type worker` or `--type opencode-restricted`

```bash
agentwire spawn --roles worker
```

### chatbot

**Purpose:** Chatbot personality for conversational interactions

**Use with:** `--type standard`

```bash
agentwire new -s chatbot --roles chatbot
```

### voice

**Purpose:** Voice input handling role

**Use with:** `--type voice` or `--type opencode-prompted`

```bash
agentwire new -s voice-bot --roles voice
```

## Creating Custom Roles

### Role File Structure

Create role files in `~/.agentwire/roles/`:

```markdown
# ~/.agentwire/roles/frontend-dev.md

# Frontend Developer Role

You are an expert frontend developer specializing in React, TypeScript, and modern web development.

## Guidelines

- Use TypeScript for type safety
- Follow React best practices
- Write clean, component-based code
- Test all changes before committing
```

### Role Configuration Fields

| Field | Type | OpenCode Implementation |
|-------|------|-------------------------|
| **instructions** | string | Prepended to first message |
| **tools** | list | Filtered by AgentWire CLI |
| **disallowedTools** | list | Filtered by AgentWire CLI |
| **model** | string | Set in OpenCode config or passed to agent |

### Example: Custom Role with All Fields

```markdown
# ~/.agentwire/roles/database-admin.md

# Database Administrator

You are a database administrator with expertise in PostgreSQL, Redis, and data migration.

## Instructions

- Always backup before making changes
- Use transactions for data modifications
- Test migrations on staging first

## Tools

Bash
Edit
Write

## Disallowed Tools

AskUserQuestion

## Model

claude-3-5-sonnet-20241022
```

**Note:** For OpenCode, `tools` and `disallowedTools` are filtered by AgentWire CLI before sending to the agent, as OpenCode doesn't support CLI flags for these.

## Using Roles with OpenCode

### Basic Usage

```bash
# Create session with role
agentwire new -s myproject --roles agentwire

# Use multiple roles (merged)
agentwire new -s myproject --roles agentwire,custom-role
```

### Project Configuration

```yaml
# ~/projects/myproject/.agentwire.yml
type: "standard"
roles:
  - agentwire
  - custom-role
```

### Spawning Workers with Roles

```bash
# Spawn worker pane with worker role
agentwire spawn --roles worker
```

## Role Instruction Prepending (OpenCode)

When using OpenCode, role instructions are prepended to the first message sent to the agent.

### How It Works

```python
# AgentWire CLI prepends role instructions
role_instructions = "You are an expert frontend developer..."
user_message = "Create a React component"

# First message sent to agent:
combined_message = f"""{role_instructions}

---

{user_message}"""
```

### Example Flow

```bash
# 1. Create OpenCode session with role
agentwire new -s myproject --type opencode-bypass --roles agentwire

# 2. Send first message
agentwire send -s myproject "Create a REST API"

# 3. First message to OpenCode:
"""
# AgentWire Orchestrator

You are coordinating voice-first development...

---

Create a REST API
"""

# 4. Send second message
agentwire send -s myproject "Add authentication"

# 5. Second message to OpenCode (no role instructions):
"Add authentication"
```

### Verification

```bash
# Check first message has role instructions
agentwire output -s myproject | head -20
# Should see role instructions before actual message
```

## Role Merging

When multiple roles are specified, they're merged:

```bash
agentwire new -s myproject --roles agentwire,worker,custom
```

### Merge Priority

1. **Instructions:** Concatenated with separators
2. **Tools:** Union (all tools allowed)
3. **Disallowed tools:** Union (all disallowed)
4. **Model:** Last role's model wins

### Example Merge

**Role 1 (agentwire):**
```markdown
## Tools
Bash
Edit
Write

## Disallowed Tools
(none)
```

**Role 2 (worker):**
```markdown
## Tools
Bash

## Disallowed Tools
AskUserQuestion
```

**Merged Result:**
```markdown
## Tools
Bash
Edit
Write

## Disallowed Tools
AskUserQuestion
```

## Common Role Configurations

### Frontend Developer

```bash
# Create role
cat > ~/.agentwire/roles/frontend.md << 'EOF'
# Frontend Developer

You specialize in React, TypeScript, and modern frontend development.

## Guidelines
- Use TypeScript for type safety
- Follow React best practices
- Test in browser before committing
EOF

# Use role
agentwire new -s frontend --roles frontend
```

### Backend Developer

```bash
cat > ~/.agentwire/roles/backend.md << 'EOF'
# Backend Developer

You specialize in API design, databases, and server-side logic.

## Guidelines
- Document all API endpoints
- Use database migrations
- Implement error handling
EOF

# Use role
agentwire new -s backend --roles backend
```

### DevOps Engineer

```bash
cat > ~/.agentwire/roles/devops.md << 'EOF'
# DevOps Engineer

You specialize in infrastructure, CI/CD, and deployment.

## Guidelines
- Use infrastructure as code
- Test deployments on staging
- Monitor production metrics
EOF

# Use role
agentwire new -s devops --roles devops
```

## Role-based Session Types

### Orchestrator with OpenCode

```bash
# Full automation with orchestrator role
agentwire new -s orchestrator --type opencode-bypass --roles agentwire

# Or use universal type
agentwire new -s orchestrator --type standard --roles agentwire
```

### Worker with OpenCode

```bash
# Worker pane (no voice, no questions)
agentwire spawn --roles worker

# Worker session
agentwire new -s worker --type opencode-restricted --roles worker
```

### Voice-enabled with OpenCode

```bash
# Voice with permission prompts
agentwire new -s voice-bot --type opencode-prompted --roles voice

# Or use universal type
agentwire new -s voice-bot --type voice --roles voice
```

## Advanced: Role Filtering for OpenCode

Since OpenCode doesn't support `--tools` flags, AgentWire can filter tools at the CLI level.

### Example: Limit Tools for OpenCode

```yaml
# ~/.agentwire/roles/limited-worker.md
# Limited Worker

You are a focused worker agent with restricted tool access.

## Tools
Bash

## Disallowed Tools
Edit
Write
AskUserQuestion
```

```bash
# AgentWire will filter Edit/Write tools before sending to OpenCode
agentwire new -s limited --roles limited-worker
```

### Example: No-Edit Role

```yaml
# ~/.agentwire/roles/no-edit.md
# Read-Only Analyst

You analyze code but don't make changes.

## Tools
Bash

## Disallowed Tools
Edit
Write
```

## Debugging Roles

### Check Role Loading

```bash
# List available roles
agentwire roles list

# Show role details
agentwire roles show agentwire
```

### Verify Role Instructions

```bash
# Create session with role
agentwire new -s test --roles agentwire

# Send first message
agentwire send -s test "Hello"

# Check output for role instructions
agentwire output -s test | head -20
```

### Debug Merged Roles

```bash
# Create session with multiple roles
agentwire new -s test --roles agentwire,worker

# Check session info
agentwire info -s test --json
```

## Role Best Practices

### 1. Keep Instructions Concise

```markdown
# Good
# Frontend Developer
Focus on React and TypeScript. Test before committing.

# Bad
# Frontend Developer
You are a frontend developer who has 20 years of experience in React... (too long)
```

### 2. Use Specific Tool Restrictions

```markdown
# Good
## Tools
Bash
Edit

## Disallowed Tools
Write  # Prevent file creation

# Bad
## Tools
*  # Too broad
```

### 3. Test Role Instructions

```bash
# Test with a simple task
agentwire new -s test-role --roles my-custom-role
agentwire send -s test-role "Write hello world"

# Check if instructions are applied correctly
agentwire output -s test-role
```

### 4. Document Your Roles

```markdown
# ~/.agentwire/roles/my-role.md

# My Custom Role

## Purpose
Brief description of what this role does.

## When to Use
- Use case 1
- Use case 2

## Instructions
Actual role instructions here...
```

## Troubleshooting

### Role Instructions Not Applied

**Issue:** Role instructions not visible in first message

**Solution:**
```bash
# Verify role file exists
ls ~/.agentwire/roles/agentwire.md

# Check role content
cat ~/.agentwire/roles/agentwire.md

# Test with fresh session
agentwire kill -s test
agentwire new -s test --roles agentwire
agentwire send -s test "Test"
```

### Tools Not Restricted

**Issue:** Agent can use disallowed tools

**Solution:**
```bash
# Verify role has disallowedTools
agentwire roles show worker

# For OpenCode, tool filtering is done by AgentWire CLI
# Check logs for filtering activity
```

### Multiple Roles Conflict

**Issue:** Roles have conflicting instructions

**Solution:**
```bash
# Merge priority: last role wins for model
# Tools/disallowedTools: union (all applied)

# Test merged result with single session
agentwire new -s test --roles role1,role2
agentwire send -s test "Test"
agentwire output -s test
```

## Examples Repository

See `docs/examples/` for complete examples:

- `frontend-workflow.md` - Frontend development with OpenCode
- `backend-workflow.md` - Backend development with OpenCode
- `multi-agent-workflow.md` - Orchestrator + workers with OpenCode

## Next Steps

- [Session Types Reference](SESSION_TYPES.md) - Understanding different session types
- [OpenCode Integration Guide](opencode-integration.md) - Complete OpenCode setup
- [Migration Guide](MIGRATION_GUIDE.md) - Migrating from Claude Code to OpenCode
