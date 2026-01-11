# Mission: Composable Roles System

> Refactor roles to follow Claude Code agent format with composable stacking.

## Summary

Replace the current orchestrator/worker system with composable roles that follow Claude Code's agent definition format. Roles can be stacked (`--roles worker,code-review`) with merged tool restrictions and concatenated system instructions.

## Wave 1: Decisions (COMPLETE)

- [x] Default role when no `--roles` specified: **No role (bare session)**
- [x] Legacy flags: **Remove both `--worker` and `--orchestrator`**, only use `--roles`
- [x] `agentwire dev` command: **Keep as-is**, maps to `agentwire new -s agentwire --roles agentwire`
- [x] Role locations: **Global + project** (`~/.agentwire/roles/` and `.agentwire/roles/`)
- [x] Role precedence: **Project overrides global** (same name = project wins completely)
- [x] rooms.json: **Store role names as array** (`roles: ['worker', 'code-review']`)
- [x] AGENTWIRE_SESSION_TYPE env var: **Remove it** (use AGENTWIRE_SESSION_ROLES if needed later)
- [x] Templates: **Use roles array** (`roles: [worker, code-review]` in YAML)
- [x] Bundled roles: **Yes, bundle agentwire.md and worker.md** (user can override)
- [x] Sample roles: **Just core two** (agentwire, worker)
- [x] chatbot.md role: **Remove it** (user creates custom restricted role if needed)
- [x] Portal badges: **Show all roles** as separate badges

## Wave 2: Role File Format

**Task 2.1: Create role parser utility**
- New file: `agentwire/roles.py`
- Parse YAML frontmatter from markdown files
- Extract: name, description, tools, disallowedTools, model, color
- Return structured RoleConfig dataclass
- Handle missing/optional fields with sensible defaults

**Task 2.2: Create bundled agentwire role**
- New file: `agentwire/roles/agentwire.md` (bundled with package)
- YAML frontmatter:
  ```yaml
  ---
  name: agentwire
  description: Main voice interface session with full tool access
  model: inherit
  ---
  ```
- System instructions for voice-first coordination

**Task 2.3: Create bundled worker role**
- New file: `agentwire/roles/worker.md` (bundled with package)
- YAML frontmatter:
  ```yaml
  ---
  name: worker
  description: Autonomous code execution, no user interaction
  disallowedTools: AskUserQuestion
  model: inherit
  ---
  ```
- System instructions for autonomous execution

**Task 2.4: Remove chatbot role**
- Delete `~/.agentwire/roles/chatbot.md` (user creates custom if needed)
- Remove any references to chatbot role in code

## Wave 3: CLI Integration

**Task 3.1: Add --roles flag to `agentwire new`**
- Files: `agentwire/__main__.py`
- Add `--roles` argument (comma-separated list)
- Role discovery order:
  1. Project: `.agentwire/roles/{name}.md`
  2. User: `~/.agentwire/roles/{name}.md`
  3. Bundled: `agentwire/roles/{name}.md`
- Project overrides global of same name
- Validate roles exist before session creation
- No `--roles` = bare session (no role instructions)

**Task 3.2: Update _build_claude_cmd() for composable roles**
- Files: `agentwire/__main__.py`
- Accept list of RoleConfig objects
- Merge tools: deduplicated union (all tools any role mentions)
- Merge disallowedTools: intersection (only block if ALL roles agree)
- Concatenate system instructions (joined with newlines)
- Use last specified model (or inherit)
- Build `--tools`, `--disallowedTools`, and `--append-system-prompt` flags

**Task 3.3: Remove --worker and --orchestrator flags**
- Files: `agentwire/__main__.py`
- Remove `--worker` flag entirely
- Remove `--orchestrator` flag entirely
- Only `--roles` flag for role specification
- Update help text and error messages

**Task 3.4: Update rooms.json structure**
- Files: `agentwire/server.py`, `agentwire/__main__.py`
- Change `type: "orchestrator" | "worker"` to `roles: ["worker", "code-review"]`
- Array of role names applied to session
- Empty array = bare session

**Task 3.5: Remove AGENTWIRE_SESSION_TYPE env var**
- Files: `agentwire/__main__.py`
- Stop setting AGENTWIRE_SESSION_TYPE
- Future: use AGENTWIRE_SESSION_ROLES if hooks need it

**Task 3.6: Update templates to use roles array**
- Files: `agentwire/__main__.py`, template handling code
- Change `role: orchestrator` to `roles: [agentwire]`
- Support array of role names in template YAML

## Wave 4: Role Discovery & Validation

**Task 4.1: Add `agentwire roles` command**
- List available roles from `~/.agentwire/roles/`
- Show: name, description, disallowedTools, model
- Format as table

**Task 4.2: Add `agentwire roles show <name>` command**
- Display full role details including system instructions
- Validate role file format

## Wave 5: Portal UI & Documentation

**Task 5.1: Update portal to show multiple role badges**
- Files: `agentwire/static/js/dashboard.js`
- Show badge for each role: `[worker] [code-review]`
- Update badge styling for role names
- Files: `agentwire/static/css/dashboard.css`
- Style for role badges (remove orchestrator-specific styles)

**Task 5.2: Update roles-diagram.md**
- Reflect new composable system
- Show role format with frontmatter
- Update examples with `--roles` flag

**Task 5.3: Update CLI-REFERENCE.md**
- Document `--roles` flag
- Remove `--worker` and `--orchestrator` flags
- Document `agentwire roles` command
- Add role file format reference

