# Mission: CLI Full Parity

> Add worktree support, remote parity for all session commands, new recreate/fork commands, then refactor portal to use CLI.

**Branch:** `mission/cli-worktree-support` (created on execution)

## Context

Currently there are two architecture issues:

1. **Portal vs CLI inconsistency** - Portal has worktree logic built-in, CLI doesn't
2. **No remote CLI support** - All CLI commands only work locally, despite `@machine` being part of naming convention

**Goal:**
- CLI is the source of truth for all session operations
- All session commands work with `session@machine` format
- Portal calls CLI via asyncio subprocess

---

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - all code changes.

---

## Wave 2: Remote Infrastructure

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Add `_run_remote(machine_id, command)` helper that SSHs and runs command | `__main__.py` |
| 2.2 | Add `_parse_session_target(name)` helper returning `(session, machine_id)` | `__main__.py` |
| 2.3 | Add `_get_machine_config(machine_id)` helper to load from machines.json | `__main__.py` |

**Helper patterns:**
```python
def _parse_session_target(name: str) -> tuple[str, str | None]:
    """Parse 'session@machine' into (session, machine_id)."""
    if "@" in name:
        session, machine = name.rsplit("@", 1)
        return session, machine
    return name, None

def _run_remote(machine_id: str, command: str) -> subprocess.CompletedProcess:
    """Run command on remote machine via SSH."""
    machine = _get_machine_config(machine_id)
    host = machine["host"]
    return subprocess.run(["ssh", host, command], capture_output=True, text=True)
```

---

## Wave 3: Existing Commands Remote Support

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Update `cmd_send` to work with `session@machine` | `__main__.py` |
| 3.2 | Update `cmd_send_keys` to work with `session@machine` | `__main__.py` |
| 3.3 | Update `cmd_output` to work with `session@machine` | `__main__.py` |
| 3.4 | Update `cmd_kill` to work with `session@machine` | `__main__.py` |
| 3.5 | Update `cmd_list` to show sessions from ALL registered machines by default | `__main__.py` |

**Pattern for each command:**
```python
def cmd_send(args) -> int:
    session, machine_id = _parse_session_target(args.session)

    if machine_id:
        # Remote: SSH and run tmux command
        cmd = f"tmux send-keys -t {shlex.quote(session)} {shlex.quote(prompt)} Enter"
        result = _run_remote(machine_id, cmd)
    else:
        # Local: existing logic
        ...
```

**List behavior:**
```
$ agentwire list
LOCAL:
  api: 1 window (~/projects/api)
  auth: 1 window (~/projects/auth)

dotdev-pc:
  ml: 1 window (~/projects/ml)
  training: 1 window (~/projects/training)

gpu-server:
  (no sessions)
```

---

## Wave 4: CLI Worktree Support (`agentwire new`)

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Parse `project/branch` and `project/branch@machine` formats | `__main__.py` |
| 4.2 | Import and use `ensure_worktree` from `worktree.py` | `__main__.py` |
| 4.3 | Create branch if needed (use config `auto_create_branch`) | `__main__.py` |
| 4.4 | Calculate worktree path using config suffix | `__main__.py` |
| 4.5 | Handle remote worktrees - SSH to create worktree on remote | `__main__.py` |
| 4.6 | Add `--json` flag for machine-readable output | `__main__.py` |

**Logic for `cmd_new`:**
```python
from .worktree import ensure_worktree, get_session_path, parse_session_name

# Parse session name
project, branch, machine = parse_session_name(name)

if machine:
    # Remote session with optional worktree
    if branch:
        # SSH to remote, create worktree there
        cmd = f"cd ~/projects/{project} && git worktree add ..."
        _run_remote(machine, cmd)
    # Then create tmux session on remote
    ...
elif branch and config.projects.worktrees.enabled:
    # Local worktree session
    project_path = projects_dir / project
    session_path = get_session_path(...)
    ensure_worktree(project_path, branch, session_path, ...)
else:
    # Simple local session
    session_path = projects_dir / name
```

---

## Wave 5: New CLI Commands

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Add `agentwire recreate -s <name>` (local + remote, --json) | `__main__.py` |
| 5.2 | Add `agentwire fork -s <source> -t <target>` (local + remote, --json) | `__main__.py` |

**`recreate` logic:**
1. Kill existing session (local or remote)
2. Remove worktree
3. Pull latest on main repo
4. Create new worktree with timestamp branch
5. Create new session

**`fork` logic:**
1. Create new worktree from current branch state
2. Copy Claude session file to new worktree
3. Create new session in forked worktree

---

## Wave 6: Portal Refactor

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 6.1 | Create helper `async def run_agentwire_cmd(args)` using asyncio subprocess | None - starts immediately |
| 6.2 | Replace `api_create_session` with `agentwire new --json` | 4.1-4.6, 6.1 |
| 6.3 | Replace `api_recreate_session` with `agentwire recreate --json` | 5.1, 6.1 |
| 6.4 | Replace `api_fork_session` with `agentwire fork --json` | 5.2, 6.1 |
| 6.5 | Replace `api_spawn_sibling` with `agentwire new --json` | 4.1-4.6, 6.1 |

**Subprocess helper:**
```python
async def run_agentwire_cmd(self, args: list[str]) -> tuple[bool, dict]:
    """Run agentwire CLI command, parse JSON output."""
    proc = await asyncio.create_subprocess_exec(
        "agentwire", *args, "--json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        return True, json.loads(stdout.decode())
    return False, {"error": stderr.decode()}
```

---

## Wave 7: Testing & Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 7.1 | Test: `agentwire list` shows local + all remote sessions | 3.5 |
| 7.2 | Test: `agentwire send -s test@remote "hello"` works | 3.1 |
| 7.3 | Test: `agentwire new -s myapp/feature` creates local worktree | 4.1-4.5 |
| 7.4 | Test: `agentwire new -s myapp/feature@remote` creates remote worktree | 4.5 |
| 7.5 | Test: `agentwire recreate -s myapp/feature` works | 5.1 |
| 7.6 | Test: `agentwire fork -s myapp/feature -t myapp/copy` works | 5.2 |
| 7.7 | Test: Dashboard operations work via CLI subprocess | 6.2-6.5 |
| 7.8 | Update CLAUDE.md with all CLI commands and remote examples | None - starts immediately |

---

## Completion Criteria

- [ ] `agentwire list` shows sessions from local + all registered machines
- [ ] `agentwire send/output/kill -s session@machine` work remotely
- [ ] `agentwire new -s project/branch` creates local worktree
- [ ] `agentwire new -s project/branch@machine` creates remote worktree
- [ ] `agentwire recreate -s <name>` works locally and remotely
- [ ] `agentwire fork -s <source> -t <target>` works locally and remotely
- [ ] All commands support `--json` for machine-readable output
- [ ] Portal uses CLI subprocess for all session operations
- [ ] CLAUDE.md documents all commands with remote examples

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

### Machine Config

Stored in `~/.agentwire/machines.json`:
```json
{
  "machines": [
    {"id": "dotdev-pc", "host": "dotdev-pc", "projects_dir": "/home/dotdev/projects"},
    {"id": "gpu-server", "host": "gpu.internal", "projects_dir": "/data/projects"}
  ]
}
```

### Design Decisions

- Portal calls CLI via `asyncio.create_subprocess_exec` (clean separation)
- `recreate` and `fork` are new CLI commands (full CLI parity)
- All session commands work with `session@machine` format
- `agentwire list` aggregates from all machines by default
- All commands support `--json` for machine-readable output

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
