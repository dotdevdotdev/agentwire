# OpenCode Capabilities Investigation Report

Investigation of OpenCode's features and capabilities for integration with AgentWire.

---

## Executive Summary

OpenCode is an open-source AI coding agent with a rich feature set including:
- **CLI and TUI interfaces** with comprehensive command structure
- **Permissions system** with allow/ask/deny granularity
- **Plugin system** with event hooks for extensibility
- **Agent system** with primary/subagent types and tool customization
- **HTTP server API** for programmatic access
- **Skills and rules** for behavior customization

**Key Finding**: OpenCode does NOT have a direct equivalent to Claude Code's `--dangerously-skip-permissions` flag, but offers flexible permission configuration as an alternative.

---

## 1. OpenCode CLI Reference

### Main Commands

| Command | Purpose | Key Flags |
|----------|---------|------------|
| `opencode [project]` | Start TUI | `--port`, `--hostname`, `--model`, `--agent`, `--session`, `--prompt`, `--continue` |
| `opencode run [message]` | Non-interactive execution | `--format`, `--share`, `--model`, `--agent`, `--file`, `--title`, `--attach` |
| `opencode serve` | Start headless HTTP server | `--port`, `--hostname`, `--mdns`, `--cors` |
| `opencode web` | Start server with web interface | Same as `serve` |
| `opencode attach <url>` | Attach TUI to running server | `--dir`, `--session` |
| `opencode agent [command]` | Manage agents | `create`, `list` |
| `opencode auth [command]` | Manage credentials | `login`, `logout`, `list` |
| `opencode mcp [command]` | Manage MCP servers | `add`, `list`, `auth`, `logout` |
| `opencode models [provider]` | List available models | `--refresh`, `--verbose` |
| `opencode session [command]` | Manage sessions | `list` |
| `opencode stats` | Show usage statistics | `--days`, `--tools`, `--models`, `--project` |
| `opencode export [sessionID]` | Export session as JSON | |
| `opencode import <file>` | Import session data | |
| `opencode github [command]` | Manage GitHub agent | `install`, `run` |
| `opencode pr <number>` | Checkout and work on PR | |
| `opencode acp` | Start ACP server | `--cwd`, `--port`, `--hostname` |
| `opencode upgrade [target]` | Update OpenCode | `--method` |
| `opencode uninstall` | Remove OpenCode | `--keep-config`, `--keep-data`, `--dry-run`, `--force` |

### Global Flags

| Flag | Short | Purpose |
|------|-------|---------|
| `--help` | `-h` | Display help |
| `--version` | `-v` | Print version |
| `--print-logs` | | Print logs to stderr |
| `--log-level` | | DEBUG, INFO, WARN, ERROR |
| `--port` | | Server port |
| `--hostname` | | Server hostname |
| `--mdns` | | Enable mDNS discovery |
| `--cors` | | CORS origins |

### Environment Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `OPENCODE` | boolean | Set to `1` when running in OpenCode (similar to `ANTHROPIC_API_KEY` in Claude Code) |
| `OPENCODE_CONFIG` | string | Custom config file path |
| `OPENCODE_CONFIG_DIR` | string | Custom config directory path |
| `OPENCODE_CONFIG_CONTENT` | string | Inline JSON config |
| `OPENCODE_PERMISSION` | string | Inline JSON permissions config |
| `OPENCODE_DISABLE_CLAUDE_CODE` | boolean | Disable reading `.claude` files |
| `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT` | boolean | Disable `~/.claude/CLAUDE.md` |
| `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` | boolean | Disable `.claude/skills` |
| `OPENCODE_SERVER_PASSWORD` | string | HTTP basic auth password |
| `OPENCODE_SERVER_USERNAME` | string | HTTP basic auth username (default: `opencode`) |
| `OPENCODE_CLIENT` | string | Client identifier (default: `cli`) |

### Claude Code Compatibility

OpenCode supports Claude Code's file conventions as fallbacks:

| Claude Code Path | OpenCode Fallback | Can be disabled by |
|------------------|-------------------|---------------------|
| `CLAUDE.md` (project) | Used if no `AGENTS.md` exists | `OPENCODE_DISABLE_CLAUDE_CODE` |
| `~/.claude/CLAUDE.md` | Used if no `~/.config/opencode/AGENTS.md` | `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT` |
| `~/.claude/skills/` | Loaded as skills | `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` |

