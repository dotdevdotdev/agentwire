# libtmux Evaluation

**Verdict:** NOT RECOMMENDED - No mission created.

**Reason:** libtmux doesn't support remote sessions (local only), pre-1.0 API instability, and marginal benefit for added dependency. Current subprocess approach works well for both local and remote.

---

Research on migrating AgentWire from subprocess tmux calls to libtmux Python library.

## Current Implementation

AgentWire uses direct subprocess calls:

```python
# From agentwire/agents/tmux.py
def _run_local(self, cmd: list[str], ...):
    return subprocess.run(cmd, capture_output=capture, text=True)

# Usage
result = self._run_local(["tmux", "new-session", "-d", "-s", name, "-c", str(path)])
```

## libtmux Overview

[libtmux](https://github.com/tmux-python/libtmux) provides typed Python bindings for tmux.

```python
import libtmux

server = libtmux.Server()
session = server.new_session(session_name="work", start_directory="/path")
window = session.active_window
pane = window.active_pane

pane.send_keys("echo hello", enter=True)
output = pane.capture_pane()
```

## Feature Comparison

| Feature | subprocess | libtmux |
|---------|------------|---------|
| Session management | Manual parsing | Object-oriented |
| Type hints | None | Full typing |
| Error handling | Return codes | Exceptions |
| Output capture | Manual `-p` flag | `.capture_pane()` |
| Wait for output | Manual polling | Built-in patterns* |
| Remote sessions | Supported (SSH) | Local only |
| Dependencies | None (stdlib) | libtmux package |
| API stability | tmux CLI stable | Pre-1.0, may change |

*libtmux docs mention wait patterns but details are sparse.

## Pros of libtmux

### 1. Cleaner API

```python
# Current (subprocess)
result = subprocess.run(["tmux", "has-session", "-t", name], capture_output=True)
exists = result.returncode == 0

# libtmux
exists = server.sessions.filter(session_name=name).count() > 0
```

### 2. Type Safety

```python
# Typed objects with IDE completion
session: libtmux.Session = server.sessions.get(session_name="work")
pane: libtmux.Pane = session.active_window.active_pane
```

### 3. Escape Hatch

When needed, can still run raw tmux commands:

```python
# Falls back to subprocess internally, but handles socket config
session.cmd('split-window', '-h')
```

### 4. Test Fixtures

libtmux provides pytest fixtures for testing:

```python
def test_my_feature(session):  # Auto-created, auto-cleaned
    pane = session.active_window.active_pane
    pane.send_keys("echo test")
    # ...
```

## Cons of libtmux

### 1. No Remote Support

libtmux only talks to local tmux server. AgentWire's remote session support would need to stay as subprocess:

```python
# Can't do this with libtmux
ssh remote "tmux send-keys -t session 'hello' Enter"
```

This is a **major limitation** - we'd need dual codepaths.

### 2. Pre-1.0 API Instability

From docs: "libtmux is pre-1.0 and APIs will be changing throughout 2026"

Would need to pin version carefully and track breaking changes.

### 3. Learning Curve / Inconsistency

Some operations are non-obvious:

```python
# User feedback from GitHub issues:
# "When I use the library to split window, I use win.cmd('split-window', '-h')
#  which let me spend a lot of time. At last, I suggest to use bash script instead"
```

### 4. Additional Dependency

Currently AgentWire has minimal dependencies. Adding libtmux:
- Adds transitive deps
- Potential version conflicts
- More to maintain

### 5. tmux Version Requirement

libtmux requires tmux 3.2a or newer. Current subprocess approach works with any tmux version.

## Impact Analysis for AgentWire

| Component | Current | With libtmux | Complexity |
|-----------|---------|--------------|------------|
| Local sessions | subprocess | libtmux | Simpler |
| Remote sessions | subprocess via SSH | Still subprocess | No change |
| Output capture | capture-pane | pane.capture_pane() | Simpler |
| Error handling | returncode checks | try/except | Cleaner |
| Testing | Manual setup | pytest fixtures | Better |

**Net assessment:** Marginal improvement for local, no improvement for remote, adds dependency.

## Recommendation

### Don't Migrate to libtmux

**Reasons:**

1. **Remote sessions are a first-class feature** - libtmux doesn't help here
2. **Current code is simple** - subprocess calls are readable and work
3. **Dependency cost** - adds maintenance burden for marginal benefit
4. **API instability** - pre-1.0 means tracking breaking changes

### Consider libtmux For:

1. **Testing utilities** - use libtmux fixtures in tests even if production uses subprocess
2. **Future local-only features** - if we add features that only need local tmux

### Better Investments

Instead of libtmux migration, invest in:

1. **SSH ControlMaster** for remote performance
2. **Better error messages** in current subprocess code
3. **Integration tests** using libtmux fixtures (but keep production code as subprocess)

## Code Comparison

### Session Creation

```python
# Current (works local + remote)
if machine:
    cmd = f"tmux new-session -d -s {name} -c {path}"
    self._run_remote(machine, cmd)
else:
    subprocess.run(["tmux", "new-session", "-d", "-s", name, "-c", str(path)])

# With libtmux (local only)
server = libtmux.Server()
session = server.new_session(session_name=name, start_directory=str(path))
# Remote would still need subprocess
```

### Output Capture

```python
# Current
result = subprocess.run(
    ["tmux", "capture-pane", "-t", name, "-p", "-e", "-S", f"-{lines}"],
    capture_output=True, text=True
)
return result.stdout

# With libtmux
session = server.sessions.get(session_name=name)
return session.active_window.active_pane.capture_pane()
```

The libtmux version is cleaner but only works locally.

## Sources

- [libtmux GitHub](https://github.com/tmux-python/libtmux)
- [libtmux Documentation](https://libtmux.git-pull.com/)
- [libtmux Quickstart](https://libtmux.git-pull.com/quickstart.html)
- [libtmux Issue #170](https://github.com/tmux-python/libtmux/issues/170) - User feedback
