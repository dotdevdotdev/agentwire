# AgentWire → Claude Code Integration Analysis

**Comprehensive documentation of all Claude Code integration points and features that need equivalents in OpenCode.**

## 1. Claude Code Invocation Points

### 1.1 Core Claude Command Builder (`__main__.py:66-110`)

**Function:** `_build_claude_cmd(session_type, roles)`

**Returns:** Full Claude CLI command string or empty string for bare sessions

**Session Type Mapping:**

| Session Type | CLI Flags | Purpose |
|--------------|------------|---------|
| `bare` | (empty string) | No Claude, tmux only |
| `claude-bypass` | `--dangerously-skip-permissions` | Full automation, no permission prompts |
| `claude-prompted` | (no flags) | Uses permission hooks, interactive approvals |
| `claude-restricted` | `--tools Bash` | Only Bash tool (for say command) |

**Role Integration:**

When roles are provided, the command builder:

1. **Merges all roles** using `merge_roles()` function
   - Tools: Union of all role tools
   - Disallowed tools: Intersection (only block if ALL agree)
   - Instructions: Concatenated with newlines
   - Model: Last non-None model wins

2. **Adds CLI flags:**
   ```bash
   --tools tool1,tool2,tool3           # Tool whitelist
   --disallowedTools tool1,tool2         # Tool blacklist
   --append-system-prompt "instructions" # Role instructions
   --model sonnet/opus/haiku            # Model override
   ```

**Example Outputs:**
```bash
# Bare session
(empty string)

# claude-bypass with roles
claude --dangerously-skip-permissions --tools Bash,Edit,Write --append-system-prompt "Role instructions..."

# claude-prompted
claude

# claude-restricted
claude --tools Bash
```

### 1.2 Direct Claude Invocations

| Location | Command | Context |
|-----------|----------|----------|
| `__main__.py:3034` | `claude --dangerously-skip-permissions` | New sessions (default) |
| `__main__.py:3125` | `claude --dangerously-skip-permissions` | New sessions (restricted bypass) |
| `__main__.py:3238` | `claude --dangerously-skip-permissions` | Fork sessions |
| `__main__.py:3385` | `claude --dangerously-skip-permissions` | Fork sessions (restricted) |
| `__main__.py:3602-3622` | `claude --resume <id> --fork-session [flags]` | Resume from history |

### 1.3 Resume from History (`__main__.py:3566-3694`)

**Command:**
```bash
claude --resume <session-id> --fork-session \
  --dangerously-skip-permissions \
  --tools tool1,tool2 \
  --disallowedTools tool1 \
  --append-system-prompt "instructions" \
  --model sonnet
```

**Purpose:** Fork a previous conversation into a new session with copied context.

**Source Data:**
- Reads Claude session ID from `.agentwire.yml` (`claude_session_id` field)
- Forks conversation state into new worktree/branch

---

## 2. Session Types Mapping

### 2.1 SessionType Enum (`project_config.py:15-41`)

```python
class SessionType(str, Enum):
    BARE = "bare"
    CLAUDE_BYPASS = "claude-bypass"
    CLAUDE_PROMPTED = "claude-prompted"
    CLAUDE_RESTRICTED = "claude-restricted"
```

### 2.2 Session Type Matrix

| Session Type | CLI Flags | Tools Available | Permission Prompts | Use Case |
|--------------|------------|-----------------|-------------------|-----------|
| **bare** | (none) | N/A (no Claude) | N/A | Manual coding, terminal only |
| **claude-bypass** | `--dangerously-skip-permissions` | All Claude tools | No | Full automation, voice-controlled agents |
| **claude-prompted** | (none) | All Claude tools | Yes (via hook) | Semi-automated, user approval required |
| **claude-restricted** | `--tools Bash` | Bash only (say command) | Auto-deny non-say | Voice-only mode, read-only access |

### 2.3 Session Type Inheritance (`.agentwire.yml`)

```yaml
# In project directory
type: claude-bypass          # Default for new projects
roles: [agentwire]           # Optional: composable roles
voice: dotdev                # Optional: TTS voice
```

### 2.4 CLI Flags for Session Types