**Note**: OpenCode has built-in `AGENTS.md` and `skills/` support that takes precedence over Claude Code conventions.

---

## 2. OpenCode Hooks System

OpenCode has a **Plugin System** with extensive event hooks. This is the closest equivalent to Claude Code's hooks.

### Plugin Structure

Plugins are defined as JavaScript/TypeScript modules that export functions returning hook objects:

```typescript
.opencode/plugins/example.ts

import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async ({ project, client, $, directory, worktree }) => {
  return {
    // Hook implementations
  }
}
```

### Available Events

Plugins can subscribe to these event hooks:

#### Tool Events
- `tool.execute.before` - Before tool execution (modify input/output)
- `tool.execute.after` - After tool execution

#### Permission Events
- `permission.replied` - When user responds to permission prompt
- `permission.updated` - When permission state changes

#### Session Events
- `session.created` - New session created
- `session.compacted` - Session context compacted
- `session.deleted` - Session deleted
- `session.diff` - File diff generated
- `session.error` - Session error occurred
- `session.idle` - Session went idle
- `session.status` - Session status changed
- `session.updated` - Session metadata updated

#### Message Events
- `message.part.removed` - Message part removed
- `message.part.updated` - Message part updated
- `message.removed` - Message removed
- `message.updated` - Message updated

#### File Events
- `file.edited` - File edited
- `file.watcher.updated` - File watcher detected change

#### Command Events
- `command.executed` - Slash command executed

#### TUI Events
- `tui.prompt.append` - Prompt text appended
- `tui.command.execute` - Command executed
- `tui.toast.show` - Toast notification shown

#### Server Events
- `server.connected` - Client connected to server

#### LSP Events
- `lsp.client.diagnostics` - LSP diagnostics updated
- `lsp.updated` - LSP state updated

#### Todo Events
- `todo.updated` - Todo list updated

#### Installation Events
- `installation.updated` - Installation state changed

### Plugin Installation Locations

1. **Local plugins**: `.opencode/plugins/`
2. **Global plugins**: `~/.config/opencode/plugins/`
3. **NPM plugins**: Specified in `opencode.json` config

### Plugin Example: Permission Hook

```javascript
.opencode/plugins/permission-hook.js

export const PermissionHook = async ({ project, client, $, directory, worktree }) => {
  return {
    "tool.execute.before": async (input, output) => {
      // Block .env file reads
      if (input.tool === "read" && output.args.filePath.includes(".env")) {
        throw new Error("Do not read .env files")
      }

      // Log all bash commands
      if (input.tool === "bash") {
        console.log(`Executing: ${output.args.command}`)
      }
    },

    "permission.updated": async (input, output) => {
      console.log(`Permission ${output.permissionID} updated to ${output.permission}`)
    }
  }
}
```

### Plugin Example: Compaction Hook

```typescript
.opencode/plugins/compaction.ts

import type { Plugin } from "@opencode-ai/plugin"

export const CompactionPlugin: Plugin = async (ctx) => {
  return {
    "experimental.session.compacting": async (input, output) => {
      // Inject custom context during compaction
      output.context.push(`
## Custom AgentWire Context
- Current session role: agentwire | worker
- Active tmux session: ${process.env.TMUX_SESSION_NAME}
- Pane context: ${process.env.TMUX_PANE}
      `)
    }
  }
}
```

---

## 3. OpenCode Permission System

OpenCode uses a flexible permission system with three states: `allow`, `ask`, `deny`.

### Permission States

| State | Behavior |
|-------|----------|
| `allow` | Tool runs without approval |
| `ask` | User prompted for approval (once/always/reject) |
| `deny` | Tool is blocked |

### Configuration

Global permissions in `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "*": "ask",
    "bash": "allow",
    "edit": "deny"
  }
}
```

### Granular Rules (Object Syntax)

Permissions can use patterns for fine-grained control:

```json
{
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "npm *": "allow",
      "rm *": "deny",
      "grep *": "allow"
    },
    "edit": {
      "*": "deny",
      "packages/web/src/content/docs/*.mdx": "allow"
    }
  }
}
```

**Rules are evaluated by pattern match, with the last matching rule winning.**

### Available Permissions

