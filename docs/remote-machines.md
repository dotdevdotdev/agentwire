# Remote Machine Management

> Living document. Update this, don't create new versions.

AgentWire can manage Claude Code sessions on remote machines via SSH. This guide covers adding, removing, and configuring remote machines.

---

## Adding a Machine

### Interactive Wizard (Recommended)

Use the `/machine-setup` skill for guided setup:

```
/machine-setup do-2 167.99.123.45
```

The wizard walks through:
- SSH access configuration
- Dependency installation (tmux, Node.js, Claude CLI)
- GitHub SSH key setup
- Claude Code authentication
- Portal registration
- Tunnel configuration
- Voice command testing

### Quick Add (Portal Only)

Skip the wizard and add directly:

```bash
agentwire machine add <id> --host <host> --user <user> --projects-dir <path>
```

Example:

```bash
agentwire machine add gpu-server --host 192.168.1.50 --user ubuntu --projects-dir ~/projects
```

### Portal UI

Dashboard → Machines → Add Machine

Fill in:
- **Machine ID** - Short identifier (e.g., `gpu-server`, `do-2`)
- **Host** - IP address or hostname
- **User** - SSH username
- **Projects Directory** - Where projects live on the remote machine

---

## Removing a Machine

### Interactive Wizard (Recommended)

Use the `/machine-remove` skill for guided removal:

```
/machine-remove do-1
```

The wizard offers cleanup levels:

| Level | Actions |
|-------|---------|
| **Disconnect only** | Remove from portal, kill tunnel |
| **Full cleanup** | + Remove SSH config entry + revoke GitHub deploy keys |
| **Complete destruction** | + Destroy the VM (DigitalOcean, etc.) |

### Quick Remove (Portal-Side Only)

```bash
agentwire machine remove <id>
```

This:
- Removes from `machines.json`
- Kills active SSH tunnel
- Cleans entries from `rooms.json`
- Prints reminders for manual cleanup

### Portal UI

Dashboard → Machines → Click ✕ button on machine card

---

## Machine CLI Commands

```bash
# List all machines with connection status
agentwire machine list

# Add a machine
agentwire machine add <id> --host <host> --user <user> --projects-dir <path>

# Remove a machine (portal-side cleanup)
agentwire machine remove <id>
```

### Machine List Output

```
MACHINES:
  gpu-server: ubuntu@192.168.1.50 (~/projects) - online
  do-2: root@167.99.123.45 (~/projects) - offline
```

---

## Session Operations on Remote Machines

All session commands support the `session@machine` format:

```bash
# Create session on remote machine
agentwire new -s myproject@gpu-server

# Create worktree session on remote
agentwire new -s myproject/feature@gpu-server

# Send prompt to remote session
agentwire send -s myproject@gpu-server "run the tests"

# Read output from remote session
agentwire output -s myproject@gpu-server -n 100

# Kill remote session
agentwire kill -s myproject@gpu-server

# List all sessions (includes remote)
agentwire list
```

---

## Minimum Specs (Remote)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 1GB | 2GB+ |
| Storage | 10GB | 20GB+ |
| CPU | 1 vCPU | 2+ vCPU |

**Note:** The LLM runs on Anthropic's servers - remote machines only need resources for Node.js and file operations. No GPU required for Claude Code sessions (GPU only needed for TTS with Chatterbox).

---

## SSH Configuration

AgentWire uses your existing SSH configuration. Ensure you can connect:

```bash
ssh <machine-id>  # Should connect without password prompt
```

For passwordless access, add your SSH key:

```bash
ssh-copy-id user@host
```

Or add to `~/.ssh/config`:

```
Host gpu-server
    HostName 192.168.1.50
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
```

**Tip:** Enable SSH ControlMaster for faster remote operations (reuses connections instead of opening new ones each time). Add to `~/.ssh/config`:

```
Host *
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600
```

---

## machines.json Schema

Machine configuration is stored in `~/.agentwire/machines.json`:

```json
[
  {
    "id": "gpu-server",
    "host": "192.168.1.50",
    "user": "ubuntu",
    "projects_dir": "~/projects"
  },
  {
    "id": "do-2",
    "host": "167.99.123.45",
    "user": "root",
    "projects_dir": "~/projects"
  }
]
```

| Field | Description |
|-------|-------------|
| `id` | Unique identifier, used in `session@machine` format |
| `host` | IP address or hostname |
| `user` | SSH username |
| `projects_dir` | Base directory for projects on the remote machine |
