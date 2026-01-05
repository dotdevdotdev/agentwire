# Mission: Session Templates

> Pre-configured session setups with initial context, role, and instructions.

## Objective

Allow ICs to create and use session templates that pre-load Claude with project-specific context when a session starts. Reduces repetitive setup and ensures consistent starting points.

## Concept

A template defines:
- **Name**: Template identifier (e.g., "backend-api", "ml-training")
- **Initial prompt**: Context sent to Claude when session starts
- **Role**: Which role file to use (from `~/.agentwire/roles/`)
- **Voice**: TTS voice for the room
- **Project path**: Default project directory
- **Flags**: Additional Claude flags (model, etc.)

Templates stored in `~/.agentwire/templates/` as YAML or JSON files.

## Wave 1: Human Actions (BLOCKING)

- [ ] Decide on template file format (YAML vs JSON)
- [ ] Decide where templates live (global vs per-project)

## Wave 2: Core Implementation

### 2.1 Template data model
- Define Template dataclass in config.py
- Add templates loading to config system
- Support both global (~/.agentwire/templates/) and project (.agentwire/templates/) templates

### 2.2 Template CLI commands
- `agentwire template list` - list available templates
- `agentwire template show <name>` - show template details
- `agentwire template create <name>` - interactive template creation

### 2.3 Use template when creating session
- `agentwire new -s myproject --template backend-api`
- Sends initial prompt after Claude starts
- Sets room config (voice, role) from template

## Wave 3: Portal Integration

### 3.1 Template selector in Create Session form
- Dropdown to select template (or "None")
- Preview template contents
- Template overrides default values in form

### 3.2 Template management UI
- List templates on dashboard
- Create/edit/delete templates
- Duplicate existing template

## Wave 4: Initial Prompt Delivery

### 4.1 Implement initial prompt sending
- After session created, wait for Claude ready
- Send initial prompt from template
- Handle multi-line prompts correctly

### 4.2 Template variables
- Support variables like `{{project_name}}`, `{{branch}}`
- Expand variables when sending initial prompt

## Completion Criteria

- [x] Can create a template via CLI or portal
- [x] Can create session with template applied
- [x] Initial prompt sent automatically to new session
- [x] Templates visible in portal Create Session form
- [x] Variables expanded in initial prompt

## Example Template

```yaml
# ~/.agentwire/templates/backend-api.yaml
name: backend-api
description: Backend API development
role: worker
voice: bashbunni
project: ~/projects/api
initial_prompt: |
  You're working on the backend API service.

  Key directories:
  - src/api/ - API endpoints
  - src/services/ - Business logic
  - tests/ - pytest tests

  Run tests with: pytest
  Run server with: uvicorn src.main:app --reload

  Current focus: {{branch}} branch
```