| Permission | Purpose | Matches |
|------------|---------|----------|
| `read` | File reading | File path |
| `edit` | File modifications | All write/edit/patch operations |
| `glob` | File globbing | Glob pattern |
| `grep` | Content search | Regex pattern |
| `list` | Directory listing | Directory path |
| `bash` | Shell commands | Parsed commands (e.g., `git status --porcelain`) |
| `task` | Subagent invocation | Subagent name |
| `skill` | Skill loading | Skill name |
| `lsp` | LSP queries | Non-granular |
| `todoread`, `todowrite` | Todo list | - |
| `webfetch` | URL fetching | URL |
| `websearch`, `codesearch` | Web/code search | Query |
| `external_directory` | Files outside project | - |
| `doom_loop` | Repeated tool calls | - |
| `question` | Ask user questions | - |

### Default Permissions

```json
{
  "permission": {
    "read": {
      "*": "allow",
      "*.env": "deny",
      "*.env.*": "deny",
      "*.env.example": "allow"
    },
    "doom_loop": "ask",
    "external_directory": "ask"
  }
}
```

**Most permissions default to `"allow"` except `doom_loop` and `external_directory`.**

### Per-Agent Permissions

Agent-specific permissions override global config:

```json
{
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "git commit *": "deny",
      "git push *": "deny"
    }
  },
  "agent": {
    "build": {
      "permission": {
        "bash": {
          "*": "ask",
          "git *": "allow",
          "git commit *": "ask",
          "git push *": "deny"
        }
      }
    }
  }
}
```

### Permission in Markdown Agents

```yaml
# ~/.config/opencode/agents/worker.md
---
description: Worker agent (no voice, no questions)
mode: subagent
permission:
  question: deny
  bash:
    "*": "allow"
    "git push*": "deny"
  webfetch: deny
tools:
  write: true
  edit: true
  bash: true
---

Worker agent with voice and questions disabled.
```

### Ask Behavior

When `ask` is triggered, users see three options:
- **once** - Approve just this request
- **always** - Approve future requests matching suggested patterns (for current session)
- **reject** - Deny the request

The tool provides suggested patterns for "always" (e.g., `git status*` for git commands).

### Inline Permission via Environment Variable

```bash
export OPENCODE_PERMISSION='{"bash":"allow","edit":"deny"}'
opencode run "Do something"
```

---

## 4. OpenCode Session Types

OpenCode has two types of agents with different modes and tool access.

### Agent Types

| Type | Description | Usage |
|------|-------------|--------|
| **Primary** | Main assistants users interact with directly | Cycled via Tab key or `switch_agent` keybind |
| **Subagent** | Specialized assistants invoked by primary agents or via @ mention | Loaded on-demand for specific tasks |

### Built-in Agents

#### Build Agent
- **Mode**: `primary`
- **Description**: Default agent with all tools enabled
- **Use Case**: Standard development work with full access
- **Tools**: All enabled by default

#### Plan Agent
- **Mode**: `primary`
- **Description**: Restricted agent for planning and analysis
- **Permissions**: All file edits and bash commands set to `ask`
- **Use Case**: Analyze code, suggest changes, create plans without modifications

#### General Subagent
- **Mode**: `subagent`
- **Description**: General-purpose for complex multi-step tasks
- **Tools**: Full access (except todo)
- **Use Case**: Running multiple units of work in parallel

#### Explore Subagent
- **Mode**: `subagent`
- **Description**: Fast, read-only agent for codebase exploration
- **Tools**: Read-only (no file modifications)
- **Use Case**: Find files, search code, answer questions about codebase

### Agent Configuration

#### JSON Configuration

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "build": {
      "mode": "primary",
      "model": "anthropic/claude-sonnet-4-20250514",
      "prompt": "{file:./prompts/build.txt}",
      "tools": {
        "write": true,
        "edit": true,
        "bash": true
      }
    },
    "plan": {
      "mode": "primary",
      "model": "anthropic/claude-haiku-4-20250514",
      "tools": {
        "write": false,
        "edit": false,
        "bash": false
      }
    },
    "agentwire": {
      "description": "Main orchestrator for AgentWire",
      "mode": "primary",
      "temperature": 0.3,
      "tools": {
        "write": true,
        "edit": true,
        "bash": true,
        "question": true
      }
    },
    "worker": {
      "description": "Worker pane (no voice, no questions)",
      "mode": "subagent",
      "tools": {
        "write": true,
        "edit": true,
        "bash": true,
        "question": false
      }
    }
  }
}
```

#### Markdown Configuration

```yaml
# ~/.config/opencode/agents/agentwire.md
---
description: Main orchestrator for AgentWire voice interface
mode: primary
model: anthropic/claude-sonnet-4-20250514
temperature: 0.3
tools:
  write: true
  edit: true
  bash: true
  question: true
