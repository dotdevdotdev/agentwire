# tmux Programmatic Management Research

Research on tmux session/window/pane commands for AgentWire CLI.

## Target Syntax

| Format | Example | Description |
|--------|---------|-------------|
| `session:window.pane` | `dev:0.1` | Full specification |
| `:window.pane` | `:2.1` | Current session |
| `.pane` | `.1` | Current session/window |
| Unique IDs | `$3`, `@1`, `%0` | Session/window/pane IDs (stable across renames) |

**IDs vs names:** Unique IDs (`$`, `@`, `%` prefixed) are stable even after rename/move - useful for long-running automation.

## Key Gotchas

### 1. Race condition on session/pane creation

`send-keys` immediately after `new-session`/`split-window` may fail because the shell isn't ready yet.

**Fix:** Add `sleep 0.4` between creation and send-keys.

Reference: [tmux/tmux#1778](https://github.com/tmux/tmux/issues/1778)

### 2. Quoting is critical

Unquoted `$@` in wrapper scripts strips spaces from arguments. Always use `"$@"` when passing through to tmux.

Reference: [tmux/tmux#1425](https://github.com/tmux/tmux/issues/1425)

### 3. capture-pane limitations

- Only captures up to `history-limit` lines (set in `.tmux.conf`)
- Use `-p -S -` for full history to stdout
- `-e` preserves ANSI codes (may need `ansifilter` to clean)

### 4. Session naming restrictions

- **No dots in session names** - tmux uses `.` as delimiter between windows/panes
- Characters like `:` also reserved

Reference: [tmuxinator docs](https://github.com/tmuxinator/tmuxinator)

## Useful Commands

```bash
# Create session (detached, in directory)
tmux new-session -d -s name -c /path/to/dir

# Send command (with delay for new sessions)
sleep 0.4 && tmux send-keys -t name "command" Enter

# Capture output (full history, strip ANSI)
tmux capture-pane -t name -p -S - | ansifilter

# Get pane dimensions
tmux display -t name -p '#{pane_width}x#{pane_height}'

# Check if session exists
tmux has-session -t name 2>/dev/null

# List sessions (parseable format)
tmux list-sessions -F '#{session_name}:#{session_id}'
```

## Windows/Panes vs Sessions

| Approach | Pros | Cons |
|----------|------|------|
| **Separate sessions** | Clean isolation, easy naming, `tmux kill-session` | More overhead, no shared clipboard |
| **Windows in one session** | Shared buffers, less overhead | Name collisions, harder targeting |
| **Panes** | Visible together | Layout complexity, harder programmatic control |

**For AgentWire:** Current session-per-agent approach is correct - clean isolation, straightforward targeting (`-t session_name`), easy lifecycle management.

## Python Libraries

- **[libtmux](https://libtmux.git-pull.com/)** - Direct Python bindings, good for pane polling/waiting
- **[tmuxp](https://github.com/tmux-python/tmuxp)** - Session manager built on libtmux, YAML configs

## Sources

- [tmux Advanced Use Wiki](https://github.com/tmux/tmux/wiki/Advanced-Use)
- [libtmux Pane Interaction](https://libtmux.git-pull.com/topics/pane_interaction.html)
- [Baeldung tmux Logging](https://www.baeldung.com/linux/tmux-logging)
- [tmux-logging plugin](https://github.com/tmux-plugins/tmux-logging)
- [tmux man page](https://man7.org/linux/man-pages/man1/tmux.1.html)