| Command | Flags | Session Type Created |
|---------|--------|---------------------|
| `agentwire new -s name` | (none) | `claude-bypass` (from config or default) |
| `agentwire new -s name --bare` | `--bare` | `bare` |
| `agentwire new -s name --prompted` | `--prompted` | `claude-prompted` |
| `agentwire new -s name --restricted` | `--restricted` | `claude-restricted` |
| `agentwire spawn` | (none) | `claude-bypass` with worker role |

---

## 3. Roles System Deep Dive

### 3.1 Role Configuration Format (`roles/__init__.py:8-18`)

```yaml
---
name: worker
description: Autonomous code execution, no user interaction
disallowedTools: AskUserQuestion
model: inherit
---

# Role instructions here...
```

**Fields:**
- `name` - Role identifier
- `description` - Human-readable description
- `instructions` - Markdown body (role instructions for Claude)
- `tools` - Tool whitelist (e.g., `["Bash", "Edit"]`)
- `disallowedTools` - Tool blacklist (e.g., `["AskUserQuestion"]`)
- `model` - Model override: `sonnet`, `opus`, `haiku`, or `inherit`
- `color` - UI hint (not used by Claude)

### 3.2 Role Discovery Order (`roles/__init__.py:172-208`)

1. **Project roles:** `.agentwire/roles/{name}.md` (project-specific overrides)
2. **User roles:** `~/.agentwire/roles/{name}.md` (user-defined)
3. **Bundled roles:** `agentwire/roles/{name}.md` (built-in)

### 3.3 Role Merging Logic (`roles/__init__.py:124-169`)

```python
def merge_roles(roles: list[RoleConfig]) -> MergedRole:
    # Tools: Union (every tool any role needs is available)
    tools = union(r.tools for r in roles)

    # Disallowed tools: Intersection (only block if ALL roles agree)
    disallowed = intersection(r.disallowed_tools for r in roles)

    # Instructions: Concatenated with newlines
    instructions = "\n\n".join(r.instructions for r in roles)

    # Model: Last non-None wins
    model = last(r.model for r in reversed(roles) if r.model)

    return MergedRole(tools, disallowed, instructions, model)
```

**Example:**
```python
role1 = RoleConfig(tools=["Bash", "Edit"], disallowed_tools=["AskUserQuestion"])
role2 = RoleConfig(tools=["Bash", "Write"], model="sonnet")

merged = merge_roles([role1, role2])
# Result:
#   tools = {"Bash", "Edit", "Write"}
#   disallowed_tools = {"AskUserQuestion"}
#   model = "sonnet"
#   instructions = role1.instructions + "\n\n" + role2.instructions
```

### 3.4 Built-in Roles

| Role | File | Tools | Disallowed | Model | Purpose |
|-------|-------|--------|------------|--------|---------|
| **agentwire** | `agentwire/roles/agentwire.md` | (none) | (none) | inherit | Main orchestrator, full tool access |
| **worker** | `agentwire/roles/worker.md` | (none) | AskUserQuestion | inherit | Autonomous execution, no user interaction |
| **chatbot** | `agentwire/roles/chatbot.md` | (none) | (none) | inherit | Conversational mode |
| **voice** | `agentwire/roles/voice.md` | (none) | (none) | inherit | Voice input handling |

### 3.5 Role CLI Integration

**Command:**
```bash
agentwire spawn --roles worker,custom-role
```

**Process:**
1. Load `worker` and `custom-role` from discovery order
2. Merge roles using union/intersection logic
3. Pass merged config to `_build_claude_cmd()`
4. Generate Claude CLI with `--tools`, `--disallowedTools`, `--append-system-prompt`, `--model`

---

## 4. Hooks Architecture

### 4.1 Permission Hooks (`hooks/agentwire-permission.sh`)

**Purpose:** Enable portal-based permission dialogs for `claude-prompted` sessions.

**Installation:** `agentwire hooks install`

**Registered In:** `~/.claude/settings.json` under `hooks.PermissionRequest`

**Hook Format:**
```json
{
  "matcher": ".*",
  "hooks": [
    {"type": "command", "command": "~/.claude/hooks/agentwire-permission.sh"}
  ]
}
```