---

You are the AgentWire orchestrator. Coordinate tasks and delegate to workers as needed.
```

### Agent Options

| Option | Type | Purpose |
|---------|------|---------|
| `description` | string | Required. What the agent does |
| `mode` | string | `primary`, `subagent`, or `all` |
| `temperature` | number | LLM randomness (0.0-1.0) |
| `maxSteps` | number | Max agentic iterations before summary |
| `prompt` | string/file | Custom system prompt |
| `model` | string | Override model (provider/model format) |
| `tools` | object | Enable/disable specific tools |
| `permissions` | object | Override permissions |
| `hidden` | boolean | Hide subagent from @ autocomplete |
| `task` | object | Control which subagents can be invoked |

### Task Permissions (Subagent Invocation)

Control which subagents an agent can invoke:

```json
{
  "agent": {
    "orchestrator": {
      "mode": "primary",
      "permission": {
        "task": {
          "*": "deny",
          "orchestrator-*": "allow",
          "code-reviewer": "ask"
        }
      }
    }
  }
}
```

**Users can always invoke any subagent directly via @ mention, even if task permissions deny it.**

### Session Management

- **Start new session**: `/new` or `ctrl+x n`
- **List sessions**: `/sessions` or `ctrl+x l`
- **Continue session**: `opencode --session <id>` or `opencode --continue`
- **Fork session**: `POST /session/:id/fork` (via API)
- **Child sessions**: Subagents can create child sessions
- **Navigation**: `<Leader>+Right` cycles through parent → child sessions

---

## 5. OpenCode Customization

### Rules (AGENTS.md)

OpenCode supports project-specific rules in `AGENTS.md`:

```markdown
# SST v3 Monorepo Project
This is an SST v3 monorepo with TypeScript.

## Project Structure
- `packages/` - Workspace packages
- `infra/` - Infrastructure definitions

## Code Standards
- Use TypeScript with strict mode
- Shared code goes in `packages/core/`
```

**Precedence**:
1. Project `AGENTS.md` (or `CLAUDE.md` as fallback)
2. Global `~/.config/opencode/AGENTS.md` (or `~/.claude/CLAUDE.md` as fallback)

**Remote Instructions**: Can load from URLs:

```json
{
  "instructions": [
    "CONTRIBUTING.md",
    "docs/guidelines.md",
    "https://raw.githubusercontent.com/my-org/shared-rules/main/style.md"
  ]
}
```

### Skills

Reusable behavior via `SKILL.md` files:

```
~/.config/opencode/skills/git-release/SKILL.md

---
name: git-release
description: Create consistent releases and changelogs
license: MIT
compatibility: opencode
---

## What I do
- Draft release notes from merged PRs
- Propose a version bump
- Provide copy-pasteable `gh release create` command
```

**Discovery**:
- `.opencode/skills/<name>/SKILL.md` (project)
- `~/.config/opencode/skills/<name>/SKILL.md` (global)
- `.claude/skills/<name>/SKILL.md` (Claude-compatible)

**Loading**: Agents see available skills and load them via `skill` tool.

### Custom Tools

Define tools the LLM can call:

```typescript
.opencode/tools/database.ts

