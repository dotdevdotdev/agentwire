---
name: machine-setup
description: Interactive guide for adding a new remote machine to AgentWire. Walks through SSH setup, dependencies, Claude auth, and portal registration.
---

# /machine-setup

Interactive wizard for adding a new remote machine to run Claude Code sessions with voice support.

## Usage

```
/machine-setup [machine-id] [ip-address]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `machine-id` | No | Short name for the machine (e.g., `gpu-1`, `do-2`) |
| `ip-address` | No | IP or hostname of the remote machine |

If not provided, the wizard will prompt for these values.

## Prerequisites

Before starting, ensure:
- You have root or sudo access to the remote machine
- The remote machine runs Ubuntu/Debian Linux
- You have an SSH key for authentication

## Setup Phases

The wizard guides you through these phases:

### Phase 1: SSH Access (Remote)

1. Create non-root user (Claude Code won't run as root)
2. Configure SSH key authentication
3. Add SSH config entry locally

### Phase 2: Dependencies (Remote)

Install on the remote machine:
- Node.js 22.x
- Python 3 + uv package manager
- tmux, git, curl, jq
- Claude Code (`npm install -g @anthropic-ai/claude-code`)

### Phase 3: GitHub Access (Remote)

For private repos, set up deploy keys:
- Generate SSH keys for each repo
- Add deploy keys via `gh repo deploy-key add`
- Configure SSH to use correct keys per repo

### Phase 4: Clone & Install (Remote)

- Clone agentwire repo
- Install in isolated venv
- Clone .claude config repo
- Clone project repos

### Phase 5: Authenticate Claude (Remote)

Interactive step - run `claude` and complete OAuth flow.

### Phase 6: Portal Registration (Local)

- Add machine to `~/.agentwire/machines.json`
- Start reverse tunnel with autossh
- Restart portal

### Phase 7: Voice Commands (Remote)

Install `say` script for TTS integration.

### Phase 8: Verification

Test the complete setup:
- SSH connectivity
- Portal visibility
- Voice command functionality

## Troubleshooting

Common issues the wizard helps resolve:

| Issue | Solution |
|-------|----------|
| Claude won't run | Running as root - create non-root user |
| Deploy key "already in use" | Each repo needs unique key per machine |
| Tunnel not connecting | Check portal is running, firewall rules |
| `say` command not found | Install voice scripts (Phase 7) |
| Portal doesn't show machine | Restart portal after registration |

## Example Session

```
You: /machine-setup

Claude: Let's set up a new remote machine for AgentWire.

What's the machine ID? (short name like 'gpu-1' or 'do-2')

You: do-2

Claude: What's the IP address or hostname?

You: 167.99.123.45

Claude: Do you have root SSH access to 167.99.123.45?

You: yes

Claude: Great! Let's start with Phase 1: SSH Access.

First, let's create a non-root user. SSH into the machine as root:
  ssh root@167.99.123.45

Then run these commands...
[continues with step-by-step guidance]
```

## CLI Alternative

For a quick add without the full wizard:

```bash
agentwire machine add <id> --host <host> --user <user> --projects-dir <path>
```

This just registers the machine. You'll still need to:
- Set up the remote machine manually
- Configure SSH and tunnels
- Install dependencies

## Related Skills

- `/machine-remove` - Remove a machine from AgentWire
- `/status` - Check all machines and their status
- `/sessions` - List sessions across all machines