**Hook Event Type:** `PermissionRequest` (Claude Code hook system)

**Session Detection:**
1. tmux session name (most reliable)
2. Inferred from directory path (`~/projects/{session}`)
3. `.agentwire.yml` lookup (fallback)

**Communication Flow:**

```
Claude Code → Permission Hook → Portal API → User Decision → Portal API → Permission Hook → Claude Code
```

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/permission/{session}` | POST | Hook posts permission request, waits for response |
| `/api/permission/{session}/respond` | POST | Portal posts user decision |

**Input (from Claude):**
```json
{
  "tool_name": "Bash",
  "tool_input": {"command": "rm -rf /"},
  "message": "Permission required"
}
```

**Output (to Claude):**
```json
{
  "decision": "allow" | "deny" | "allow_always",
  "message": "Optional denial message"
}
```

**Timeout:** 5 minutes (300 seconds)

### 4.2 Damage Control Hooks

**Purpose:** Pre-execution security checks to block dangerous operations.

**Installation:** `agentwire safety install`

**Location:** `~/.agentwire/hooks/damage-control/`

**Files:**
1. `bash-tool-damage-control.py` - Blocks dangerous Bash commands
2. `edit-tool-damage-control.py` - Blocks edits to protected files
3. `write-tool-damage-control.py` - Blocks writes to protected files
4. `audit_logger.py` - Logs all security decisions
5. `patterns.yaml` - Configuration for all hooks

**Hook Event Type:** `PreToolUse` (Claude Code hook system)

**Exit Codes:**
- `0` - Allow operation
- `2` - Block operation (stderr fed back to Claude)

**Ask Pattern Output:**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "Reason for confirmation"
  }
}
```

### 4.3 Bash Tool Damage Control

**File:** `hooks/damage-control/bash-tool-damage-control.py`

**Checks Commands Against:**

1. **bashToolPatterns** - Regex patterns from `patterns.yaml`
   - Destructive operations: `rm -rf /`, `chmod 777`, `git reset --hard`
   - Infrastructure destruction: `terraform destroy`, `aws ec2 terminate-instances`
   - Cloud platform ops: `gcloud projects delete`, `firebase projects:delete`

2. **zeroAccessPaths** - No access allowed (including reads)
   - Secrets: `.env`, `~/.ssh/`, `~/.aws/`, `*-credentials.json`
   - SSL keys: `*.pem`, `*.key`, `*.p12`
   - AgentWire state: `~/.agentwire/credentials/`

3. **readOnlyPaths** - Reads allowed, writes blocked
   - System dirs: `/etc/`, `/usr/`, `/root/`
   - Shell configs: `~/.bashrc`, `~/.zshrc`
   - Lock files: `*.lock`, `package-lock.json`
   - Build artifacts: `node_modules/`, `dist/`, `__pycache__/`

4. **noDeletePaths** - Deletes blocked, reads/writes allowed
   - AgentWire config: `~/.agentwire/`, `.agentwire/`
   - Git data: `.git/`, `.gitignore`
   - Documentation: `README.md`, `LICENSE`
   - Project dirs: `src/`, `lib/` (optional)

**Pattern Formats:**
- **Literal paths:** `~/.ssh/`, `/etc/` (prefix matching)
- **Glob patterns:** `*.pem`, `.env*`, `*-credentials.json` (glob matching)

**Glob Matching Rules:**
- Supports `*` (any chars), `?` (single char), `[...]` (char class)
- Case-insensitive for security
- Matches in file-path contexts only (not method calls like `module.method()`)

**Example Blocked Commands:**
```bash
# Destructive file ops
rm -rf /                           # blocked by bashToolPatterns
rm --force file.txt                   # blocked by bashToolPatterns

# Permission changes
chmod 777 /path                     # blocked by bashToolPatterns
chown root:root /path               # blocked by bashToolPatterns

# Git destructive
git reset --hard                     # blocked by bashToolPatterns
git push --force                     # blocked by bashToolPatterns
git push --force-with-lease           # NOT blocked (explicit exception)

# Cloud destruction
terraform destroy                    # blocked by bashToolPatterns
aws ec2 terminate-instances          # blocked by bashToolPatterns
gcloud projects delete               # blocked by bashToolPatterns

# Zero-access paths
cat ~/.ssh/id_rsa                   # blocked by zeroAccessPaths
ls /etc/passwd                     # blocked by readOnlyPaths
rm -rf ~/.agentwire                 # blocked by noDeletePaths

# Ask patterns (require confirmation)
git checkout -- .                    # ask=true in patterns.yaml
git stash drop                       # ask=true in patterns.yaml
```

