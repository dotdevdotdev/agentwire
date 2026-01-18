# Mission: Projects Model

> Add project discovery to CLI and Portal as navigation anchors for history and new sessions.

**Branch:** `mission/projects-model` (created on execution)

## Context

Users need a way to:
1. See conversation history even when no sessions are running
2. Create new sessions in a specific project folder

**Solution:** Projects window shows folders with `.agentwire.yml` discovered from machines' `projects_dir`. Click a project to see its history and create new sessions.

**No central registry.** A project exists if it has `.agentwire.yml` in the folder. This file is created by `agentwire new` when starting a session.

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required.

## Wave 2: CLI

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | **Projects utility module** - Create utility to discover projects. `get_projects(machine?)` scans machine's `projects_dir` for folders with `.agentwire.yml`, returns list of `{name, path, type, roles}`. For local machine, reads from config. For remote, uses SSH. | `agentwire/projects.py` |
| 2.2 | **CLI list command** - Add `agentwire projects list`. Shows discovered projects: name, type, path. Options: `--machine <id>` to filter, `--json`. | `agentwire/__main__.py` |

## Wave 3: Portal API

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | **List projects endpoint** - `GET /api/projects`. Query: `machine` (optional filter). Returns discovered projects from all machines (or specified machine): `{name, path, type, roles, machine}`. Uses CLI internally. | `agentwire/server.py` |

## Wave 4: Portal UI

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | **Projects window** - New ListWindow for projects. Columns: Name, Type, Path, Machine. Click row to select. Groups by machine if multiple. | `agentwire/static/js/windows/projects-window.js` |
| 4.2 | **Project detail panel** - When project selected, show: name, path, type, roles, machine. "New Session" button (opens new session modal pre-filled with project path). "History" section placeholder (enabled by conversation-history mission). | `agentwire/static/js/windows/projects-window.js` |
| 4.3 | **Menu bar reorganization** - Remove owl icon. Reorder: Projects, Sessions on left. Add cog icon dropdown on right containing Machines, Config. | `agentwire/templates/desktop.html`, `agentwire/static/js/desktop.js` |

## Technical Notes

### Discovery Logic

```python
def get_projects(machine: str | None = None) -> list[dict]:
    """Discover projects from machine's projects_dir."""
    projects = []

    # Local machine (implicit) - uses projects.dir from main config
    if machine is None or machine == 'local':
        projects_dir = config.get('projects.dir', '~/projects')
        for folder in Path(projects_dir).expanduser().iterdir():
            if (folder / '.agentwire.yml').exists():
                cfg = yaml.safe_load((folder / '.agentwire.yml').read_text())
                projects.append({
                    'name': folder.name,
                    'path': str(folder),
                    'type': cfg.get('type', 'claude-bypass'),
                    'roles': cfg.get('roles', []),
                    'machine': 'local'
                })

    # Remote machines - each has projects_dir in machines.json
    if machine is None:
        for m in get_remote_machines():
            if m.get('projects_dir'):
                # SSH to list folders with .agentwire.yml
                remote_projects = discover_remote_projects(m)
                projects.extend(remote_projects)
    elif machine != 'local':
        m = get_machine(machine)
        if m.get('projects_dir'):
            projects.extend(discover_remote_projects(m))

    return projects
```

### Machine Config

- **Local**: Uses `projects.dir` from `~/.agentwire/config.yaml` (already exists)
- **Remote**: Each machine in `machines.json` can have optional `projects_dir` field

### No Central Registry

Projects are discovered, not registered. Benefits:
- `.agentwire.yml` travels with git repos
- No sync issues between machines
- CLI `agentwire new` already creates the file
- Simple mental model: folder has config = it's a project

## Completion Criteria

- [ ] `agentwire projects list` shows discovered projects
- [ ] Portal has Projects window accessible from menu bar
- [ ] Menu bar reorganized: owl removed, Projects + Sessions (left) | cog menu (right)
- [ ] Clicking project shows details with "New Session" button
- [ ] Project detail has placeholder for History (enabled by next mission)

## Dependencies

This mission is a **prerequisite** for:
- `conversation-history` - History shown in project detail panel
