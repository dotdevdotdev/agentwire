# Mission: CLI-First Architecture

> Ensure portal and workers use `agentwire` CLI commands instead of direct tmux calls.

**Branch:** `mission/cli-first-architecture`

## Context

The CLI is the single source of truth for session management. Currently, some code bypasses the CLI and calls tmux directly. This creates:
- Duplicate logic (CLI and server both implement same operations)
- Inconsistent behavior (CLI might add features that direct calls miss)
- Harder testing (can't mock CLI calls as easily)

## Audit Results

### Acceptable Direct tmux (Low-Level PTY)

These are acceptable because they're tied to PTY/WebSocket handling:
- `tmux attach` - WebSocket terminal mode needs direct PTY control
- `tmux resize-window` - Part of SIGWINCH/PTY resize flow
- `tmux display-message` - Fast path lookup (could be CLI but acceptable)

### Should Use CLI

| File | Current | Should Use |
|------|---------|------------|
| `server.py` L2422-2439 | `tmux send-keys` for permission "2" | `agentwire send-keys` |
| `server.py` L2528-2551 | `tmux send-keys` for prompt responses | `agentwire send-keys` |
| `listen.py` L~50-60 | `tmux load-buffer/paste-buffer/send-keys` | `agentwire send` |
| `pane_manager.py` | Direct tmux for pane ops | Already has CLI: `spawn`, `send`, `kill`, `jump` |

### CLI Gaps

| Gap | Proposed Command |
|-----|------------------|
| Portal restart (kill + start) | `agentwire portal restart` |
| Get session working directory | `agentwire info -s <session>` (returns JSON with cwd, panes, etc.) |

---

## Wave 1: Human Actions

None required.

---

## Wave 2: CLI Enhancements

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Add `agentwire portal restart` command | `__main__.py` |
| 2.2 | Add `agentwire info -s <session>` - returns JSON with cwd, pane count, status | `__main__.py` |

---

## Wave 3: Refactor listen.py

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Replace `tmux load-buffer/paste-buffer/send-keys` with `agentwire send` | `listen.py` |
| 3.2 | Test voice input still works correctly | Browser test |

---

## Wave 4: Refactor server.py Permission Handling

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Replace `tmux send-keys` in `_handle_response()` with subprocess call to `agentwire send-keys` | `server.py` |
| 4.2 | Test permission flow (approve/deny/custom) via portal | Browser test |

---

## Wave 5: Refactor pane_manager.py

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Update `send_to_pane()` to use `agentwire send --pane` internally | `pane_manager.py` |
| 5.2 | Update `kill_pane()` to use `agentwire kill --pane` internally | `pane_manager.py` |
| 5.3 | Update `jump_to_pane()` to use `agentwire jump --pane` internally | `pane_manager.py` |
| 5.4 | Keep `spawn_worker_pane()` as-is (it's the implementation behind `agentwire spawn`) | - |

---

## Wave 6: Documentation & Cleanup

| Task | Description | Files |
|------|-------------|-------|
| 6.1 | Update CLAUDE.md to emphasize CLI-first principle | `CLAUDE.md` |
| 6.2 | Grep for remaining direct tmux calls, document any that are intentionally kept | - |
| 6.3 | Move SSH optimization mission content into this mission or complete it | `docs/missions/later/` |

---

## Completion Criteria

- [x] `listen.py` uses `agentwire send` for transcription input
- [x] `server.py` permission handling uses `agentwire send-keys`
- [x] `pane_manager.py` kept as-is (it's the CLI implementation layer, not external code)
- [x] `agentwire portal restart` command works
- [x] `agentwire info -s <session>` returns session metadata
- [x] Portal UI verified working
- [x] CLAUDE.md updated with new commands

---

## Technical Notes

### Why CLI Wrappers in pane_manager.py?

`pane_manager.py` is used by Claude Code skills and internal code. By making it call CLI commands internally:
- Skills get consistent behavior
- CLI can add features (logging, remote support) that propagate everywhere
- Testing can mock CLI calls

### Subprocess Pattern

```python
# Instead of:
subprocess.run(["tmux", "send-keys", "-t", target, text])

# Use:
subprocess.run(["agentwire", "send", "-s", session, "--pane", str(pane), text])
```

For async contexts in server.py:
```python
proc = await asyncio.create_subprocess_exec(
    "agentwire", "send-keys", "-s", session, keystroke,
    stdout=asyncio.subprocess.DEVNULL,
    stderr=asyncio.subprocess.DEVNULL,
)
await proc.wait()
```
