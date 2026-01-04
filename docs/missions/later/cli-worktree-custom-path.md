# Mission: CLI Worktree with Custom Path

> Allow `agentwire new -s name/branch -p /path/to/repo` to create worktrees even when path differs from session name.

**Status:** Deferred - test after portal-worktree-ui to see if needed

## Problem

Currently the CLI has a gap:
- `agentwire new -s project/branch` → derives path from name (`~/projects/project`)
- `agentwire new -s name -p /custom/path` → uses path but skips worktree creation

This breaks when folder name differs from session-safe name:
- Folder: `~/projects/dotdev.dev`
- Session name must be: `dotdev_dev` (no dots allowed)
- CLI looks for: `~/projects/dotdev_dev` (doesn't exist)

## Desired Behavior

```bash
# Should create worktree at ~/projects/dotdev.dev-worktrees/feature/
agentwire new -s dotdev_dev/feature -p ~/projects/dotdev.dev
```

When `-p` points to a git repo and session name has `/branch`:
1. Use `-p` as the main repo path
2. Create worktree at `{repo}-worktrees/{branch}/`
3. Create session in the worktree

## Workaround

Manually create worktree, then pass worktree path to `-p`:

```bash
cd ~/projects/dotdev.dev
git worktree add ../dotdev.dev-worktrees/feature -b feature
agentwire new -s dotdev_dev/feature -p ~/projects/dotdev.dev-worktrees/feature
```
