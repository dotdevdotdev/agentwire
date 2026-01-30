# Idea: Session Templates

> Pre-configured session setups for common workflows

## Problem

Starting a new session for a specific workflow is manual and repetitive:

```bash
# Want to debug an issue
agentwire new -s myproject -p ~/projects/myproject --type claude-bypass --roles debugger,leader

# Want to do a code review
agentwire new -s myproject -p ~/projects/myproject --type claude-bypass --roles reviewer

# Want to plan a feature
agentwire new -s myproject -p ~/projects/myproject --type claude-bypass --roles architect,leader
```

Every time you start a new task type, you remember (or forget) the right combination of type, roles, and initial setup.

## Why This Matters

1. **Cognitive overhead** - Users must remember role names, type options, common patterns
2. **Inconsistency** - Different users/sessions configured slightly differently
3. **Onboarding friction** - New users don't know what roles to use for what
4. **Repeated setup** - Same commands typed over and over

Templates package best practices into reusable, shareable configurations.

## Proposed Solution: Session Templates

### 1. Template Definition

Templates are YAML files in `~/.agentwire/templates/` or bundled:

```yaml
# ~/.agentwire/templates/debug.yaml
name: debug
description: Debug issues with systematic root cause analysis
type: claude-bypass
roles:
  - debugger
  - leader
voice: may
pre_commands:
  - "git status"
  - "git log --oneline -5"
initial_prompt: |
  You're starting a debugging session. 
  First, understand the current state of the codebase.
  Ask what issue needs to be debugged.
```

### 2. Using Templates

```bash
# Use a template
agentwire new -s myproject --template debug

# Override template settings
agentwire new -s myproject --template debug --roles debugger,custom-role

# List available templates
agentwire templates list

# Show template details
agentwire templates show debug
```

### 3. Bundled Templates

Ship with sensible defaults:

| Template | Description | Roles |
|----------|-------------|-------|
| `debug` | Root cause analysis, systematic debugging | debugger, leader |
| `review` | Code review with focus on quality | reviewer |
| `feature` | Plan and implement new features | architect, leader |
| `refactor` | Improve code structure without changing behavior | refactor-specialist |
| `explore` | Understand unfamiliar codebase | explorer |
| `test` | Write and improve tests | tester |
| `docs` | Write documentation | technical-writer |

### 4. Project-Level Templates

Projects can define templates in `.agentwire.yml`:

```yaml
type: claude-bypass
roles:
  - leader

templates:
  api-work:
    description: Work on API endpoints
    roles:
      - leader
      - api-specialist
    pre_commands:
      - "npm run dev &"
    initial_prompt: "API dev server starting. What endpoint are we working on?"
  
  frontend:
    description: Frontend component work
    roles:
      - leader
      - ui-specialist
    pre_commands:
      - "npm run storybook &"
```

```bash
# Use project template
agentwire new -s myproject --template api-work
```

Project templates override bundled templates of the same name.

## Template Schema

```yaml
name: string              # Template identifier
description: string       # Human-readable description
type: string              # Session type (claude-bypass, opencode-bypass, etc.)
roles: list[string]       # Roles to apply
voice: string             # TTS voice (optional)
parent: string            # Parent session for hierarchy (optional)
pre_commands: list[string] # Shell commands to run before agent starts
initial_prompt: string    # First message sent to agent (optional)
env: dict                 # Environment variables to set
workers:                  # Auto-spawn workers on session start
  - roles: [worker]
    count: 2
```

## CLI Commands

```bash
# List all templates (bundled + user + project)
agentwire templates list

# Show template details
agentwire templates show <name>

# Create from template
agentwire new -s <session> --template <name>

# Create new user template interactively
agentwire templates create

# Edit existing template
agentwire templates edit <name>

# Delete user template
agentwire templates delete <name>

# Export project templates to user templates
agentwire templates export <name>
```

## MCP Tools