### 4.4 Edit/Write Tool Damage Control

**Files:**
- `edit-tool-damage-control.py` - Checks Edit tool
- `write-tool-damage-control.py` - Checks Write tool

**Checks File Paths Against:**

1. **zeroAccessPaths** - No access (read or write)
2. **readOnlyPaths** - Reads allowed, writes blocked

**Same Path Pattern Format as Bash hook:**
- Literal paths: `~/.ssh/`, `/etc/` (prefix matching)
- Glob patterns: `*.pem`, `.env*` (fnmatch)

### 4.5 Audit Logger (`hooks/damage-control/audit_logger.py`)

**Storage:** `~/.agentwire/logs/damage-control/YYYY-MM-DD.jsonl`

**Format (JSONL - one JSON per line):**
```json
{
  "timestamp": "2026-01-19T10:30:00",
  "session_id": "agentwire-dev",
  "agent_id": "main",
  "tool": "Bash",
  "command": "rm -rf /",
  "decision": "blocked",
  "blocked_by": "rm with recursive/force flags",
  "pattern_matched": "\\brm\\s+-[rRf]",
  "user_approved": null
}
```

**Decision Types:**
- `blocked` - Operation was blocked by damage control
- `asked` - Operation requires user confirmation
- `allowed` - Operation was allowed

**Session Context:**
- `AGENTWIRE_SESSION_ID` - Session identifier
- `AGENTWIRE_AGENT_ID` - Agent identifier (for parallel execution)

---

## 5. Permission Dialog Flow

### 5.1 Complete Flow Diagram

```
User Request
    ↓
Claude Code Prepares Tool Use
    ↓
[Session Type Check]
    ├─→ claude-bypass: Execute directly (no permission prompt)
    ├─→ claude-restricted: Auto-filter (only say allowed)
    └─→ claude-prompted: Permission check
           ↓
    Claude Calls Permission Hook
           ↓
    agentwire-permission.sh Receives Request
           ↓
    Hook POSTs to Portal: POST /api/permission/{session}
           ↓
    Portal Broadcasts to WebSocket Clients
           ↓
    [Browser Connected?]
        ├─→ Yes: Show permission dialog in UI
        └─→ No: Auto-deny (no user present)
               ↓
        User Clicks Allow/Deny
               ↓
        Portal POSTs: POST /api/permission/{session}/respond
               ↓
        Portal Returns Decision to Hook (blocks on async wait)
               ↓
        Hook Returns to Claude
               ↓
        [Decision Mapping]
            ├─→ allow: Send keystroke "1" to session
            ├─→ allow_always: Send keystroke "2" to session
            ├─→ deny: Send keystroke "Escape" to session
            └─→ custom: Send keystroke "3", message, "Enter"
                   ↓
            Claude Proceeds or Aborts
```

### 5.2 Portal Permission API

**Request Endpoint:** `POST /api/permission/{session}` (`server.py:2348-2453`)

**Flow:**
1. Parse request: `tool_name`, `tool_input`, `message`
2. Check session type
   - `claude-restricted`: Auto-handle without user interaction
     - **Auto-allow:** `Bash` with `say` command only
     - **Auto-deny:** Everything else (send "Escape" keystroke)
   - `claude-prompted`: Wait for user decision
3. Create `PendingPermission` object with `asyncio.Event`
4. Broadcast to WebSocket clients: `{"type": "permission_request", ...}`
5. Generate TTS announcement: `"Claude wants to edit filename.txt"`
6. Wait for user decision (5 minute timeout)
7. Return decision to hook

**Response Endpoint:** `POST /api/permission/{session}/respond` (`server.py:2456-2522`)