import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Query the project database",
  args: {
    query: tool.schema.string().describe("SQL query to execute"),
  },
  async execute(args, context) {
    const { agent, sessionID, messageID } = context
    return `Executed query: ${args.query}`
  },
})
```

**Locations**:
- `.opencode/tools/` (project)
- `~/.config/opencode/tools/` (global)

**Context includes**: `agent`, `sessionID`, `messageID`, `directory`, `worktree`

### Commands

Custom slash commands for repetitive tasks:

```json
{
  "command": {
    "test": {
      "template": "Run the full test suite with coverage report.\nFocus on failing tests.",
      "description": "Run tests with coverage",
      "agent": "build",
      "model": "anthropic/claude-haiku-4-5"
    },
    "component": {
      "template": "Create a React component named $ARGUMENTS with TypeScript support.",
      "description": "Create a new component"
    }
  }
}
```

**Locations**:
- `.opencode/commands/` (markdown)
- `~/.config/opencode/commands/` (markdown)
- `opencode.json` (JSON config)

### Themes

Customize appearance:

```json
{
  "theme": "opencode"
}
```

Themes in `~/.config/opencode/themes/` or `.opencode/themes/`.

### Keybinds

Customize keyboard shortcuts:

```json
{
  "keybinds": {
    "switch_agent": ["ctrl+o"],
    "submit_prompt": ["ctrl+enter"]
  }
}
```

### Formatters

Configure code formatters:

```json
{
  "formatter": {
    "prettier": {
      "disabled": true
    },
    "custom-prettier": {
      "command": ["npx", "prettier", "--write", "$FILE"],
      "environment": {
        "NODE_ENV": "development"
      },
      "extensions": [".js", ".ts", ".jsx", ".tsx"]
    }
  }
}
```

### LSP Servers

Configure language servers:

```json
{
  "lsp": {
    "typescript": {
      "command": ["typescript-language-server", "--stdio"],
      "languageId": "typescript"
    }
  }
}
```

### MCP Servers

Integrate external tools:

```json
{
  "mcp": {
    "jira": {
      "type": "remote",
      "url": "https://jira.example.com/mcp",
      "enabled": true
    },
    "local-tools": {
      "type": "local",
      "command": ["node", "/path/to/server.js"]
    }
  }
}
```

**Management**: `opencode mcp add`, `opencode mcp list`, `opencode mcp auth`

---

## 6. Feature Comparison Matrix

| Feature | Claude Code | OpenCode | Notes |
|---------|-------------|-----------|-------|
| **CLI Interface** | ✅ | ✅ | OpenCode has richer CLI with `run`, `serve`, `web`, etc. |
| **Permission Bypass Flag** | `--dangerously-skip-permissions` | ❌ | No direct equivalent |
| **Tool Control** | `--tools`, `--disallowedTools` | Via config/permissions | OpenCode uses `permission` config instead |
| **System Prompt Appending** | `--append-system-prompt` | Via `instructions` config | OpenCode uses `instructions` array |
| **Sessions** | ✅ | ✅ | OpenCode has richer session management (fork, children) |
| **Agent Types** | Single agent | Primary + Subagent | OpenCode has more sophisticated agent system |
| **Hooks System** | Permission hooks only | Plugin system with 30+ events | OpenCode's hooks are more comprehensive |
| **Permissions** | Ask/deny | Ask/allow/deny | OpenCode has three states vs Claude's two |
| **Granular Permissions** | Basic | Advanced (patterns, globs) | OpenCode supports pattern-based permissions |
| **Custom Roles** | ✅ (via prompt) | ✅ (via agents) | OpenCode has explicit agent configuration |
| **Rules/Instructions** | `CLAUDE.md` | `AGENTS.md` (supports `CLAUDE.md` as fallback) | OpenCode compatible with Claude Code format |
| **Skills** | ✅ | ✅ | Compatible formats |
| **HTTP API** | ❌ | ✅ | OpenCode has full OpenAPI server |
| **Multiple Sessions** | ❌ | ✅ | OpenCode supports parallel sessions |
| **TUI** | ❌ | ✅ | OpenCode has rich terminal UI |
| **IDE Extensions** | VS Code only | VS Code, multiple planned | OpenCode supports multiple platforms |
| **Desktop App** | ❌ | ✅ (beta) | macOS, Windows, Linux |
| **Web Interface** | ❌ | ✅ | Via `opencode web` |
| **Mobile Access** | ❌ | Planned | Client/server architecture enables this |
| **MCP Support** | ✅ | ✅ | Both support Model Context Protocol |
| **LSP Support** | ✅ | ✅ | Automatic LSP loading in OpenCode |
| **Custom Tools** | ❌ | ✅ | TypeScript/JavaScript tools |
| **Plugins** | ❌ | ✅ | Event-based plugin system |
| **Provider Agnostic** | ❌ (Anthropic only) | ✅ | 75+ LLM providers supported |
| **Open Source** | ❌ | ✅ | MIT licensed, 79k GitHub stars |

---

## 7. Missing Features Analysis

### Missing Direct Equivalent: `--dangerously-skip-permissions`

**Problem**: Claude Code has `--dangerously-skip-permissions` flag that bypasses all permission checks. OpenCode has no direct equivalent.

**Impact on AgentWire**: AgentWire uses this flag to allow full control for orchestrator sessions while restricting workers.

### Alternatives & Solutions

#### Solution 1: Permissive Permission Config (Recommended)

Create a config that allows all operations:

**Global config** (`~/.config/opencode/opencode.json`):
```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": "allow"
}
```

**Or specific permissions**:
```json
{
  "permission": {
    "*": "allow",
    "read": {
      "*.env": "deny",
      "*.env.*": "deny",
      "*.env.example": "allow"
    }
  }
}
```

**Environment variable approach** (for AgentWire):
```bash
export OPENCODE_PERMISSION='{"*":"allow"}'
opencode run "message"
```

#### Solution 2: Per-Agent Permission Control

Allow specific agents full access while restricting others:

```json
{
  "permission": {
    "*": "ask"
  },
  "agent": {
    "agentwire": {
      "permission": {
        "*": "allow"
      }
    },
    "worker": {
      "permission": {
        "bash": {
          "git push*": "deny",
          "rm -rf*": "deny"
        },
        "question": "deny"
      }
    }
  }
}
```

#### Solution 3: Plugin Hook (Advanced)

Create a plugin that modifies permission behavior:

```javascript
.opencode/plugins/auto-approve.js

