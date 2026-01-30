# Idea: Worker Warmup Protocol

> Pre-load workers with context before sending tasks

## Problem

Workers waste turns orienting themselves in unfamiliar codebases:

```
Turn 1: "Let me read the README..."
Turn 2: "I'll check the project structure..."
Turn 3: "Looking at package.json for dependencies..."
Turn 4: "Now let me find the relevant files..."
Turn 5: *Finally starts actual work*
```

This burns tokens and time on every worker spawn, even for simple tasks.

## Why This Matters

1. **Token waste** - Orientation turns cost real money, repeated across every worker
2. **Latency** - 4-5 turns of exploration before work starts
3. **Inconsistency** - Different workers orient differently, miss things
4. **Orchestrator burden** - Must write verbose context in every task description

Workers should arrive "warm" - already understanding the codebase context.

## Proposed Solution: Warmup Bundles

### 1. Define Warmup Context

Per-project warmup in `.agentwire.yml`:

```yaml
warmup:
  # Files to pre-read (content injected into worker prompt)
  files:
    - README.md
    - CLAUDE.md
    - src/index.ts
  
  # Commands to run, output injected
  commands:
    - git status
    - git log --oneline -3
  
  # Static context string
  context: |
    This is a TypeScript/Express API. Key patterns:
    - Controllers in src/controllers/
    - Services in src/services/
    - Tests colocated with source files
    
    Common gotchas:
    - Always run `npm run typecheck` before committing
    - Auth middleware is in src/middleware/auth.ts
  
  # Max tokens for warmup (truncate if exceeded)
  max_tokens: 2000
```

### 2. Warmup on Spawn

When spawning a worker, warmup is automatic:

```bash
# Warmup applied from .agentwire.yml
agentwire spawn --roles glm-worker

# Override warmup
agentwire spawn --roles glm-worker --warmup minimal
agentwire spawn --roles glm-worker --no-warmup
```

### 3. Warmup Injection

Warmup content is prepended to the worker's first message:

```
<context>
## Project Context (auto-generated warmup)

### README.md
[truncated content]

### Git Status
On branch main
nothing to commit, working tree clean

### Project Notes
This is a TypeScript/Express API...
</context>

---

Your task: Add rate limiting to the /api/users endpoint...
```

### 4. Warmup Presets

Common warmup patterns as presets:

```yaml
warmup:
  preset: typescript-api  # Use bundled preset
  
  # Override specific parts
  files:
    - src/custom-important.ts
```

Bundled presets:
| Preset | Files | Commands | For |
|--------|-------|----------|-----|
| `minimal` | README.md | git status | Quick tasks |
| `standard` | README, package.json, tsconfig | git status, git log -3 | Most work |
| `typescript-api` | README, src/index.ts, routes | npm run typecheck | TS backends |
| `react-app` | README, src/App.tsx, components/index | npm run build --dry | React frontends |
| `python` | README, pyproject.toml, src/__init__.py | uv pip list | Python projects |

### 5. Dynamic Warmup

Orchestrators can specify per-task warmup:

```python
agentwire_pane_spawn(
    roles="glm-worker",
    warmup={
        "files": ["src/auth/login.ts", "src/auth/types.ts"],
        "context": "Focus on the login flow. Don't touch logout."
    }
)
```

Or via CLI:
```bash
agentwire spawn --roles glm-worker \
  --warmup-files "src/auth/*.ts" \
  --warmup-context "Focus on login flow"
```

## Implementation

### Warmup Bundle Generation

```python
def generate_warmup(project_dir: Path, config: dict) -> str:
    """Generate warmup content from config."""
    parts = []
    
    # Static context
    if config.get("context"):
        parts.append(f"## Project Notes\n{config['context']}")
    
    # File contents (truncated)
    for file_pattern in config.get("files", []):
        for file_path in glob(project_dir / file_pattern):
            content = truncate(file_path.read_text(), max_lines=50)
            parts.append(f"## {file_path.name}\n```\n{content}\n```")
    
    # Command outputs
    for cmd in config.get("commands", []):
        output = run_command(cmd, cwd=project_dir)
        parts.append(f"## $ {cmd}\n```\n{output}\n```")
    
    # Truncate total if needed
    warmup = "\n\n".join(parts)
    return truncate_tokens(warmup, config.get("max_tokens", 2000))
```

### Integration with `spawn`

```python
@cli.command()
@click.option("--no-warmup", is_flag=True)
@click.option("--warmup", help="Warmup preset or 'none'")
def spawn(roles, no_warmup, warmup, ...):
    # Load project config
    config = load_agentwire_yml(project_dir)
    
    # Generate warmup unless disabled
    warmup_content = None
    if not no_warmup and warmup != "none":
        warmup_config = resolve_warmup(config, warmup)
        warmup_content = generate_warmup(project_dir, warmup_config)
    
    # Spawn pane
    pane_id = spawn_pane(...)
    
    # Inject warmup as system context
    if warmup_content:
        inject_warmup(pane_id, warmup_content)
```

### Warmup Injection Methods

**Option A: Prefix first message**
```
[orchestrator sends task]
→ warmup + "\n---\n" + task
→ [worker receives combined message]
```

**Option B: Separate warmup message**
```
[spawn worker]
→ send warmup as "context only" message
→ send actual task
```

Option A is simpler and keeps context together with task.

## CLI Commands

```bash
# Spawn with default warmup
agentwire spawn --roles worker

# Spawn with specific preset
agentwire spawn --roles worker --warmup minimal

# Spawn with no warmup
agentwire spawn --roles worker --no-warmup

# Spawn with custom warmup files
agentwire spawn --roles worker --warmup-files "src/auth/*"

# Preview warmup content
agentwire warmup show
agentwire warmup show --preset typescript-api

# Generate warmup for debugging
agentwire warmup generate > warmup.md
```

## MCP Tools

```python
@mcp.tool()
def pane_spawn(
    roles: str | None = None,
    warmup: str | dict | None = None,  # preset name or config
    no_warmup: bool = False
) -> str:
    """Spawn worker pane with optional warmup context.
    
    Args:
        roles: Roles to apply
        warmup: Warmup preset name or custom config dict
        no_warmup: Skip warmup entirely
    """

@mcp.tool()
def warmup_show(preset: str | None = None) -> str:
    """Preview warmup content for current project.
    
    Shows what context would be injected into workers.
    """
```

## Warmup vs Task Context

| Aspect | Warmup | Task Context |
|--------|--------|--------------|
| Scope | Project-wide | Task-specific |
| Source | .agentwire.yml, presets | Orchestrator's message |
| Content | README, structure, patterns | Specific files, instructions |
| Persistence | Cached per project | Per-task |

They complement each other:
- **Warmup**: "Here's how this project works"
- **Task**: "Here's what I need you to do"

## Caching

Warmup content can be cached since it changes infrequently:

```
~/.agentwire/cache/warmup/{project_hash}.md
```

Invalidate on:
- `.agentwire.yml` change
- README.md change
- Manual `agentwire warmup refresh`

## Success Criteria

1. Workers start work 2-3 turns faster
2. Default warmup requires zero orchestrator effort
3. Orchestrators can customize warmup per-task
4. Token usage for orientation drops measurably
5. Workers make fewer "didn't know about X" mistakes

## Non-Goals

- **Full codebase indexing** - Just key files, not RAG
- **Semantic understanding** - Static content injection only
- **Cross-project learning** - Warmup is per-project

## Open Questions

- Should warmup be visible in worker output or hidden?
- How to handle very large projects (warmup token limits)?
- Should warmup include recent git commits by default?