**Flow:**
1. Parse request: `decision` ("allow", "deny", "allow_always", "custom")
2. Store decision and signal waiting `asyncio.Event`
3. Send keystroke to session via `agentwire send-keys`:
   ```bash
   agentwire send-keys -s <session> <keystroke>
   ```
4. Keystroke mapping:
   - `allow` → "1"
   - `allow_always` → "2"
   - `deny` → "Escape"
   - `custom` → "3", message, "Enter"
5. Broadcast resolution: `{"type": "permission_resolved", ...}`

### 5.3 Restricted Mode Auto-Filter (`server.py:40-73`)

**Function:** `_is_allowed_in_restricted_mode(tool_name, tool_input)`

**Allowed Operations:**
1. `AskUserQuestion` tool (always allowed)
2. `Bash` tool with `say` command only

**Say Command Pattern:**
```regex
^(?:agentwire\s+)?say\s+(?:-[sv]\s+\S+\s+)*(["\']).*\1\s*&?\s*$
```

**Allows:**
```bash
say "hello world"
say 'hello world'
agentwire say "hello world"
agentwire say "hello world" &
agentwire say -s session "hello"
```

**Rejects:**
```bash
say "hi" && rm -rf /           # Shell operator
say "hi" > /tmp/log             # Redirect
say $(cat /etc/passwd)          # Command substitution
ls -la                         # Non-say command
```

**Multi-line Commands:** Always rejected (newline check)

### 5.4 TTS Permission Announcements (`server.py:2524-2545`)

**Function:** `_announce_permission_request(session_name, tool_name, tool_input)`

**Announcement Templates:**
- Edit: `"Claude wants to edit {filename}"`
- Write: `"Claude wants to write to {filename}"`
- Bash: `"Claude wants to run a command: {command}"`
- Other: `"Claude wants to use {tool_name}"`

**Integration:** Calls `_say_to_room()` which routes audio to browser or local speakers

---

## 6. Safety Features Inventory

### 6.1 Damage Control Pattern Categories

**From `hooks/damage-control/patterns.yaml` (721 lines)**

| Category | Pattern Count | Examples |
|----------|---------------|-----------|
| **Destructive File Ops** | 9 | `rm -rf /`, `trash`, `rmdir` |
| **Permission Changes** | 5 | `chmod 777`, `chown root`, `recursive chmod` |
| **Git Destructive** | 8 | `git reset --hard`, `git push --force`, `git stash clear` |
| **Git Require Confirmation** | 6 | `git checkout -- .`, `git stash drop`, `git branch -D` |
| **System-Level Destruction** | 4 | `mkfs.`, `dd of=/dev/`, `killall -9` |
| **History/Shell Manipulation** | 1 | `history -c` |
| **AgentWire Infrastructure** | 7 | `tmux kill-server`, `agentwire destroy`, `rm ~/.agentwire` |
| **Remote Execution** | 16 | SSH with `rm`, `mkfs`, `dd`, `reboot`, `shutdown` |
| **AWS CLI** | 9 | `aws s3 rm --recursive`, `aws ec2 terminate-instances` |
| **GCP (gcloud)** | 8 | `gcloud projects delete`, `gcloud compute instances delete` |
| **Firebase** | 5 | `firebase projects:delete`, `firebase firestore:delete --all-collections` |
| **Vercel** | 4 | `vercel remove --yes`, `vercel projects rm` |
| **Netlify** | 2 | `netlify sites:delete`, `netlify functions:delete` |
| **Cloudflare (wrangler)** | 5 | `wrangler delete`, `wrangler r2 bucket delete` |
| **Docker** | 5 | `docker system prune -a`, `docker rm -f $(docker ps)` |
| **Kubernetes (kubectl)** | 4 | `kubectl delete namespace`, `helm uninstall` |
| **Database CLI** | 5 | `redis-cli FLUSHALL`, `mongosh dropDatabase`, `dropdb` |
| **Infrastructure as Code** | 5 | `terraform destroy`, `pulumi destroy`, `serverless remove` |
| **Heroku** | 2 | `heroku apps:destroy`, `heroku pg:reset` |
| **GitHub CLI** | 1 | `gh repo delete` |
| **Package Registry** | 1 | `npm unpublish` |
| **SQL Destructive** | 5 | `DELETE FROM table;` (no WHERE), `DROP TABLE`, `TRUNCATE` |

