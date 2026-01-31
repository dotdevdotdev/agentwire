# Session Snapshots

> Automatic save points before major operations, with voice-triggered rollback.

## Problem

When delegating complex tasks to AI agents, there's always anxiety about irreversible changes. What if the agent deletes the wrong file? Overwrites important code? Makes a series of changes that break everything in a subtle way?

Currently, recovery requires:
- Manually checking git status/diff
- Understanding what changed and why
- Crafting git commands to revert specific changes
- Hoping the agent didn't touch untracked files

This friction discourages users from delegating ambitious tasks. The safety net is too manual.

## Proposed Solution

**Automatic snapshots before risky operations, with instant voice rollback.**

### Core Mechanics

1. **Pre-Operation Snapshots**
   - Before file writes, git operations, or shell commands, capture state
   - Snapshot includes: git stash of changes, list of untracked files, file hashes
   - Lightweight - only captures what's needed, not full disk images

2. **Voice Commands**
   - "Rollback" - restore last snapshot
   - "Rollback to before the migration" - named/contextual rollback
   - "What changed since last snapshot?" - diff summary via voice
   - "Save checkpoint" - manual snapshot with voice label

3. **Automatic Naming**
   - Snapshots get contextual names from the task: "before-auth-refactor", "before-db-migration"
   - Recent snapshots listed with `agentwire snapshots list`
   - Configurable retention (default: last 10 per session)

### Implementation Sketch

```yaml
# .agentwire.yml
snapshots:
  enabled: true
  retention: 10
  triggers:
    - pattern: "rm -rf"
    - pattern: "git reset"
    - pattern: "DROP TABLE"
    - on_worker_spawn: true  # Snapshot before workers start
```

```bash
# CLI commands
agentwire snapshot create "before refactor"  # Manual
agentwire snapshot list                       # Show recent
agentwire snapshot restore latest             # Rollback
agentwire snapshot restore "before-auth"      # Named rollback
agentwire snapshot diff latest                # What changed?
```

```python
# MCP tools for agents
agentwire_snapshot_create(name="before migration")
agentwire_snapshot_restore(name="latest")
agentwire_snapshot_diff(name="latest")
```

### Storage Strategy

```
~/.agentwire/snapshots/
├── {session}/
│   ├── 2024-01-15T10-30-00_before-auth-refactor/
│   │   ├── manifest.json      # What was captured
│   │   ├── git-stash.patch    # Stashed changes
│   │   ├── untracked.tar.gz   # Untracked files backup
│   │   └── file-hashes.json   # For integrity verification
│   └── ...
```

### Integration Points

- **Damage control hooks**: Auto-snapshot before any blocked-then-allowed command
- **Worker lifecycle**: Snapshot when spawning workers, before they start editing
- **Task runner**: Snapshot at task start, restore on task failure
- **Voice interface**: Natural language rollback without touching keyboard

## Implementation Considerations

### What to Capture

| Item | Method | When |
|------|--------|------|
| Staged/unstaged git changes | `git stash create` | Always |
| Untracked files in project | `tar` with exclusions | If configured |
| File modification times | Stat calls | Always |
| Current branch/commit | `git rev-parse` | Always |

### Performance

- Snapshot creation should be <1 second for typical projects
- Use sparse captures - only files in project directory
- Exclude node_modules, venv, build artifacts via .gitignore patterns
- Lazy compression - compress older snapshots in background

### Edge Cases

- **Large untracked files**: Skip or warn if >10MB untracked files
- **Uncommitted binary files**: Capture but warn about size
- **Detached HEAD**: Capture commit hash for reference
- **Worktrees**: Each worktree gets independent snapshots

## Potential Challenges

1. **Storage bloat**: Need aggressive pruning and size limits. Solution: hash-based deduplication, configurable retention.

2. **Partial restores**: User might want to restore one file, not everything. Solution: `agentwire snapshot restore latest --file path/to/file.ts`

3. **Snapshot during active editing**: Race condition if files change during capture. Solution: Brief write lock or copy-on-read strategy.

4. **User expectations**: Snapshots aren't time machines - they capture project state, not system state. Need clear documentation about scope.

5. **Git state conflicts**: Restoring when git state has diverged. Solution: Create new branch with restored state rather than force-overwriting.

## Success Metrics

- Reduced time-to-recovery after agent mistakes
- Increased willingness to delegate risky operations
- Fewer manual git revert/reset commands
- Voice rollback completion rate >95%

## Related Ideas

- Could integrate with session-replay for full action history
- Snapshots could power "what if" branching - try two approaches, keep the better one
- Cross-session snapshots for project-level safety nets
