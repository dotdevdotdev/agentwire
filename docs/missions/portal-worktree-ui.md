# Mission: Portal Create Session Improvements

> Add machine selector, git detection, worktree options, and input validation to the Create Session form.

**Branch:** `mission/portal-worktree-ui` (created on execution)

## Context

The CLI now supports worktrees (`project/branch`) and remote sessions (`session@machine`), but the portal UI doesn't expose this functionality. When creating a session from the dashboard:

- No machine selector (can only create local sessions)
- User can't see if the target path is a git repo
- No option to create a worktree
- No branch name input
- No input validation (@ and / in names cause issues)

**Goals:**
1. Machine dropdown (default: local) that appends `@machine` to session name
2. Git detection with worktree checkbox and branch input
3. Input validation to prevent problematic characters

---

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - all code changes.

---

## Wave 2: Backend API

All tasks start immediately (no dependencies):

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Add `GET /api/check-path` endpoint - returns `{exists, is_git, current_branch}` | `server.py` |
| 2.2 | Update `POST /api/create` to accept `machine`, `worktree`, `branch` parameters | `server.py` |
| 2.3 | Update `api_create_session` to build proper CLI args for machine and worktree | `server.py` |

**2.1 Check Path Endpoint:**
```python
async def api_check_path(self, request: web.Request) -> web.Response:
    """Check if a path exists and is a git repo."""
    path = request.query.get("path", "")
    machine = request.query.get("machine", "local")

    if machine != "local":
        # Remote path check via SSH
        result = _run_remote(machine, f"test -d {shlex.quote(path)} && echo exists")
        exists = "exists" in result.stdout
        is_git = False
        current_branch = None
        if exists:
            result = _run_remote(machine, f"test -d {shlex.quote(path)}/.git && echo git")
            is_git = "git" in result.stdout
            if is_git:
                result = _run_remote(machine, f"cd {shlex.quote(path)} && git rev-parse --abbrev-ref HEAD")
                current_branch = result.stdout.strip() if result.returncode == 0 else None
    else:
        # Local path check
        expanded = Path(path).expanduser().resolve()
        exists = expanded.exists()
        is_git = exists and (expanded / ".git").exists()
        current_branch = None
        if is_git:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=expanded, capture_output=True, text=True
            )
            current_branch = result.stdout.strip() if result.returncode == 0 else None

    return web.json_response({
        "exists": exists,
        "is_git": is_git,
        "current_branch": current_branch
    })
```

**2.3 Create Session Logic:**
```python
# Build session name for CLI
if machine and machine != "local":
    # Remote session: name@machine or project/branch@machine
    if worktree and branch:
        cli_session = f"{project}/{branch}@{machine}"
    else:
        cli_session = f"{name}@{machine}"
else:
    # Local session: name or project/branch
    if worktree and branch:
        cli_session = f"{project}/{branch}"
    else:
        cli_session = name

args = ["new", "-s", cli_session]
# Don't pass -p when using worktree (CLI derives path from convention)
if not worktree and custom_path:
    args.extend(["-p", custom_path])
```

---

## Wave 3: Frontend - Machine Selector

All tasks start immediately (parallel with Wave 2):

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Add machine dropdown to Create Session form HTML (after Session Name) | `dashboard.html` |
| 3.2 | Add CSS for machine selector with suffix preview | `dashboard.css` |
| 3.3 | Populate machine dropdown from `/api/machines` on page load | `dashboard.js` |
| 3.4 | Show `@machine` suffix preview next to session name when remote selected | `dashboard.js` |
| 3.5 | Update `createSession()` to include machine in payload | `dashboard.js` |

**3.1 Form HTML (after Session Name row):**
```html
<div class="form-row">
    <label>Session Name</label>
    <div class="session-name-input">
        <input type="text" id="sessionName" placeholder="e.g., assistant">
        <span class="machine-suffix" id="machineSuffix"></span>
    </div>
</div>
<div class="form-row">
    <label>Machine</label>
    <select id="sessionMachine">
        <option value="local">Local</option>
        <!-- Populated from /api/machines -->
    </select>
</div>
```

**3.4 Suffix Preview:**
```javascript
function updateMachineSuffix() {
    const machine = document.getElementById('sessionMachine').value;
    const suffix = document.getElementById('machineSuffix');
    if (machine === 'local') {
        suffix.textContent = '';
    } else {
        suffix.textContent = `@${machine}`;
    }
}
```

---

## Wave 4: Frontend - Input Validation

All tasks start immediately (parallel with Waves 2 & 3):

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Add input validation to session name (block `@`, `/`, spaces, special chars) | `dashboard.js` |
| 4.2 | Show inline validation error message | `dashboard.js` |
| 4.3 | Disable Create button when validation fails | `dashboard.js` |

**4.1 Validation Pattern:**
```javascript
const INVALID_SESSION_CHARS = /[@\/\s\\:*?"<>|]/;

function validateSessionName(name) {
    if (!name) return { valid: false, error: 'Session name is required' };
    if (INVALID_SESSION_CHARS.test(name)) {
        return { valid: false, error: 'Name cannot contain @ / \\ : * ? " < > | or spaces' };
    }
    if (name.startsWith('.') || name.startsWith('-')) {
        return { valid: false, error: 'Name cannot start with . or -' };
    }
    return { valid: true };
}
```

---