### 6.2 Path Protection Levels

**Zero Access Paths (66 patterns)**
- Environment files: `.env`, `.env.*`, `*.env`
- SSH/GPG keys: `~/.ssh/`, `~/.gnupg/`
- Cloud credentials: `~/.aws/`, `~/.config/gcloud/`, `*-credentials.json`
- Kubernetes: `~/.kube/`, `kubeconfig`, `*-secret.yaml`
- Docker: `~/.docker/`
- SSL/TLS certs: `*.pem`, `*.key`, `*.p12`, `*.pfx`
- Terraform: `*.tfstate`, `.terraform/`
- Platform tokens: `.vercel/`, `.netlify/`, `firebase-adminsdk*.json`
- Package auth: `~/.netrc`, `~/.npmrc`, `~/.pypirc`
- AgentWire secrets: `~/.agentwire/credentials/`, `~/.agentwire/secrets/`

**Read-Only Paths (30+ patterns)**
- System dirs: `/etc/`, `/usr/`, `/root/`
- Shell configs: `~/.bashrc`, `~/.zshrc`, `~/.profile`
- Shell history: `~/.bash_history`, `~/.zsh_history`
- Lock files: `*.lock`, `package-lock.json`, `yarn.lock`, `poetry.lock`
- Build artifacts: `node_modules/`, `dist/`, `build/`, `__pycache__/`

**No-Delete Paths (20+ patterns)**
- AgentWire config: `~/.agentwire/`, `.agentwire/`
- Git data: `.git/`, `.gitignore`, `.gitattributes`
- License: `LICENSE`, `COPYING`, `NOTICE`
- Documentation: `README.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`
- CI/CD: `.github/`, `.gitlab-ci.yml`, `Jenkinsfile`
- Docker: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

### 6.3 Safety CLI Commands

| Command | Purpose | Implementation |
|---------|---------|----------------|
| `agentwire safety check <cmd>` | Dry-run check if command would be blocked | `cli_safety.py:142-213` |
| `agentwire safety status` | Show pattern counts and recent blocks | `cli_safety.py:216-254` |
| `agentwire safety logs` | Query audit logs with filters | `cli_safety.py:257-314` |
| `agentwire safety install` | Install damage control hooks | `cli_safety.py:449-517` |

### 6.4 Safety Status Output

```
AgentWire Safety Status
==================================================

✓ Hooks directory: True
✓ Patterns file: /Users/dotdev/.agentwire/hooks/damage-control/patterns.yaml
  Exists: True

Pattern Counts:
  • Bash Patterns: 100+
  • Zero Access Paths: 66
  • Read Only Paths: 30
  • No Delete Paths: 20

Audit Logs: /Users/dotdev/.agentwire/logs/damage-control
  Exists: True

Recent Blocks (last 5):
  [2026-01-19T10:30:00] rm -rf /
    → rm with recursive/force flags
  [2026-01-19T10:31:00] chmod 777 /path
    → chmod 777 (world writable)
```

---

## 7. Claude Code-Specific Features

### 7.1 Hooks System (Unique to Claude Code)

**PreToolUse Hook:**
- Intercept tool calls before execution
- Return JSON with `permissionDecision: "ask"` to trigger confirmation
- Exit code 2 to block operation
- Exit code 0 to allow operation

**PermissionRequest Hook:**
- Intercept permission prompts
- Route to external system (portal) for decision
- Wait for async response (with timeout)
- Return decision to Claude

**Hook Registration Format (`~/.claude/settings.json`):**
```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": ".*",
        "hooks": [
          {"type": "command", "command": "~/.claude/hooks/agentwire-permission.sh"}
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {"type": "command", "command": "~/.agentwire/hooks/damage-control/bash-tool-damage-control.py"}
        ]
      }
    ]
  }
}
```

### 7.2 CLI Flags (Claude Code Specific)