```python
@mcp.tool()
def templates_list() -> str:
    """List available session templates.
    
    Returns bundled, user, and project templates with descriptions.
    """

@mcp.tool()
def template_show(name: str) -> str:
    """Show details of a session template.
    
    Returns full template configuration including roles, type, commands.
    """

@mcp.tool()
def session_create_from_template(
    name: str, 
    template: str,
    project_dir: str | None = None
) -> str:
    """Create a new session from a template.
    
    Applies template's type, roles, pre_commands, and initial_prompt.
    """
```

## Template Resolution Order

1. **Project templates** (`.agentwire.yml` in project directory)
2. **User templates** (`~/.agentwire/templates/*.yaml`)
3. **Bundled templates** (shipped with agentwire)

Project templates shadow user templates, which shadow bundled.

## Example Bundled Templates

### debug.yaml
```yaml
name: debug
description: Systematic debugging and root cause analysis
type: claude-bypass
roles:
  - leader
voice: may
initial_prompt: |
  You're in debugging mode. Approach problems systematically:
  1. Understand the symptom
  2. Form hypotheses
  3. Test each hypothesis
  4. Find root cause
  5. Implement fix
  6. Verify fix
  
  What issue are we debugging?
```

### review.yaml
```yaml
name: review
description: Code review with quality focus
type: claude-bypass
roles:
  - leader
initial_prompt: |
  You're reviewing code. Check for:
  - Correctness
  - Edge cases
  - Performance implications
  - Security concerns
  - Readability and maintainability
  
  What code should I review? (PR link, file path, or paste code)
```

### explore.yaml
```yaml
name: explore
description: Understand an unfamiliar codebase
type: claude-bypass
roles:
  - leader
initial_prompt: |
  You're exploring this codebase. Start by:
  1. Read README and docs
  2. Identify entry points
  3. Map key modules
  4. Understand data flow
  
  What aspect of the codebase should I explore first?
```

## Implementation Notes

### Template Storage

```
~/.agentwire/
├── templates/           # User templates
│   ├── my-custom.yaml
│   └── team-standard.yaml
└── config.yaml

agentwire/
├── templates/           # Bundled templates
│   ├── debug.yaml
│   ├── review.yaml
│   └── ...
```

### Loading Logic

```python
def load_template(name: str, project_dir: str | None) -> Template:
    # 1. Check project's .agentwire.yml
    if project_dir:
        project_config = load_agentwire_yml(project_dir)
        if name in project_config.get("templates", {}):
            return project_config["templates"][name]
    
    # 2. Check user templates
    user_template = Path.home() / ".agentwire/templates" / f"{name}.yaml"
    if user_template.exists():
        return yaml.safe_load(user_template.read_text())
    
    # 3. Check bundled
    bundled = Path(__file__).parent / "templates" / f"{name}.yaml"
    if bundled.exists():
        return yaml.safe_load(bundled.read_text())
    
    raise TemplateNotFound(name)
```

### Integration with `new` Command

```python
@cli.command()
@click.option("--template", "-t", help="Session template to use")
def new(session, template, ...):
    if template:
        tpl = load_template(template, project_dir)
        # Apply template defaults, allow overrides
        session_type = session_type or tpl.get("type")
        roles = roles or tpl.get("roles")
        voice = voice or tpl.get("voice")
        # etc.
    
    # Create session as normal
    create_session(...)
    
    # Run pre_commands
    for cmd in tpl.get("pre_commands", []):
        run_in_session(session, cmd)
    
    # Send initial_prompt
    if tpl.get("initial_prompt"):
        send_to_session(session, tpl["initial_prompt"])
```

## Success Criteria

1. `agentwire new -s x --template debug` creates a ready-to-use debugging session
2. Users can create custom templates without editing code
3. Projects can ship their own templates
4. Templates reduce session setup to one command
5. New users can discover templates with `templates list`

## Non-Goals

- **Template inheritance** - Keep it flat for simplicity
- **Template versioning** - Use git for that
- **Template sharing marketplace** - Users copy files manually or use git
- **Dynamic templates** - No scripting/conditionals, just static config

## Rollout

1. **Phase 1:** Bundled templates (debug, review, explore, feature)
2. **Phase 2:** User templates in `~/.agentwire/templates/`
3. **Phase 3:** Project templates in `.agentwire.yml`
4. **Phase 4:** MCP tools for template management
