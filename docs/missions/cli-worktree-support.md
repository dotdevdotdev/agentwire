# Mission: CLI Worktree Support

> Add worktree/branch creation to `agentwire new` CLI, then refactor portal to use CLI commands.

**Branch:** `mission/cli-worktree-support` (created on execution)

## Context

Currently there's an architecture inconsistency:
- **Portal** (`server.py`) has worktree logic built-in (creates branches, worktrees, sessions)
- **CLI** (`agentwire new`) only creates simple sessions, no worktree support

This means:
- `agentwire new -s project/branch` fails (path doesn't exist)
- Portal works but bypasses CLI, making it untestable
- Two codepaths doing the same thing = maintenance burden

**Goal:** CLI is the source of truth. Portal calls CLI commands.

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - all code changes.

---

## Wave 2: CLI Worktree Support

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Parse `project/branch` format in session name | `__main__.py` |
| 2.2 | Import and use `ensure_worktree` from `worktree.py` | `__main__.py` |
| 2.3 | Create branch if needed (like server does) | `__main__.py` |
| 2.4 | Calculate worktree path using config suffix | `__main__.py` |

**2.1-2.4 Logic (update `cmd_new`):**
```python
from .worktree import ensure_worktree, get_session_path, parse_session_name

# Parse session name
project, branch, machine = parse_session_name(name)

if branch and config.projects.worktrees.enabled:
    # Worktree session: project/branch
    project_path = projects_dir / project
    session_path = get_session_path(project, branch, projects_dir, config.projects.worktrees.suffix)

    if not ensure_worktree(project_path, branch, session_path, config.projects.worktrees.auto_create_branch):
        print(f"Failed to create worktree for '{branch}'", file=sys.stderr)
        return 1
else:
    # Simple session
    session_path = projects_dir / name
```

---

## Wave 3: Portal Refactor

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 3.1 | Replace `api_create_session` subprocess calls with `agentwire new` CLI | 2.1-2.4 |
| 3.2 | Replace recreate session logic with CLI commands | 2.1-2.4 |
| 3.3 | Replace fork/spawn-sibling with CLI commands | 2.1-2.4 |

**Note:** Portal still handles HTTP/WebSocket, but delegates session creation to CLI.

---

## Wave 4: Testing & Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 4.1 | Test: `agentwire new -s myapp/feature` creates worktree | 2.1-2.4 |
| 4.2 | Test: Dashboard "Create Session" still works | 3.1 |
| 4.3 | Test: Recreate/Fork still work | 3.2, 3.3 |
| 4.4 | Update CLAUDE.md with worktree CLI examples | None - starts immediately |

---

## Completion Criteria

- [ ] `agentwire new -s project/branch` creates worktree and session
- [ ] `agentwire new -s project/branch` creates branch if it doesn't exist
- [ ] Portal "Create Session" uses CLI under the hood
- [ ] All session creation paths use same CLI command
- [ ] CLAUDE.md documents worktree session creation

---

## Technical Notes

### Session Name Parsing

Already exists in `worktree.py`:
```python
def parse_session_name(name: str) -> tuple[str, str | None, str | None]:
    """Parse session name into (project, branch, machine)."""
```

### Worktree Path Convention

```
~/projects/myapp/                    # Main repo
~/projects/myapp-worktrees/          # Worktree container
~/projects/myapp-worktrees/feature/  # Worktree for "myapp/feature" session
```

### Config

```yaml
projects:
  dir: "~/projects"
  worktrees:
    enabled: true
    suffix: "-worktrees"
    auto_create_branch: true
```