| Flag | Purpose | Session Types |
|------|---------|---------------|
| `--dangerously-skip-permissions` | Bypass permission prompts (full automation) | claude-bypass |
| `--tools tool1,tool2` | Whitelist specific tools | All types (except bare) |
| `--disallowedTools tool1,tool2` | Blacklist specific tools | All types (except bare) |
| `--append-system-prompt "text"` | Add role instructions | All types (except bare) |
| `--model sonnet/opus/haiku` | Override model | All types (except bare) |
| `--resume <session-id>` | Resume from conversation history | Fork sessions |
| `--fork-session` | Fork into new session | Fork sessions |

**No Equivalent Needed:**
- `--no-browser` - Not used by AgentWire

### 7.3 Tools (Claude Code Tool Set)

**Core Tools:**
- `Bash` - Execute shell commands
- `Edit` - Edit files with line-based diffs
- `Write` - Create/overwrite files
- `Read` - Read file contents
- `Glob` - Find files by pattern
- `Grep` - Search file contents
- `AskUserQuestion` - Interactive prompts to user

**Claude Code-Specific:**
- `Task` - Spawn sub-agents (for parallel execution)

**OpenCode Needs:**
- All of the above
- Equivalent hook system for PreToolUse/PermissionRequest

### 7.4 History Integration (`history.py`)

**Claude Data Directories:**
- `~/.claude/history.jsonl` - User message history with timestamps
- `~/.claude/projects/{encoded-path}/*.jsonl` - Session files with summaries

**Path Encoding:**
```python
# /home/user/projects/myapp → -home-user-projects-myapp
encode_project_path("/home/user/projects/myapp")  # Returns "-home-user-projects-myapp"
decode_project_path("-home-user-projects-myapp")   # Returns "/home/user/projects/myapp"
```

**History Commands:**
- `agentwire history list` - List recent sessions for project
- `agentwire history show <id>` - Show session details
- `agentwire history resume <id>` - Resume session (always forks)

**Session Data Structure:**
```json
{
  "sessionId": "uuid",
  "firstMessage": "Initial user message",
  "lastSummary": "Summary of last action",
  "timestamp": 1737270000,
  "messageCount": 15
}
```

**Remote History Support:**
- Reads history from remote machines via SSH
- Supports distributed AgentWire deployments

### 7.5 Session/Pane Architecture

**tmux Integration:**
- Sessions: `agentwire-dev`, `agentwire-dev/feature-branch`
- Panes: `:0.0` (orchestrator), `:0.1`, `:0.2` (workers)
- Format: `session_name:pane_index`

**Pane Commands:**
- `agentwire spawn` - Create worker pane
- `agentwire send --pane 1 "task"` - Send to pane 1
- `agentwire output --pane 1` - Read pane 1 output
- `agentwire kill --pane 1` - Kill pane 1
- `agentwire jump --pane 1` - Focus pane 1

**Session Format Variants:**
- Simple: `myproject` → `~/projects/myproject/`
- Worktree: `myproject/feature-branch` → `~/projects/myproject-worktrees/feature-branch/`
- Remote: `myproject@machine-id` → SSH to machine, use remote path

### 7.6 Remote Machine Support

**Machine Config (`~/.agentwire/machines.json`):**
```json
{
  "machines": [
    {
      "id": "gpu-server",
      "host": "192.168.1.100",
      "user": "deploy",
      "port": 22,
      "projects_dir": "~/projects",
      "worktrees_enabled": true
    }
  ]
}
```

**CLI Format:** `<session>@<machine-id>`

**Execution:**
- Run `agentwire` CLI commands via SSH
- Tunnel required for portal/TTS/STT access
- Local tmux manages sessions, remote executes work

### 7.7 AgentWire CLI as SSOT

**Principle:** CLI is authoritative, portal wraps CLI commands.

**Portal Commands → CLI Mapping:**
```
POST /api/session/new   → agentwire new -s name --json
POST /api/session/kill   → agentwire kill -s name --json
POST /api/pane/send     → agentwire send --pane N --json
```

**CLI Invocation Wrapper:**
```python
def run_agentwire_cmd(args):
    """Run agentwire command and parse JSON output."""
    result = subprocess.run(
        ["agentwire"] + args + ["--json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)
```

**Benefits:**
- Consistent behavior across all interfaces (CLI, portal, remote)
- Easy testing via CLI
- Portal is thin layer (no business logic duplication)

---

