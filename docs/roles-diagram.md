# AgentWire Roles & Skills Diagram

## Session Type Architecture

```
                              User Request
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SESSION CREATION                                   │
│                                                                             │
│   agentwire new -s {name} [--orchestrator|--worker] [-t template]           │
│                                                                             │
│   1. Parse session type (orchestrator default, or --worker)                 │
│   2. Load template if specified                                             │
│   3. Build claude command with role injection                               │
│   4. Create tmux session with env vars                                      │
│   5. Update rooms.json with config                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│      ORCHESTRATOR SESSION       │  │        WORKER SESSION           │
│                                 │  │                                 │
│  Role: ~/.agentwire/roles/      │  │  Role: ~/.agentwire/roles/      │
│        orchestrator.md          │  │        worker.md                │
│                                 │  │                                 │
│  Env: AGENTWIRE_SESSION_TYPE=   │  │  Env: AGENTWIRE_SESSION_TYPE=   │
│       orchestrator              │  │       worker                    │
│                                 │  │                                 │
│  ┌───────────────────────────┐  │  │  ┌───────────────────────────┐  │
│  │     ALL TOOLS AVAILABLE   │  │  │  │     ALLOWED TOOLS         │  │
│  │                           │  │  │  │                           │  │
│  │  • Edit, Write, Read      │  │  │  │  • Edit, Write, Read      │  │
│  │  • Glob, Grep             │  │  │  │  • Glob, Grep             │  │
│  │  • Task (spawn agents)    │  │  │  │  • NotebookEdit           │  │
│  │  • Bash (inc. say cmd)    │  │  │  │  • Bash                    │  │
│  │  • AskUserQuestion        │  │  │  │  • MCP filesystem tools   │  │
│  │  • All MCP tools          │  │  │  │  • Task (spawn agents)    │  │
│  │  • AgentWire skills       │  │  │  └───────────────────────────┘  │
│  └───────────────────────────┘  │  │                                 │
│                                 │  │  ┌───────────────────────────┐  │
│  Role file provides guidance    │  │  │    BLOCKED TOOLS          │  │
│  on when to delegate vs do      │  │  │                           │  │
│  directly - not enforcement     │  │  │  • AskUserQuestion        │  │
│                                 │  │  └───────────────────────────┘  │
│  Purpose: Voice interface,      │  │                                 │
│  coordination, decisions,       │  │                                 │
│  direct work when appropriate   │  │  Purpose: Autonomous code       │
│                                 │  │  execution, no user interaction │
└─────────────────────────────────┘  └─────────────────────────────────┘
                    │                              │
                    │     /spawn, /send            │
                    └──────────────────────────────┘
```

