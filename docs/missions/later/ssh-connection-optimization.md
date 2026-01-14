# Mission: SSH Connection Optimization

> Help users enable SSH ControlMaster for faster remote session operations.

**Branch:** `mission/ssh-connection-optimization` (created on execution)

## Context

Each remote operation opens a new SSH connection (~400ms handshake). SSH ControlMaster reuses connections, reducing subsequent operations to ~50ms.

This is a standard SSH feature - we just need to help users discover and enable it.

---

## Wave 1: Human Actions (RUNTIME DEPENDENCY)

None required.

---

## Wave 2: Documentation

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Add SSH optimization section to installation docs | `docs/installation.md` |
| 2.2 | Mention optimization when documenting remote machines | `docs/installation.md` |

**Content to add:**

```markdown
## SSH Connection Optimization (Recommended)

When using remote machines, enable SSH ControlMaster for 5-8x faster operations:

mkdir -p ~/.ssh/sockets

Add to `~/.ssh/config`:

Host *
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600

This keeps SSH connections alive for 10 minutes, reusing them for subsequent commands.
```

---

## Wave 3: CLI Command

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Add `agentwire ssh-config check` - shows current status | `__main__.py` |
| 3.2 | Add `agentwire ssh-config install` - creates dir + adds config | `__main__.py` |
| 3.3 | Add `agentwire ssh-config remove` - removes config block | `__main__.py` |

**CLI behavior:**

```bash
$ agentwire ssh-config check
SSH ControlMaster: not configured
Run 'agentwire ssh-config install' for 5-8x faster remote operations.

$ agentwire ssh-config install
Created ~/.ssh/sockets/
Added ControlMaster config to ~/.ssh/config
SSH ControlMaster: enabled

$ agentwire ssh-config remove
Removed ControlMaster config from ~/.ssh/config
SSH ControlMaster: disabled
```

**Implementation notes:**
- `check`: Look for `ControlMaster` in `~/.ssh/config`, check if sockets dir exists
- `install`: Create sockets dir, append config block with comment markers
- `remove`: Remove config block between markers

**Config block format:**
```
# --- agentwire ssh optimization ---
Host *
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600
# --- end agentwire ---
```

---

## Completion Criteria

- [ ] Installation docs explain SSH optimization for remote machines
- [ ] `agentwire ssh-config check` shows current status
- [ ] `agentwire ssh-config install` enables ControlMaster
- [ ] `agentwire ssh-config remove` disables it cleanly
- [ ] CLAUDE.md updated with new command

---

## Technical Notes

### Why This Approach

- Zero code changes to tmux.py - SSH handles everything transparently
- User controls their SSH config (can customize per-host if needed)
- Benefits all SSH usage, not just AgentWire
