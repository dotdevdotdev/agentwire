# Mission: Digital Ocean Droplet Network Test

> Test multi-machine networking by adding a small DO droplet to the AgentWire network.

## Objective

Create a minimal Digital Ocean droplet, configure it as an AgentWire worker machine, and verify the full network stack works (SSH, tunnels, sessions, voice).

## Wave 1: Human Actions (BLOCKING)

- [ ] Create DO droplet (smallest size, Ubuntu 24.04)
- [ ] Note the droplet IP address
- [ ] Add SSH key to droplet (or use existing DO SSH key)
- [ ] Verify SSH access: `ssh root@<droplet-ip>`

## Wave 2: Droplet Setup

### 2.1 Install dependencies on droplet
- Install Node.js (for Claude Code)
- Install uv (Python package manager)
- Install tmux
- Create non-root user if needed

### 2.2 Install Claude Code on droplet
- Install Claude Code CLI
- Authenticate with Anthropic (may need API key or OAuth)

### 2.3 Install AgentWire on droplet
- Clone agentwire repo
- Install via uv tool

## Wave 3: Network Integration

### 3.1 Add droplet to portal machine list
- Use `agentwire machine add` on jordans-mini
- Or use portal UI to add machine

### 3.2 Run init wizard on droplet
- SSH to droplet
- Run `agentwire init`
- Select "Worker" role
- Point to jordans-mini as portal host

### 3.3 Verify tunnel creation
- Check `agentwire doctor` on droplet
- Verify portal reachable via tunnel

## Wave 4: Integration Testing

### 4.1 Test session creation from portal
- Create session on droplet from portal UI
- Verify session appears in `agentwire list`

### 4.2 Test voice commands
- Send voice command to droplet session
- Verify `remote-say` works from droplet back to portal

### 4.3 Test network status
- Run `agentwire network status` from both machines
- Verify all services show as healthy

## Completion Criteria

- [ ] Droplet appears in `agentwire machine list` on portal
- [ ] `agentwire doctor` passes on droplet
- [ ] Can create/kill sessions on droplet from portal
- [ ] Voice input/output works to droplet sessions
- [ ] `agentwire network status` shows healthy on both machines

## Notes

- Use smallest droplet size ($4-6/month) - just needs to run Claude Code
- Can destroy droplet after testing to avoid ongoing costs
- This validates the init wizard's remote setup feature
- Good test of cross-network (not just LAN) connectivity
