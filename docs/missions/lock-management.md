# Mission: Lock Management CLI

> Living document. Update this, don't create new versions.

## Status: Complete

## Summary

Add CLI commands to manage session locks for the `ensure` command. Locks can become stale if a process crashes or is killed, blocking future runs.

## Commands

### `agentwire lock list`

Show all locks with metadata.

```
$ agentwire lock list
SESSION          PID     AGE        STATUS
brainstorm       -       2h 15m     stale (no PID)
agentwire-dev    12345   5m         active
ensure-test      99999   3d         stale (process dead)
```

**Output columns:**
- SESSION: Lock name (matches session name)
- PID: Process ID that holds the lock (or `-` if not recorded)
- AGE: How long the lock has existed
- STATUS: `active` (process running) or `stale` (process dead/missing)

**Flags:**
- `--json` - JSON output for scripting

### `agentwire lock clean`

Remove all stale locks (where PID is missing or process is dead).

```
$ agentwire lock clean
Removed 2 stale locks: brainstorm, ensure-test
```

**Flags:**
- `--dry-run` - Show what would be removed without removing
- `--json` - JSON output

### `agentwire lock remove <session>`

Force-remove a specific lock by session name.

```
$ agentwire lock remove brainstorm
Removed lock: brainstorm
```

**Flags:**
- `--json` - JSON output

## Implementation

### Lock file format

Current: Empty file or file containing PID.

Update locking.py to always write PID to lock file:
```
~/.agentwire/locks/{session}.lock
Contents: {pid}\n
```

### Functions needed

In `agentwire/locking.py`:

```python
def list_locks() -> list[dict]:
    """Return list of locks with metadata."""
    # Returns: [{"session": str, "pid": int|None, "age_seconds": int, "status": str}]

def clean_stale_locks(dry_run=False) -> list[str]:
    """Remove locks where PID is dead. Returns list of removed lock names."""

def remove_lock(session: str) -> bool:
    """Force-remove a lock. Returns True if removed."""
```

### CLI integration

Add to `__main__.py`:

```python
# === lock command group ===
lock_parser = subparsers.add_parser("lock", help="Manage session locks")
lock_subparsers = lock_parser.add_subparsers(dest="lock_command")

# lock list
lock_list_parser = lock_subparsers.add_parser("list", help="List all locks")
lock_list_parser.add_argument("--json", action="store_true")

# lock clean
lock_clean_parser = lock_subparsers.add_parser("clean", help="Remove stale locks")
lock_clean_parser.add_argument("--dry-run", action="store_true")
lock_clean_parser.add_argument("--json", action="store_true")

# lock remove
lock_remove_parser = lock_subparsers.add_parser("remove", help="Force-remove a lock")
lock_remove_parser.add_argument("session", help="Session name")
lock_remove_parser.add_argument("--json", action="store_true")
```

## Testing

1. Create a stale lock manually
2. `agentwire lock list` shows it as stale
3. `agentwire lock clean --dry-run` shows it would be removed
4. `agentwire lock clean` removes it
5. `agentwire lock list` shows empty or remaining active locks

## Acceptance Criteria

- [x] `agentwire lock list` shows all locks with PID, age, status
- [x] `agentwire lock clean` removes only stale locks
- [x] `agentwire lock remove <session>` force-removes specific lock
- [x] All commands support `--json` flag
- [x] Lock files now always contain PID
- [ ] CLAUDE.md updated with new commands (deferred)