export const AutoApprovePlugin = async ({ project, client, $, directory, worktree }) => {
  // Auto-approve specific tools for orchestrator agent
  return {
    "permission.updated": async (input, output) => {
      const agent = context.agent
      if (agent === "agentwire" && output.permissionID === "bash") {
        // Auto-approve bash commands for agentwire
        return { response: "always", remember: true }
      }
    }
  }
}
```

**Difficulty**: Medium - Requires understanding plugin hooks and context.

#### Solution 4: Server API + Custom Frontend

Use OpenCode's HTTP server with custom AgentWire frontend that handles permission decisions:

```bash
# Start OpenCode server
opencode serve --port 8765

# AgentWire portal sends requests to server
# AgentWire handles permission UI/logic
```

**Difficulty**: Medium-High - Requires HTTP API integration.

### Feature Gap Summary

| Claude Code Feature | OpenCode Status | Implementation Difficulty | Recommended Solution |
|-------------------|-----------------|--------------------------|----------------------|
| `--dangerously-skip-permissions` | ❌ Missing | Easy | Use `OPENCODE_PERMISSION='{"*":"allow"}'` env var |
| `--tools` flag | ❌ CLI flag missing | Easy | Use agent config or permission config |
| `--disallowedTools` flag | ❌ CLI flag missing | Easy | Use permission config with deny rules |
| `--append-system-prompt` | ❌ CLI flag missing | Easy | Use `instructions` config array |
| Permission hooks | ⚠️ Limited | Medium | Use plugin system with `permission.updated` hook |
| Session sharing via CLI | ✅ Better | N/A | OpenCode has `/share` command |

### Implementation Recommendations for AgentWire

#### 1. Replace `--dangerously-skip-permissions` with Permission Config

**Current AgentWire** (from CLAUDE.md):
```yaml
agent:
  command: "claude --dangerously-skip-permissions"
```

**Recommended OpenCode Integration**:
```yaml
# ~/.config/opencode/agents/agentwire.md
---
description: Main orchestrator for AgentWire
mode: primary
permission:
  "*": "allow"
tools:
  question: true
---

You are the AgentWire orchestrator...
```

Or via environment variable in AgentWire:
```python
# AgentWire CLI would set this before spawning opencode
os.environ['OPENCODE_PERMISSION'] = '{"*":"allow"}'
subprocess.run(["opencode", "run", message])
```

#### 2. Implement Worker Role Restrictions

**For worker panes** (no voice, no questions):

```yaml
# ~/.config/opencode/agents/worker.md
---
description: Worker pane (no voice, no AskUserQuestion)
mode: subagent
permission:
  question: deny
  bash:
    "*": "allow"
    "git push*": "deny"
    "rm -rf*": "deny"
tools:
  write: true
  edit: true
  bash: true
  question: false
---

Worker agent with voice and questions disabled. Execute tasks delegated by orchestrator.
```

#### 3. Use OpenCode's Agent System

Instead of passing flags, configure agents:

```bash
# Start agentwire orchestrator
opencode --agent agentwire "Coordinate tasks"