**Task 5.4: Update other documentation**
- `CLAUDE.md` - Update session types section
- `README.md` - Update examples
- `docs/cli-diagram.md` - Update command diagrams

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

## Wave 7: Config Architecture - .agentwire.yml as Source of Truth

**Task 7.1: Define .agentwire.yml schema**
- Full session config lives in project root
- Fields:
  ```yaml
  session: myapp               # tmux session name (required)
  type: claude-bypass          # session type (see Task 7.7)
  roles: [worker, code-review] # composable roles (optional, ignored if bare)
  voice: bashbunni             # TTS voice (optional)
  ```
- Parser in `agentwire/config.py` or new `agentwire/project_config.py`

**Task 7.2: Update session creation to write .agentwire.yml**
- Files: `agentwire/__main__.py`
- `agentwire new` creates/updates `.agentwire.yml` in project directory
- Remove `AGENTWIRE_ROOM` env var (not needed anymore)
- Session config comes from yaml, not env vars

**Task 7.3: Update commands to read .agentwire.yml**
- Files: `say` command, hooks, any command needing session context
- Read yaml from current working directory
- Get session name, roles, voice from yaml
- No env var fallback (yaml is required)

**Task 7.4: Rename rooms.json → sessions.json (runtime cache)**
- Files: `agentwire/server.py`, portal code
- No longer source of truth - just a cache for portal
- Rebuilt by scanning tmux sessions + reading their project yamls
- Portal refreshes cache on start and periodically

**Task 7.5: Add cache rebuild logic**
- Files: `agentwire/server.py`
- Scan all tmux sessions
- For each session, get working directory
- Read `.agentwire.yml` from that directory (if exists)
- Sessions without yaml: show with defaults (no roles, default permissions)
- Build sessions.json cache from aggregated data

**Task 7.6: Remove AGENTWIRE_ROOM env var**
- Files: `agentwire/__main__.py`, `agentwire/agents/tmux.py`
- Stop setting `AGENTWIRE_ROOM` at session creation
- Update any code that reads this env var

**Task 7.7: Consolidate to single `type` field**
- Files: `agentwire/__main__.py`
- Replace separate bool flags with single `type` field
- Session types: `bare` | `claude-bypass` | `claude-prompted` | `claude-restricted`
- CLI flags: `--bare`, `--prompted`, `--restricted` (default is `claude-bypass`)
- In `.agentwire.yml`: `type: claude-bypass` (single field)
- Remove old `bypass_permissions`, `restricted` bool fields
- Portal shows session type badge

## Completion Criteria

**Roles:**
- [x] Role files use YAML frontmatter format
- [x] `agentwire new -s foo --roles worker,code-review` works
- [x] Multiple roles merge tools correctly (deduplicated union)
- [x] Multiple roles merge disallowedTools correctly (intersection)
- [x] Multiple roles concatenate system instructions
- [x] `agentwire roles` lists available roles
- [x] Role discovery: project → user → bundled (project overrides)
- [x] `--worker` and `--orchestrator` flags removed
- [x] Templates use `roles: [...]` array
- [x] Portal shows all role badges for session
- [x] No references to "orchestrator" as session type (renamed to "agentwire")
- [x] agentwire.md and worker.md bundled with package
- [x] chatbot.md removed

**Config Architecture:**
- [x] `.agentwire.yml` is source of truth for session config
- [x] `agentwire new` creates `.agentwire.yml` in project root
- [ ] Commands read `.agentwire.yml` instead of env vars (say command - future)
- [x] `AGENTWIRE_ROOM` env var removed
- [x] `AGENTWIRE_SESSION_TYPE` env var removed
- [x] `rooms.json` renamed to `sessions.json` (runtime cache)
- [ ] Portal rebuilds cache from tmux sessions + yaml files (future enhancement)
- [x] Single `type` field replaces separate bool flags
- [x] Session types: bare | claude-bypass | claude-prompted | claude-restricted

**Documentation:**
- [x] Documentation updated

## Technical Notes

**Role discovery order (first match wins):**
1. Project: `.agentwire/roles/{name}.md`
2. User: `~/.agentwire/roles/{name}.md`
3. Bundled: `agentwire/roles/{name}.md` (package)

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

**.agentwire.yml (source of truth - lives in project root):**
```yaml
session: myapp                # tmux session name (required)
type: claude-bypass           # session type (see below)
roles: [worker, code-review]  # composable roles (optional, ignored if bare)
voice: bashbunni              # TTS voice (optional)
```

**Session types:**
| Type | CLI Flag | Description |
|------|----------|-------------|
| `bare` | `--bare` | No Claude, just tmux session |
| `claude-bypass` | (default) | Claude with `--dangerously-skip-permissions` |
| `claude-prompted` | `--prompted` | Claude with permission hook |
| `claude-restricted` | `--restricted` | Claude, only `say` allowed |

**Why `type` matters (architecture note):**
The `type` field is our escape hatch and extension point for session logic that lives outside/alongside Claude. Instead of scattering conditionals everywhere, all type-specific logic lives in clean `if type ==` blocks. This keeps code maintainable when adding future types like watchers, remote shells, bridges, etc.

**sessions.json (runtime cache - rebuilt from tmux + yaml files):**
```json
{
  "myapp": {
    "roles": ["worker", "code-review"],
    "voice": "bashbunni",
    "bypass_permissions": true,
    "path": "/Users/dev/projects/myapp"
  }
}
```

**Template roles field:**
```yaml
name: feature-impl
description: Implement a feature
roles: [worker]  # Array, not single "role" field
voice: bashbunni
```
