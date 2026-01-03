# Mission: Portal Worktree UI

> Add git detection and worktree options to the Create Session form in the portal dashboard.

**Branch:** `mission/portal-worktree-ui` (created on execution)

## Context

The CLI now supports worktrees via session name convention (`project/branch`), but the portal UI doesn't expose this functionality. When creating a session from the dashboard:

- User can't see if the target path is a git repo
- No option to create a worktree
- No branch name input
- Sessions are created directly in the path without worktrees

**Goal:** When creating a session for a git repo, default to worktree creation with a branch name input.

---

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required - all code changes.

---

## Wave 2: Backend API

All tasks start immediately (no dependencies):

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Add `GET /api/check-path` endpoint - returns `{exists: bool, is_git: bool, current_branch: str}` | `server.py` |
| 2.2 | Update `POST /api/create` to accept `worktree: bool` and `branch: str` parameters | `server.py` |
| 2.3 | Update `api_create_session` to build proper CLI args when worktree requested | `server.py` |

**2.1 Check Path Endpoint:**
```python
async def api_check_path(self, request: web.Request) -> web.Response:
    """Check if a path exists and is a git repo."""
    path = request.query.get("path", "")
    expanded = Path(path).expanduser().resolve()

    exists = expanded.exists()
    is_git = exists and (expanded / ".git").exists()
    current_branch = None

    if is_git:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=expanded, capture_output=True, text=True
        )
        if result.returncode == 0:
            current_branch = result.stdout.strip()

    return web.json_response({
        "exists": exists,
        "is_git": is_git,
        "current_branch": current_branch
    })
```

**2.3 Logic:**
- If `worktree=true` and `branch` provided:
  - Extract project name from path (last component)
  - Build session name as `project/branch` for CLI
  - Don't pass `-p path` (let CLI derive worktree path from convention)
- If `worktree=false` or no branch:
  - Pass name and path as before

---

## Wave 3: Frontend Form Updates

All tasks start immediately (parallel with Wave 2):

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Add worktree checkbox and branch input to Create Session form HTML | `dashboard.html` |
| 3.2 | Add CSS for git status indicator and worktree options | `dashboard.css` |
| 3.3 | Add path change handler that calls `/api/check-path` with debounce | `dashboard.js` |
| 3.4 | Show/hide worktree options based on git detection | `dashboard.js` |
| 3.5 | Update `createSession()` to include worktree and branch in payload | `dashboard.js` |

**3.1 Form HTML additions (after Project Path row):**
```html
<div class="form-row git-options" id="gitOptions" style="display: none;">
    <div class="git-status">
        <span class="git-indicator"></span>
        <span class="git-branch"></span>
    </div>
    <label class="checkbox-option">
        <input type="checkbox" id="useWorktree" checked>
        <span>Create worktree</span>
    </label>
    <div class="branch-input" id="branchInput">
        <label>Branch Name</label>
        <input type="text" id="branchName" placeholder="e.g., feature-x">
    </div>
</div>
```

**3.3 Debounced path check:**
```javascript
let pathCheckTimeout = null;

function onPathChange(path) {
    clearTimeout(pathCheckTimeout);
    pathCheckTimeout = setTimeout(async () => {
        if (!path) {
            hideGitOptions();
            return;
        }
        const res = await fetch(`/api/check-path?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        if (data.is_git) {
            showGitOptions(data.current_branch);
        } else {
            hideGitOptions();
        }
    }, 300);
}
```

---

## Wave 4: Smart Defaults

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 4.1 | Auto-populate branch name from session name when empty | 3.4 |
| 4.2 | Suggest timestamp-based branch names (e.g., `jan-3-work`) | 3.4 |
| 4.3 | Show current branch in git status indicator | 3.3, 3.4 |

**4.2 Timestamp branch suggestion:**
```javascript
function suggestBranchName() {
    const now = new Date();
    const month = now.toLocaleString('en', { month: 'short' }).toLowerCase();
    const day = now.getDate();
    return `${month}-${day}-work`;  // e.g., "jan-3-work"
}
```

---

## Wave 5: Testing & Polish

| Task | Description | Needs Output From |
|------|-------------|-------------------|
| 5.1 | Test: Create session for git repo shows worktree options | 3.1-3.5, 2.1 |
| 5.2 | Test: Create session for non-git path hides worktree options | 3.1-3.5, 2.1 |
| 5.3 | Test: Worktree is created when checkbox enabled | 2.2, 2.3, 3.5 |
| 5.4 | Test: Session created directly in path when checkbox disabled | 2.2, 2.3, 3.5 |
| 5.5 | Update CLAUDE.md with worktree UI documentation | All |

---

## Completion Criteria

- [ ] `/api/check-path` returns git status for any path
- [ ] Create Session form shows git indicator for git repos
- [ ] Worktree checkbox appears and defaults to checked for git repos
- [ ] Branch name input with smart default (timestamp-based)
- [ ] Unchecking worktree creates session directly in path
- [ ] Session created with worktree when checkbox enabled
- [ ] Non-git paths work as before (no worktree options shown)

---

## Technical Notes

### Session Name Derivation

When worktree mode:
- Path: `~/projects/dotdev.dev/`
- Branch: `jan-3-work`
- Derived project: `dotdev.dev` (from path)
- CLI session name: `dotdev.dev/jan-3-work`
- Worktree path: `~/projects/dotdev.dev-worktrees/jan-3-work/`

### Form State

| Path State | Worktree Checkbox | Branch Input |
|------------|-------------------|--------------|
| Empty/invalid | Hidden | Hidden |
| Non-git directory | Hidden | Hidden |
| Git repository | Shown (checked) | Shown |
| Git repo + unchecked | Shown (unchecked) | Hidden |

### Error Cases

| Error | Handling |
|-------|----------|
| Path doesn't exist | Show error, disable create |
| Branch already exists | CLI handles (uses existing branch) |
| Worktree already exists | CLI handles (reuses worktree) |
| Not a git repo but worktree checked | Shouldn't happen (checkbox hidden) |