# Start worker pane
opencode --agent worker "Execute this task"
```

#### 4. Leverage OpenCode Server API

Use `opencode serve` + HTTP API for AgentWire portal:

```python
import requests

# Start OpenCode server (once)
subprocess.Popen(["opencode", "serve", "--port", "8765"])

# Send messages from AgentWire portal
response = requests.post(
    "http://localhost:8765/session/{session_id}/message",
    json={
        "agent": "agentwire",
        "parts": [{"type": "text", "text": prompt}]
    }
)
```

**Benefits**:
- Single OpenCode instance handles all sessions
- AgentWire portal just sends HTTP requests
- Session management handled by OpenCode
- No need to spawn multiple opencode processes

### Migration Path from Claude Code to OpenCode

#### Step 1: Config Migration
1. Copy `~/.claude/CLAUDE.md` to `~/.config/opencode/AGENTS.md`
2. Copy `~/.claude/skills/` to `~/.config/opencode/skills/`
3. Create agent config in `~/.config/opencode/agents/`

#### Step 2: CLI Command Replacement

| Claude Code | OpenCode | Notes |
|------------|-----------|-------|
| `claude` | `opencode` | Start TUI |
| `claude --dangerously-skip-permissions` | `OPENCODE_PERMISSION='{"*":"allow"}' opencode` | Env var approach |
| `claude --append-system-prompt "extra"` | `instructions: ["extra.md"]` | Config file |
| `claude --disallowedTools webfetch` | `permission: {"webfetch": "deny"}` | Config file |

#### Step 3: AgentWire Integration

**Current** (AgentWire with Claude Code):
```bash
agentwire new -s name
# spawns: claude --dangerously-skip-permissions
```

**Proposed** (AgentWire with OpenCode):
```bash
# Pre-config: Set up agentwire and worker agents

# Then:
agentwire new -s name
# spawns: opencode --agent agentwire
```

**AgentWire CLI Changes**:
1. Remove `--dangerously-skip-permissions` from command template
2. Add `--agent` flag support (default to `agentwire`)
3. Optionally set `OPENCODE_PERMISSION` env var for orchestrator
4. Use `opencode serve` + HTTP API instead of spawning processes

### Complexity Assessment

| Task | Difficulty | Time Estimate |
|------|-------------|----------------|
| Replace `--dangerously-skip-permissions` with env var | Easy | 1-2 hours |
| Create agentwire/worker agent configs | Easy | 1-2 hours |
| Migrate CLAUDE.md/skills to OpenCode format | Easy | 30 min |
| Use OpenCode Server API instead of CLI spawning | Medium | 4-6 hours |
| Integrate permission hooks via plugins | Medium | 3-4 hours |
| Full migration from Claude Code to OpenCode | Medium | 1-2 days |

**Total Migration Time**: 2-3 days (including testing)

---

## Conclusion

OpenCode is a feature-rich alternative to Claude Code with:

### ✅ Advantages
- **Open source** with active development (79k stars, 601 contributors)
- **Provider agnostic** (75+ LLM providers vs Claude-only)
- **Richer permission system** (allow/ask/deny with patterns)
- **Plugin system** with 30+ event hooks
- **HTTP API** for programmatic access
- **Agent system** with primary/subagent types
- **Multiple sessions** and parallel execution
- **TUI, web, desktop, mobile** support
- **Claude Code compatibility** (AGENTS.md, CLAUDE.md fallback, skills)

### ⚠️ Considerations
- **No `--dangerously-skip-permissions` flag** - Use `OPENCODE_PERMISSION='{"*":"allow"}'` env var instead
- **Learning curve** - More complex than Claude Code's simplicity
- **Younger project** - Claude Code has been around longer

### 📋 Recommendation

**AgentWire should integrate with OpenCode** because:

1. **Feature parity** - All critical features available (permissions, agents, skills)
2. **Better architecture** - Client/server enables multi-device access
3. **Provider flexibility** - Not locked to Anthropic
4. **Open source** - Can contribute fixes/features
5. **Claude Code compatible** - Smooth migration path

**Migration is straightforward**:
- Replace `--dangerously-skip-permissions` with permission config/env var
- Create `agentwire` and `worker` agent definitions
- Use HTTP API for portal integration
- Leverage plugin system for custom behavior

**Estimated effort**: 2-3 days to fully migrate from Claude Code to OpenCode in AgentWire.
