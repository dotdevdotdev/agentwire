# Remote SSH Session Management Research

Research on improving AgentWire's remote session management via SSH.

## Current Implementation

AgentWire currently uses **per-command SSH invocations**:

```python
# From agentwire/agents/tmux.py
def _run_remote(self, machine: dict, cmd: str, ...):
    ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", ...]
    ssh_cmd.extend([ssh_target, cmd])
    return subprocess.run(ssh_cmd, ...)
```

Each operation (create_session, get_output, send_input, etc.) opens a new SSH connection.

## Problems with Current Approach

| Issue | Impact |
|-------|--------|
| **Latency** | ~400ms per command due to SSH handshake |
| **Reliability** | Connection failures compound (87% cumulative failure rate over 100 ops) |
| **Resource overhead** | Each SSH spawns new process, auth, connection |

Reference: [Claude Code Issue #13613](https://github.com/anthropics/claude-code/issues/13613) quantified these issues.

## Alternative Approaches

### 1. SSH ControlMaster (Connection Multiplexing)

Reuse a single SSH connection for multiple commands.

```bash
# ~/.ssh/config
Host *
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600
```

**Pros:**
- Drop-in improvement (no code changes, just SSH config)
- Eliminates handshake latency after first connection
- Works with existing subprocess approach

**Cons:**
- Socket management complexity (stale sockets, cleanup)
- No session persistence (connection drops = all commands fail)
- Still per-command subprocess overhead

**Verdict:** Quick win, but doesn't solve persistence.

### 2. Persistent SSH + Remote tmux (Current Architecture)

AgentWire already creates tmux sessions on remote machines. The issue is how we communicate with them.

**Current:** `ssh remote "tmux send-keys ..."` per command
**Better:** Single SSH connection held open, commands piped through

**Implementation options:**

#### 2a. SSH with stdin pipeline

```python
# Hold SSH connection open, pipe commands
proc = subprocess.Popen(
    ["ssh", host, "bash"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
# Send commands through stdin
proc.stdin.write(b"tmux send-keys -t session 'hello' Enter\n")
proc.stdin.flush()
```

**Pros:** Low latency after connection established
**Cons:** Blocking I/O, complex output parsing, error handling

#### 2b. SSH with tmux control mode on remote

```bash
ssh remote "tmux -CC attach -t session"
```

Control mode provides structured output but adds complexity.

**Pros:** Structured protocol, async notifications
**Cons:** 850ms latency (vs 220ms normal mode), parsing complexity

### 3. Local tmux + SSH tunnel (Reference Implementation)

From Claude Code feature request - run tmux locally, SSH to remote inside it:

```python
# Create LOCAL tmux session
subprocess.run(['tmux', 'new-session', '-d', '-s', 'remote-work'])
# SSH to remote WITHIN that session
subprocess.run(['tmux', 'send-keys', '-t', 'remote-work', 'ssh remote', 'Enter'])
# Commands go to local tmux, which forwards to remote shell
subprocess.run(['tmux', 'send-keys', '-t', 'remote-work', 'ls -la', 'Enter'])
```

**Pros:**
- Single SSH connection (persistent)
- Local tmux handles all command/output
- Detach/reattach survives network issues
- Works with any SSH host

**Cons:**
- Session state confusion (local tmux vs remote tmux)
- Can't leverage remote tmux features
- Adds complexity when you actually want remote tmux sessions

**Verdict:** Good for "run commands on remote", not for "manage remote tmux sessions".

## Recommendation for AgentWire

AgentWire's use case is **managing remote tmux sessions** (not just running remote commands). The best approach:

### Hybrid: ControlMaster + Batched Operations

1. **Enable SSH ControlMaster** system-wide or per-machine
2. **Batch related operations** where possible (e.g., create + send-keys in single SSH)
3. **Add connection health checks** with automatic reconnection

This preserves the current architecture while reducing latency.

### Implementation Changes

```python
# Already doing batching for create_session on remote:
cmd = (
    f"tmux new-session -d -s {session_name} -c {path} && "
    f"tmux send-keys -t {session_name} {agent_cmd} Enter"
)

# Could extend to other operations:
# - get_output + session_exists in single call
# - Health check with fallback
```

### ControlMaster Setup Helper

AgentWire could provide a setup command:

```bash
agentwire setup ssh-multiplexing
# Creates ~/.ssh/sockets directory
# Adds ControlMaster config (with user confirmation)
```

## Performance Expectations

| Metric | Current | With ControlMaster | Improvement |
|--------|---------|-------------------|-------------|
| First command | 400ms | 400ms | - |
| Subsequent commands | 400ms | 50-80ms | 5-8x |
| 100 commands | 40s | ~8s | 5x |

## Open Questions

1. Should AgentWire auto-detect/suggest ControlMaster config?
2. Worth adding connection pooling in Python (vs relying on SSH)?
3. Is "local tmux + SSH inside" pattern worth supporting as alternative mode?

## Sources

- [Claude Code #13613 - Remote Session Management](https://github.com/anthropics/claude-code/issues/13613)
- [tmux-remote-sessions plugin](https://github.com/tomhey/tmux-remote-sessions)
- [SSH ControlMaster docs](https://en.wikibooks.org/wiki/OpenSSH/Cookbook/Multiplexing)
