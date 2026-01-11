# Mission: Composable Roles System

> Refactor roles to follow Claude Code agent format with composable stacking.

## Summary

Replace the current orchestrator/worker system with composable roles that follow Claude Code's agent definition format. Roles can be stacked (`--roles worker,code-review`) with merged tool restrictions and concatenated system instructions.

## Wave 1: Human Actions (BLOCKING)

- [ ] Decide: Default role when no `--roles` specified (none? agentwire?)
- [ ] Decide: Keep `--worker` as shorthand for `--roles worker`?
- [ ] Decide: Deprecate `--orchestrator` flag or keep as `--roles agentwire`?

## Wave 2: Role File Format

**Task 2.1: Create role parser utility**
- New file: `agentwire/roles.py`
- Parse YAML frontmatter from markdown files
- Extract: name, description, tools, disallowedTools, model, color
- Return structured RoleConfig dataclass
- Handle missing/optional fields with sensible defaults

**Task 2.2: Convert agentwire role (was orchestrator)**
- Rename `~/.agentwire/roles/orchestrator.md` → `agentwire.md`
- Add YAML frontmatter:
  ```yaml
  ---
  name: agentwire
  description: Main voice interface session with full tool access
  model: inherit
  ---
  ```
- Keep existing system instructions as markdown body

**Task 2.3: Convert worker role**
- Update `~/.agentwire/roles/worker.md` with frontmatter:
  ```yaml
  ---
  name: worker
  description: Autonomous code execution, no user interaction
  disallowedTools: AskUserQuestion
  model: inherit
  ---
  ```
- Keep existing system instructions as markdown body

## Wave 3: CLI Integration

**Task 3.1: Add --roles flag to `agentwire new`**
- Files: `agentwire/__main__.py`
- Add `--roles` argument (comma-separated list)
- Parse role names, load from `~/.agentwire/roles/{name}.md`
- Validate roles exist before session creation

**Task 3.2: Update _build_claude_cmd() for composable roles**
- Files: `agentwire/__main__.py`
- Accept list of RoleConfig objects
- Merge tools: deduplicated union (all tools any role mentions)
- Merge disallowedTools: intersection (only block if ALL roles agree)
- Concatenate system instructions (joined with newlines)
- Use last specified model (or inherit)
- Build `--tools`, `--disallowedTools`, and `--append-system-prompt` flags

**Task 3.3: Migrate --worker and --orchestrator flags**
- `--worker` becomes shorthand for `--roles worker`
- `--orchestrator` becomes shorthand for `--roles agentwire` (or deprecate)
- Update argparse, keep backwards compat during transition

## Wave 4: Role Discovery & Validation

**Task 4.1: Add `agentwire roles` command**
- List available roles from `~/.agentwire/roles/`
- Show: name, description, disallowedTools, model
- Format as table

**Task 4.2: Add `agentwire roles show <name>` command**
- Display full role details including system instructions
- Validate role file format

## Wave 5: Documentation

**Task 5.1: Update roles-diagram.md**
- Reflect new composable system
- Show role format with frontmatter
- Update examples

**Task 5.2: Update CLI-REFERENCE.md**
- Document `--roles` flag
- Document `agentwire roles` command
- Add role file format reference

**Task 5.3: Create sample roles**
- `code-review.md` - Read-only code review
- `diligent-work.md` - Thorough, careful approach
- Place in `agentwire/roles/` as bundled examples

## Wave 6: Rename orchestrator → agentwire Throughout Codebase

**Task 6.1: Python code cleanup**
- Files: `agentwire/__main__.py`
  - `session_type="orchestrator"` → `session_type="agentwire"`
  - `is_orchestrator` → remove or rename
  - `--orchestrator` flag → deprecate, map to `--roles agentwire`
  - Help text updates
- Files: `agentwire/server.py`
  - `type: str = "orchestrator"` → `type: str = "agentwire"` (or no default)
  - `spawned_by` comment update
  - `cfg.get("type", "orchestrator")` → update default
- Files: `agentwire/onboarding.py`
  - `skip_orchestrator` → `skip_agentwire` or just `skip_session`
  - `orchestrator_role` variable names
  - Role file references
- Files: `agentwire/init_orchestrator.py`
  - Rename file to `init_agentwire.py`
  - Update function names and messages

