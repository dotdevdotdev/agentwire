---
name: machine-remove
description: Interactive guide for removing a machine from AgentWire. Handles portal cleanup, tunnels, SSH config, GitHub keys, and optionally destroys the VM.
---

# /machine-remove

Interactive wizard for removing a machine from the AgentWire network.

## Usage

```
/machine-remove [machine-id]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `machine-id` | No | ID of machine to remove (will prompt if not provided) |

## What Gets Removed

### Automatic (via CLI)

The `agentwire machine remove` command handles:
- Remove from `~/.agentwire/machines.json`
- Kill autossh tunnel process
- Clean up `~/.agentwire/sessions.json` entries

### Manual Steps (wizard guides through)

1. **SSH Config** - Remove entry from `~/.ssh/config`
2. **Tunnel Startup** - Remove from `~/.local/bin/agentwire-tunnels` if using
3. **GitHub Deploy Keys** - Delete keys for each repo
4. **Remote Machine** - Delete user or destroy VM

## Removal Levels

### Level 1: Disconnect Only

Just remove from AgentWire, keep the machine running:
- Run `agentwire machine remove <id>`
- Done - machine still exists but not in portal

### Level 2: Full Cleanup (Keep VM)

Remove from AgentWire and clean up authentication:
- Run `agentwire machine remove <id>`
- Remove SSH config entry
- Delete GitHub deploy keys
- (VM stays running for other uses)

### Level 3: Complete Destruction

Remove everything including the VM:
- All of Level 2
- SSH in and delete user: `userdel -r agentwire`
- Destroy VM via provider CLI or console

## Example Session

```
You: /machine-remove do-1

Claude: I'll help you remove machine 'do-1' from AgentWire.

First, let me run the CLI command to handle the automatic cleanup:
[runs: agentwire machine remove do-1]

Done. Removed from machines.json and killed the tunnel.

How thorough do you want the removal?

1. Disconnect only (done - machine still running)
2. Full cleanup (also remove SSH config + GitHub keys)
3. Complete destruction (also destroy the VM)

You: 3

Claude: Let's do a complete removal.

**Step 1: SSH Config**
Remove this block from ~/.ssh/config:
  Host do-1
    HostName 138.197.139.51
    User agentwire
    IdentityFile ~/.ssh/digitalocean

Want me to remove it?

You: yes

Claude: [removes SSH config entry]

**Step 2: GitHub Deploy Keys**
Let me check which repos have keys for 'do-1':
[runs: gh repo deploy-key list --repo user/repo]

Found 3 keys. Deleting...
[deletes keys]

**Step 3: Destroy VM**
Do you have doctl installed for DigitalOcean?

You: yes

Claude: [lists droplets, confirms, destroys]

Machine 'do-1' has been completely removed.
```

## CLI Alternative

For quick removal without the wizard:

```bash
# Just disconnect from AgentWire
agentwire machine remove <id>

# Then manually:
# 1. Edit ~/.ssh/config
# 2. gh repo deploy-key delete <id> --repo <repo>
# 3. Destroy VM via provider console
```

## Provider-Specific Destruction

### DigitalOcean

```bash
doctl compute droplet list
doctl compute droplet delete <id> --force
```

### AWS EC2

```bash
aws ec2 describe-instances --filters "Name=tag:Name,Values=<name>"
aws ec2 terminate-instances --instance-ids <id>
```

### Manual (Any Provider)

1. Log into provider console
2. Find the instance
3. Terminate/destroy it

## Checklist

The wizard ensures all these are handled:

- [ ] Tunnel stopped
- [ ] Removed from machines.json
- [ ] Session configs cleaned
- [ ] SSH config entry removed
- [ ] GitHub deploy keys deleted
- [ ] Remote machine destroyed (if requested)

## Related Skills

- `/machine-setup` - Add a new machine
- `/status` - Check machine status
- `/sessions` - List sessions (verify none running on machine)