## Wave 5: Frontend - Git/Worktree Options

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Add git options section to form HTML (worktree checkbox, branch input) | `dashboard.html` |
| 5.2 | Add CSS for git status indicator and worktree options | `dashboard.css` |
| 5.3 | Add path change handler that calls `/api/check-path` with debounce | `dashboard.js` |
| 5.4 | Show/hide git options based on detection, include machine in check | `dashboard.js` |
| 5.5 | Update `createSession()` to include worktree and branch in payload | `dashboard.js` |

**5.1 Form HTML (after Project Path row):**
```html
<div class="form-row git-options" id="gitOptions" style="display: none;">
    <div class="git-status">
        <span class="git-indicator"></span>
        <span class="git-branch-label">on <span class="git-branch"></span></span>
    </div>
    <label class="checkbox-option">
        <input type="checkbox" id="useWorktree" checked>
        <span>Create worktree</span>
    </label>
    <div class="branch-row" id="branchRow">
        <label>Branch Name</label>
        <input type="text" id="branchName" placeholder="e.g., jan-3-work">
    </div>
</div>
```

**5.3 Debounced Path Check:**
```javascript
let pathCheckTimeout = null;

function onPathChange() {
    const path = document.getElementById('projectPath').value.trim();
    const machine = document.getElementById('sessionMachine').value;

    clearTimeout(pathCheckTimeout);
    pathCheckTimeout = setTimeout(async () => {
        if (!path) {
            hideGitOptions();
            return;
        }
        const params = new URLSearchParams({ path, machine });
        const res = await fetch(`/api/check-path?${params}`);
        const data = await res.json();

        if (data.is_git) {
            showGitOptions(data.current_branch);
        } else {
            hideGitOptions();
        }
    }, 300);
}

// Also re-check when machine changes
document.getElementById('sessionMachine').addEventListener('change', onPathChange);
```

---

## Wave 6: Smart Defaults

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 6.1 | Auto-suggest timestamp-based branch name (e.g., `jan-3-work`) | 5.4 |
| 6.2 | When worktree unchecked, hide branch input | 5.4 |
| 6.3 | Update default projects path when machine changes (use machine's projects_dir) | 3.3 |

**6.1 Timestamp Branch Suggestion:**
```javascript
function suggestBranchName() {
    const now = new Date();
    const month = now.toLocaleString('en', { month: 'short' }).toLowerCase();
    const day = now.getDate();
    return `${month}-${day}-work`;  // e.g., "jan-3-work"
}

// Pre-fill when git options shown
function showGitOptions(currentBranch) {
    document.getElementById('gitOptions').style.display = 'block';
    document.querySelector('.git-branch').textContent = currentBranch || 'unknown';

    const branchInput = document.getElementById('branchName');
    if (!branchInput.value) {
        branchInput.value = suggestBranchName();
    }
}
```

---

## Wave 7: Testing & Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 7.1 | Test: Machine dropdown populates from API | 3.3 |
| 7.2 | Test: Selecting remote machine shows @suffix and updates path check | 3.4, 5.4 |
| 7.3 | Test: Invalid chars in session name show error, block create | 4.1-4.3 |
| 7.4 | Test: Git repo path shows worktree options | 5.1-5.5, 2.1 |
| 7.5 | Test: Worktree created on remote machine | 2.2, 2.3 |
| 7.6 | Test: Non-git paths work as before | All |
| 7.7 | Update CLAUDE.md with new Create Session form documentation | All |

---

## Completion Criteria

- [ ] Machine dropdown shows local + all configured machines
- [ ] Selecting remote machine shows `@machine` suffix next to session name
- [ ] Session name blocks `@`, `/`, `\`, spaces, and other problem characters
- [ ] Validation error shown inline, Create button disabled
- [ ] `/api/check-path` works for local and remote paths
- [ ] Git repos show worktree checkbox (default checked) and branch input
- [ ] Branch input pre-filled with timestamp suggestion (e.g., `jan-3-work`)
- [ ] Worktree checkbox hidden for non-git paths
- [ ] Session created with worktree when checkbox enabled
- [ ] Remote worktree sessions work correctly
- [ ] CLAUDE.md documents new form options

---

## Technical Notes

### Full Session Name Derivation

| Machine | Worktree | Session Name Sent to CLI |
|---------|----------|--------------------------|
| local | no | `myapp` |
| local | yes | `myapp/jan-3-work` |
| gpu-server | no | `myapp@gpu-server` |
| gpu-server | yes | `myapp/jan-3-work@gpu-server` |

### Form State Matrix

| Path State | Machine | Git Options | Branch Input |
|------------|---------|-------------|--------------|
| Empty | Any | Hidden | Hidden |
| Non-git | Local | Hidden | Hidden |
| Non-git | Remote | Hidden | Hidden |
| Git repo | Local | Shown (checked) | Shown |
| Git repo | Remote | Shown (checked) | Shown |
| Git + unchecked | Any | Shown | Hidden |

### Validation Rules

| Character/Pattern | Reason Blocked |
|-------------------|----------------|
| `@` | Machine separator |
| `/` | Branch separator |
| `\` | Windows path issues |
| Spaces | Shell escaping issues |
| `: * ? " < > \|` | Filesystem restrictions |
| Leading `.` or `-` | Hidden files, flag confusion |

### API Machines Response (existing)

```json
[
  { "id": "local", "host": "macbook", "local": true, "status": "online" },
  { "id": "gpu-server", "host": "192.168.1.50", "user": "ubuntu", "status": "online" }
]
```