**Task 6.2: Portal UI cleanup**
- Files: `agentwire/static/js/dashboard.js`
  - Session type badge: `orchestrator` → `agentwire`
- Files: `agentwire/static/css/dashboard.css`
  - `.session-badge.orchestrator` → `.session-badge.agentwire`
- Files: `agentwire/static/js/room.js`
  - Update any orchestrator references in comments

**Task 6.3: Skills cleanup**
- Files: `agentwire/skills/check-workers.md`
- Files: `agentwire/skills/sessions.md`
- Files: `agentwire/skills/new.md`
- Files: `agentwire/skills/status.md`
- Files: `agentwire/skills/kill.md`
- Files: `agentwire/skills/workers.md`
- Files: `agentwire/skills/init.md`
- Update all references from orchestrator → agentwire

**Task 6.4: Documentation cleanup**
- Files: `CLAUDE.md`, `README.md`
- Files: `docs/CLI-REFERENCE.md`, `docs/cli-diagram.md`, `docs/cli-review.md`
- Files: `docs/roles-diagram.md`, `docs/system-diagram.md`
- Files: `docs/docker-deployment.md`, `docs/deployment.md`, `docs/PORTAL.md`
- Files: `docs/installation-case-study.md`
- Update terminology: orchestrator → agentwire (for the main session role)
- Keep "orchestration" as a concept where it makes sense (portal orchestrates)

**Task 6.5: Config/examples cleanup**
- Files: `Dockerfile.portal`, `docker-compose.yml`
- Files: `examples/config-distributed.yaml`, `examples/machines-distributed.json`
- Update comments and descriptions

**Note:** Completed/cancelled mission docs in `docs/missions/completed/` and `docs/missions/cancelled/` are historical and should NOT be modified.

## Completion Criteria

- [ ] Role files use YAML frontmatter format
- [ ] `agentwire new -s foo --roles worker,code-review` works
- [ ] Multiple roles merge tools correctly (deduplicated union)
- [ ] Multiple roles merge disallowedTools correctly (intersection)
- [ ] Multiple roles concatenate system instructions
- [ ] `agentwire roles` lists available roles
- [ ] No references to "orchestrator" as session type (renamed to "agentwire")
- [ ] Portal UI shows "agentwire" badge instead of "orchestrator"
- [ ] Documentation updated
- [ ] Existing `--worker` flag still works (backwards compat)

## Technical Notes

**Role file location:** `~/.agentwire/roles/*.md`

**RoleConfig dataclass:**
```python
@dataclass
class RoleConfig:
    name: str
    description: str
    instructions: str  # markdown body
    tools: list[str] | None = None  # whitelist
    disallowed_tools: list[str] | None = None  # blacklist
    model: str | None = None  # sonnet, opus, haiku, inherit
    color: str | None = None  # UI hint
```

**Merge logic:**
```python
def merge_roles(roles: list[RoleConfig]) -> MergedRole:
    # Union of all tools (deduplicated) - every tool any role needs is available
    tools = set()
    for r in roles:
        if r.tools:
            tools.update(r.tools)

    # Intersection of disallowed tools - only block if ALL roles agree
    disallowed = None
    for r in roles:
        if r.disallowed_tools:
            if disallowed is None:
                disallowed = set(r.disallowed_tools)
            else:
                disallowed &= set(r.disallowed_tools)
    disallowed = disallowed or set()

    # Concatenate instructions
    instructions = "\n\n".join(r.instructions for r in roles)

    # Last non-None model wins
    model = next((r.model for r in reversed(roles) if r.model), None)

    return MergedRole(tools, disallowed, instructions, model)
```

**Example merge:**
```
Role A: tools=[Read, Grep], disallowedTools=[Bash, AskUserQuestion]
Role B: tools=[Write, Edit], disallowedTools=[AskUserQuestion]
Role C: tools=[Read], disallowedTools=[AskUserQuestion, Write]

Result:
  tools = [Read, Grep, Write, Edit]  # union of all
  disallowedTools = [AskUserQuestion]  # only one in ALL three
```

**Bundled vs user roles:**
- Bundled: `agentwire/roles/*.md` (installed with package)
- User: `~/.agentwire/roles/*.md` (user customizations)
- User roles override bundled roles with same name
