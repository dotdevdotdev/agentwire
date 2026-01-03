# Mission: CLI Worktree Support

> Add worktree/branch creation to CLI, add recreate/fork commands, then refactor portal to use CLI via subprocess.

**Branch:** `mission/cli-worktree-support` (created on execution)

## Context

Currently there's an architecture inconsistency:
- **Portal** (`server.py`) has worktree logic built-in (creates branches, worktrees, sessions)
- **CLI** (`agentwire new`) only creates simple sessions, no worktree support

This means:
- `agentwire new -s project/branch` fails (path doesn't exist)
- Portal works but bypasses CLI, making it untestable
- Two codepaths doing the same thing = maintenance burden

**Goal:** CLI is the source of truth. Portal calls CLI commands via asyncio subprocess.

---

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - all code changes.

---

## Wave 2: CLI Worktree Support (`agentwire new`)

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Parse `project/branch` and `project/branch@machine` formats | `__main__.py` |
| 2.2 | Import and use `ensure_worktree` from `worktree.py` | `__main__.py` |
| 2.3 | Create branch if needed (use config `auto_create_branch`) | `__main__.py` |
| 2.4 | Calculate worktree path using config suffix | `__main__.py` |
| 2.5 | Handle remote worktrees (`@machine` suffix) | `__main__.py` |
| 2.6 | Add `--json` flag for machine-readable output | `__main__.py` |

**Logic for `cmd_new`:**
```python
from .worktree import ensure_worktree, get_session_path, parse_session_name

# Parse session name
project, branch, machine = parse_session_name(name)

if machine:
    # Remote session - SSH to machine
    # Create worktree on remote if branch specified
    ...
elif branch and config.projects.worktrees.enabled:
    # Local worktree session: project/branch
    project_path = projects_dir / project
    session_path = get_session_path(project, branch, projects_dir, config.projects.worktrees.suffix)

    if not ensure_worktree(project_path, branch, session_path, config.projects.worktrees.auto_create_branch):
        print(f"Failed to create worktree for '{branch}'", file=sys.stderr)
        return 1
else:
    # Simple local session
    session_path = projects_dir / name
```

---

## Wave 3: New CLI Commands

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Add `agentwire recreate -s <name>` command (with --json support) | `__main__.py` |
| 3.2 | Add `agentwire fork -s <source> -t <target>` command (with --json support) | `__main__.py` |

**`recreate` logic:**
1. Kill existing session (`agentwire kill`)
2. Remove worktree (`git worktree remove`)
3. Pull latest on main repo
4. Create new worktree with timestamp branch
5. Create new session (`agentwire new`)

**`fork` logic:**
1. Create new worktree from current branch state
2. Copy Claude session file to new worktree
3. Create new session in forked worktree

---

## Wave 4: Portal Refactor

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 4.1 | Create helper `async def run_agentwire_cmd(args: list[str])` using `asyncio.create_subprocess_exec` | None - starts immediately |
| 4.2 | Replace `api_create_session` logic with `agentwire new` subprocess call | 2.1-2.5, 4.1 |
| 4.3 | Replace `api_recreate_session` logic with `agentwire recreate` subprocess call | 3.1, 4.1 |
| 4.4 | Replace `api_fork_session` logic with `agentwire fork` subprocess call | 3.2, 4.1 |
| 4.5 | Replace `api_spawn_sibling` logic with `agentwire new` subprocess call | 2.1-2.5, 4.1 |

**Subprocess helper pattern:**
```python
async def run_agentwire_cmd(self, args: list[str]) -> tuple[bool, str]:
    """Run agentwire CLI command via subprocess."""
    proc = await asyncio.create_subprocess_exec(
        "agentwire", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    success = proc.returncode == 0
    output = stdout.decode() if success else stderr.decode()
    return success, output
```

---

## Wave 5: Testing & Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 5.1 | Test: `agentwire new -s myapp/feature` creates local worktree | 2.1-2.5 |
| 5.2 | Test: `agentwire new -s myapp/feature@remote` creates remote worktree | 2.5 |
| 5.3 | Test: `agentwire recreate -s myapp/feature` works | 3.1 |
| 5.4 | Test: `agentwire fork -s myapp/feature -t myapp/feature-copy` works | 3.2 |
| 5.5 | Test: Dashboard "Create Session" still works via CLI | 4.2 |
| 5.6 | Test: Dashboard Recreate/Fork buttons work via CLI | 4.3, 4.4 |
| 5.7 | Update CLAUDE.md with new CLI commands | None - starts immediately |

---

## Completion Criteria

- [ ] `agentwire new -s project/branch` creates worktree and session
- [ ] `agentwire new -s project/branch@machine` creates remote worktree and session
- [ ] `agentwire new -s project/branch` creates branch if it doesn't exist
- [ ] `agentwire recreate -s <name>` destroys and recreates session with fresh worktree
- [ ] `agentwire fork -s <source> -t <target>` creates parallel session with copied state
- [ ] Portal uses CLI subprocess for all session operations
- [ ] CLAUDE.md documents all new CLI commands

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

### Design Decisions

- Portal calls CLI via `asyncio.create_subprocess_exec` (clean separation)
- `recreate` and `fork` are new CLI commands (full CLI parity)
- Remote worktrees supported (`project/branch@machine` format)
- CLI commands support `--json` flag for machine-readable output (portal uses this)

### JSON Output Format

```json
{
  "success": true,
  "session": "myapp/feature",
  "path": "/Users/dotdev/projects/myapp-worktrees/feature",
  "branch": "feature",
  "machine": null
}
```

On error:
```json
{
  "success": false,
  "error": "Failed to create worktree: not a git repository"
}
```