## System Prompt Assembly

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SYSTEM PROMPT PIPELINE                                  │
│                                                                             │
│  ┌─────────────────────────────┐                                            │
│  │   Base Claude System        │  Claude Code's default instructions       │
│  │   Prompt                    │                                            │
│  └──────────────┬──────────────┘                                            │
│                 ▼                                                            │
│  ┌─────────────────────────────┐                                            │
│  │   ~/.claude/CLAUDE.md       │  User's global project instructions       │
│  │   + rules/*.md              │  (loaded via Claude Code discovery)       │
│  └──────────────┬──────────────┘                                            │
│                 ▼                                                            │
│  ┌─────────────────────────────┐                                            │
│  │   Project CLAUDE.md         │  Project-specific instructions            │
│  └──────────────┬──────────────┘                                            │
│                 ▼                                                            │
│  ┌─────────────────────────────┐                                            │
│  │   Role Instructions         │  --append-system-prompt flag              │
│  │   ~/.agentwire/roles/       │                                            │
│  │   {orchestrator|worker}.md  │  Injected via: $(cat ~/.agentwire/...)    │
│  └──────────────┬──────────────┘                                            │
│                 ▼                                                            │
│  ┌─────────────────────────────┐                                            │
│  │   Template Initial Prompt   │  Sent after session starts (if template)  │
│  │   (optional)                │                                            │
│  └─────────────────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Roles Directory Structure

```
~/.agentwire/
├── roles/
│   ├── agentwire.md        # Coordination, voice, full tool access
│   └── worker.md           # Autonomous execution, no user input
│
├── templates/
│   ├── voice-assistant.yaml
│   ├── feature-impl.yaml
│   ├── code-review.yaml
│   └── bug-fix.yaml
│
├── hooks/
│   ├── damage-control/             # Blocks dangerous commands
│   └── agentwire-permission.sh     # Routes permissions to portal
│
├── rooms.json              # Per-session config (voice, type, permissions)
└── config.yaml             # Global config (TTS, STT, machines)
```

## Role Definitions

### AgentWire (`~/.agentwire/roles/agentwire.md`)

| Aspect | Description |
|--------|-------------|
| Purpose | Voice interface, coordination, direct work when appropriate |
| File Access | FULL - uses judgment on when to delegate vs do directly |
| Voice | Can use `say` command |
| User Input | Can use `AskUserQuestion` |
| Key Skills | /spawn, /send, /output, /kill, /sessions |
| Blocked Tools | NONE - role file provides guidance, not enforcement |

### Worker (`~/.agentwire/roles/worker.md`)

| Aspect | Description |
|--------|-------------|
| Purpose | Execute code changes autonomously |
| File Access | FULL - Edit, Write, Read, Glob, Grep |
| Voice | BLOCKED via bash hook |
| User Input | BLOCKED - cannot use AskUserQuestion |
| Key Tools | All file tools, Task (can spawn sub-workers) |
| Blocked Tools | AskUserQuestion, say command |

## Skills Available to Orchestrators

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTWIRE SKILLS                                     │
│                       (agentwire/skills/*.md)                                │
│                                                                             │
│  Session Management                                                          │
│  ├── /new           Create new session                                      │
│  ├── /spawn         Smart create (handles existing sessions)                │
│  ├── /sessions      List all tmux sessions                                  │
│  ├── /kill          Terminate session                                       │
│  └── /jump          Get attach instructions                                 │
│                                                                             │
│  Communication                                                               │
│  ├── /send          Send prompt to session                                  │
│  └── /output        Read recent output from session                         │
│                                                                             │
│  Infrastructure                                                              │
│  └── /status        Check all machines and sessions                         │
│                                                                             │
│  Worker Management                                                           │
│  ├── /workers       List/manage worker sessions                             │
│  └── /spawn-worker  Create autonomous worker                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tool Blocking Implementation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOOL BLOCKING                                        │
│                                                                             │
│  Claude --disallowedTools Flag                                              │
│  ────────────────────────────                                               │
│                                                                             │
│  Orchestrator:                                                               │
│    (none) - all tools available, role file provides guidance                │
│                                                                             │
│  Worker:                                                                     │
│    --disallowedTools "AskUserQuestion"                                      │
│    (say command not blocked - workers just aren't told about it)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Template System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TEMPLATE FORMAT                                      │
│                   ~/.agentwire/templates/*.yaml                              │
│                                                                             │
│  name: feature-impl                    # Template identifier                │
│  description: Implement a feature      # Display name                       │
│  roles: [worker]                       # Array of composable roles          │
│  voice: bashbunni                      # TTS voice name                     │
│  project: ~/projects/myapp             # Default working directory          │
│  bypass_permissions: true              # Skip permission prompts            │
│  restricted: false                     # Block all execution                │
│  initial_prompt: |                     # Context sent after session starts  │
│    You are implementing feature X.                                          │
│    Focus on the API layer first.                                            │
│                                                                             │
│  Variable Expansion:                                                         │
│    {{project_name}}  → session/project name                                 │
│    {{branch}}        → current git branch                                   │
│    {{machine}}       → machine ID if remote                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Parallel Execution Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR → WORKER PATTERN                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Orchestrator Session                              │    │
│  │                    (agentwire main)                                  │    │
│  │                                                                      │    │
│  │   Role: orchestrator.md                                              │    │
│  │   Can: /spawn, /send, /output, /kill, say                           │    │
│  │   Cannot: Edit, Write, Read files                                   │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                              │
│           ┌───────────────────┼───────────────────┐                         │
│           │                   │                   │                         │
│           ▼                   ▼                   ▼                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │  Worker: api   │  │  Worker: ui    │  │  Worker: tests │                 │
│  │                │  │                │  │                │                 │
│  │  Role: worker  │  │  Role: worker  │  │  Role: worker  │                 │
│  │  Can: Edit,    │  │  Can: Edit,    │  │  Can: Edit,    │                 │
│  │  Write, Read   │  │  Write, Read   │  │  Write, Read   │                 │
│  │  Cannot: say,  │  │  Cannot: say,  │  │  Cannot: say,  │                 │
│  │  AskUser       │  │  AskUser       │  │  AskUser       │                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
│                                                                             │
│  All workers run in parallel, report results to orchestrator                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Environment Variables

| Variable | Set By | Purpose |
|----------|--------|---------|
| `AGENTWIRE_ROOM` | Session creation | Room ID for portal routing |
| `AGENTWIRE_SESSION_TYPE` | Session creation | "orchestrator" or "worker" |
| `AGENTWIRE_PORTAL_URL` | Config | Portal URL for API calls |

## Hooks Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HOOKS PIPELINE                                     │
│                                                                             │
│  Command Execution                                                           │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────┐                                            │
│  │   damage-control.py         │  PreToolUse hook                           │
│  │                             │  Blocks: rm -rf /, git push --force, etc   │
│  │   Exit: 0=allow, 2=block    │                                            │
│  └──────────────┬──────────────┘                                            │
│                 ▼                                                            │
│  ┌─────────────────────────────┐                                            │
│  │   session-type-bash-hook.py │  Bash hook                                 │
│  │                             │  Blocks: say for workers                   │
│  │   Checks: SESSION_TYPE      │                                            │
│  └──────────────┬──────────────┘                                            │
│                 ▼                                                            │
│  ┌─────────────────────────────┐                                            │
│  │   agentwire-permission.sh   │  Permission hook                           │
│  │                             │  Routes to portal for user decision        │
│  │   POST /api/permission/     │                                            │
│  └──────────────┬──────────────┘                                            │
│                 ▼                                                            │
│            Execute Command                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Configuration Files Summary

| File | Format | Purpose |
|------|--------|---------|
| `~/.agentwire/config.yaml` | YAML | Global settings (TTS, STT, machines) |
| `~/.agentwire/rooms.json` | JSON | Per-session config (voice, type, permissions) |
| `~/.agentwire/roles/*.md` | Markdown | Role instructions appended to system prompt |
| `~/.agentwire/templates/*.yaml` | YAML | Session templates with initial context |
| `~/.agentwire/hooks/*.py` | Python | PreToolUse/Bash hooks for safety |
| `~/.agentwire/machines.json` | JSON | Remote machine SSH configurations |