## 8. Summary: OpenCode Requirements

### 8.1 Essential Features (Must Have)

| Feature | Claude Code | OpenCode | Priority |
|---------|-------------|-----------|----------|
| **Hook System** | PreToolUse, PermissionRequest | TBD | Critical |
| **Session Types** | bypass, prompted, restricted, bare | TBD | Critical |
| **CLI Flags** | `--dangerously-skip-permissions`, `--tools`, etc. | TBD | Critical |
| **Permission Dialog** | Portal-based async approval | TBD | Critical |
| **Damage Control** | Pattern-based blocking | TBD | Critical |
| **Tool Whitelist/Blacklist** | `--tools`, `--disallowedTools` | TBD | Critical |

### 8.2 Architectural Differences

| Aspect | Claude Code | OpenCode |
|---------|-------------|-----------|
| **Hooks** | PreToolUse, PermissionRequest events | TBD |
| **Permission Prompts** | Built-in to CLI | TBD (need equivalent) |
| **History Format** | `~/.claude/history.jsonl` | TBD |
| **Session IDs** | UUID-based | TBD |
| **Tool Registry** | Built-in (Bash, Edit, Write, etc.) | TBD |
| **Sub-agent spawning** | `Task` tool | TBD |

### 8.3 Migration Strategy

**Phase 1: Essential Hooks**
- Implement PreToolUse equivalent (before tool execution)
- Implement PermissionRequest equivalent (async approval)
- Support same exit codes and JSON output format

**Phase 2: Session Types**
- Map Claude's session types to OpenCode equivalents
- Implement `--dangerously-skip-permissions` equivalent
- Implement `--tools`/`--disallowedTools` whitelisting

**Phase 3: Safety**
- Port damage-control patterns to OpenCode format
- Implement audit logging
- Create equivalent safety CLI commands

**Phase 4: History**
- Implement conversation history storage
- Support session resume/fork
- Migrate existing Claude history (optional)

---

## 9. File Reference

| File | Purpose | Lines |
|------|---------|--------|
| `agentwire/__main__.py` | CLI entry point, Claude invocation | 6062 |
| `agentwire/project_config.py` | Session types, .agentwire.yml parsing | 172 |
| `agentwire/roles/__init__.py` | Role loading, merging, discovery | 239 |
| `agentwire/server.py` | Portal API, permission dialogs | ~3000 |
| `agentwire/hooks/agentwire-permission.sh` | Permission hook (shell) | 116 |
| `agentwire/hooks/damage-control/bash-tool-damage-control.py` | Bash tool safety | 332 |
| `agentwire/hooks/damage-control/edit-tool-damage-control.py` | Edit tool safety | 144 |
| `agentwire/hooks/damage-control/write-tool-damage-control.py` | Write tool safety | 144 |
| `agentwire/hooks/damage-control/audit_logger.py` | Security audit logging | 235 |
| `agentwire/hooks/damage-control/patterns.yaml` | Safety pattern config | 721 |
| `agentwire/cli_safety.py` | Safety CLI commands | 518 |
| `agentwire/history.py` | Claude history integration | 379 |
| `agentwire/config.py` | Global config parsing | ~300 |

---

## 10. Key Code Locations

| Feature | File:Lines | Description |
|---------|-------------|-------------|
| **Claude command builder** | `__main__.py:66-110` | `_build_claude_cmd()` function |
| **Session type enum** | `project_config.py:15-41` | `SessionType` enum + CLI flags |
| **Role merging** | `roles/__init__.py:124-169` | `merge_roles()` function |
| **Permission API** | `server.py:2348-2522` | Permission request/response endpoints |
| **Restricted mode filter** | `server.py:40-73` | `_is_allowed_in_restricted_mode()` |
| **Bash damage control** | `bash-tool-damage-control.py:199-271` | `check_command()` function |
| **Pattern loading** | `cli_safety.py:125-139` | `load_patterns()` function |
| **History reading** | `history.py:175-256` | `get_history()` function |
| **Hook registration** | `__main__.py:4867-4925` | `register_hook_in_settings()` |
| **Resume/fork** | `__main__.py:3566-3694` | `cmd_fork()` function |

---

**End of Report**
