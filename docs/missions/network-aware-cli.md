# Mission: Network-Aware CLI

> Make AgentWire CLI work identically from any machine in the network, with guided onboarding for new users.

## Problem Statement

**For existing users:** CLI commands assume they run on the same machine as the services they control. After a reboot, we had to manually:
1. SSH into dotdev-pc to start TTS
2. Manually create SSH tunnel (`ssh -f -N -L 8100:localhost:8100 dotdev-pc`)
3. Know which machine runs what

**For new users:** No guided setup experience. Users must manually create config files, understand the architecture, and figure out multi-machine setup on their own.

**Goals:**
1. Any CLI command works from any machine (location transparency)
2. New users get a guided wizard that walks them through setup
3. The system adapts to their setup: single machine, multi-machine, or team

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AgentWire Network                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │ Portal Machine  │    │  TTS Machine    │    │ Dev Machine │ │
│  │ (lightweight)   │    │  (GPU)          │    │ (workers)   │ │
│  │                 │    │                 │    │             │ │
│  │ • Portal :8765  │◄───│ • TTS :8100     │    │ • Workers   │ │
│  │ • CLI works ✓   │    │ • CLI works ✓   │    │ • CLI works✓│ │
│  │                 │◄───┼─────────────────┼────│             │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│         ▲                                            │         │
│         │              Portal URL                    │         │
│         └────────────────────────────────────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Tunnel Requirements:
• Portal machine → TTS machine (for voice synthesis)
• Worker machines → Portal machine (for remote-say)
```

## Design Principles

### 1. Config is the Source of Truth

Every machine in the network has the same `~/.agentwire/config.yaml` with a `services` section declaring where each service runs.

### 2. Location Transparency

`agentwire portal status` works identically whether you're on the portal machine or SSH'd into a worker. The CLI figures out routing.

### 3. Fail Loudly with Actionable Errors

When something goes wrong, tell the user:
- **WHAT** failed (specific error)
- **WHY** it matters (context)
- **HOW** to fix it (concrete steps)
- **DIAGNOSTIC** commands to run

### 4. Tunnels are Implementation Details

Users shouldn't think about tunnels. `agentwire tunnels up` creates whatever's needed based on config. Services "just work" after that.

---

## Config Schema

### services section (NEW)

```yaml
# ~/.agentwire/config.yaml

services:
  portal:
    machine: null          # null = this machine, or machine ID from machines.json
    port: 8765
    health_endpoint: "/health"

  tts:
    machine: "dotdev-pc"   # TTS runs on GPU machine
    port: 8100
    health_endpoint: "/health"
```

### Validation Rules

| Rule | Error if violated |
|------|-------------------|
| `machine` must be null or exist in machines.json | "Unknown machine 'foo'. Add it with: agentwire machine add foo --host ..." |
| `port` must be 1-65535 | "Invalid port {port}. Must be between 1 and 65535" |
| Cannot have circular tunnel dependencies | "Circular dependency detected: portal→tts→portal" |
| machines.json must be readable | "Cannot read machines.json: {error}. Run: agentwire init" |

---

## Onboarding Flow

New users experience a two-phase setup:

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: CLI Wizard (agentwire init)                          │
│  ─────────────────────────────────────────────────────────────  │
│  • Config directory setup (~/.agentwire/)                       │
│  • SSL certificates (self-signed for HTTPS portal)              │
│  • Audio device selection (list mics, pick one)                 │
│  • Projects directory (where are your projects?)                │
│  • Detects existing config → offers merge/replace/skip          │
│                                                                 │
│  End: "Ready to start orchestrator setup? (y/n)"                │
│       If yes → spawns orchestrator session with init prompt     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Orchestrator Init Session                             │
│  ─────────────────────────────────────────────────────────────  │
│  Claude walks user through advanced setup via conversation:     │
│                                                                 │
│  • "Are you setting up just this machine, or multiple?"         │
│  • "Where will TTS run? (this machine / remote GPU / skip)"     │
│  • "Let's add your GPU machine to the network..."               │
│  • "Testing connectivity... ✓ SSH works, ✓ TTS responds"        │
│                                                                 │
│  Uses AskUserQuestion for structured choices                    │
│  Runs agentwire CLI commands to configure                       │
│  Tests everything works before declaring success                │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles for Onboarding

1. **Idempotent** - Safe to run `agentwire init` multiple times. Detects existing config and offers choices.

2. **Adaptive** - Asks questions to determine user's situation, skips irrelevant steps.

3. **Fail-safe** - If orchestrator setup fails, user still has working local setup from Phase 1.

4. **Educational** - Explains what each step does and why, so users understand their system.

---

## Wave 0: Init & Onboarding

### 0.1 CLI Init Wizard

**File:** `agentwire/__main__.py` - enhance `cmd_init`

Guided wizard that walks through local setup:

```python
def cmd_init(args) -> int:
    """Interactive setup wizard for AgentWire."""

    print("Welcome to AgentWire Setup")
    print("=" * 50)

    # Step 1: Config directory
    config_dir = Path.home() / ".agentwire"
    if config_dir.exists():
        choice = prompt_choice(
            "Config directory exists. What would you like to do?",
            ["Keep existing config", "Start fresh (backup old)", "Cancel"]
        )
        if choice == "Cancel":
            return 0
        if choice == "Start fresh (backup old)":
            backup_and_reset(config_dir)
    else:
        config_dir.mkdir(parents=True)
        print(f"✓ Created {config_dir}")

    # Step 2: SSL certificates
    # Step 3: Audio device
    # Step 4: Projects directory
    # Step 5: Generate config.yaml

    # Final: Offer orchestrator setup
    if prompt_yes_no("Ready to start orchestrator setup?"):
        return spawn_init_orchestrator()

    print("\nLocal setup complete!")
    print("Run 'agentwire dev' to start the orchestrator when ready.")
    return 0
```

**Wizard Steps:**

| Step | Prompt | Default | Notes |
|------|--------|---------|-------|
| Config dir | "Config directory exists. What to do?" | Keep existing | Only if exists |
| SSL certs | "Generate SSL certificates for HTTPS portal?" | Yes | Skip if exist |
| Audio device | "Select your microphone:" (list) | System default | Show device names |
| Projects dir | "Where are your projects?" | ~/projects | Validate exists |
| Orchestrator | "Ready to start orchestrator setup?" | Yes | Spawns Phase 2 |

**Acceptance criteria:**
- [ ] Detects existing config, offers merge/replace/skip
- [ ] Each step explains what it does
- [ ] Can be cancelled at any point
- [ ] Works without network (local-only setup)
- [ ] Generates valid config.yaml

### 0.2 Orchestrator Init Prompt

**File:** `~/.agentwire/prompts/init.md` (template, copied during install)

When the orchestrator spawns in init mode, it receives this prompt:

```markdown
# AgentWire Init Session

You are helping a user set up AgentWire for the first time. The CLI wizard has already completed local setup (config directory, SSL certs, audio device, projects directory).

Your job is to walk them through advanced setup:

## Your Tasks

1. **Understand their setup**
   - Ask if they're using just this machine, or multiple machines
   - Ask about TTS: local (if GPU), remote GPU machine, or skip voice

2. **Configure services** (based on their answers)
   - For single machine: ensure services.portal and services.tts are both null (local)
   - For multi-machine: help them add machines and configure service locations

3. **Add remote machines** (if multi-machine)
   - For each machine: get hostname/IP, SSH user, projects directory
   - Run `agentwire machine add` for each
   - Test SSH connectivity

4. **Configure TTS location**
   - If TTS on remote GPU: update config.yaml services.tts.machine
   - Verify TTS dependencies are installed on that machine

5. **Test everything**
   - Run `agentwire tunnels up` to create needed tunnels
   - Run `agentwire network status` to verify all services
   - Run `agentwire tts status` and `agentwire portal status`

6. **Start services**
   - Start TTS if remote
   - Start portal
   - Test voice with a quick `remote-say "Setup complete!"`

## Guidelines

- Use AskUserQuestion for choices (single vs multi, TTS location, etc.)
- Run CLI commands to actually configure things, don't just tell the user to do it
- If something fails, explain what went wrong and offer to retry or skip
- Be encouraging - this is their first time!

## Example Flow

You: "Let's finish setting up AgentWire! First, tell me about your setup."
[AskUserQuestion: "What kind of setup do you have?"
  - "Just this machine (simple)"
  - "Multiple machines (e.g., separate GPU for TTS)"
  - "I'm not sure yet, help me decide"]

[If multi-machine selected]
You: "Great! Let's add your other machines. Do you have a machine with a GPU for TTS?"
[AskUserQuestion: "Where will TTS (voice synthesis) run?"
  - "This machine has a GPU"
  - "I have a separate GPU machine"
  - "Skip voice features for now"]

... continue based on answers ...
```

**Acceptance criteria:**
- [ ] Prompt is comprehensive but not overwhelming
- [ ] Uses AskUserQuestion for all choices
- [ ] Handles all three personas (single, multi, team)
- [ ] Actually runs commands (not just instructions)
- [ ] Tests everything before declaring success

### 0.3 Spawn Init Orchestrator

**File:** `agentwire/__main__.py`

After CLI wizard, spawn orchestrator with init prompt:

```python
def spawn_init_orchestrator() -> int:
    """Spawn orchestrator session with init instructions."""

    # Create the orchestrator session
    session_name = "agentwire"
    if tmux_session_exists(session_name):
        print(f"Orchestrator session '{session_name}' already exists.")
        choice = prompt_choice(
            "What would you like to do?",
            ["Attach to existing", "Kill and restart", "Cancel"]
        )
        if choice == "Cancel":
            return 0
        if choice == "Kill and restart":
            subprocess.run(["tmux", "kill-session", "-t", session_name])

    # Start fresh session
    print(f"\nStarting orchestrator session...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
        "-c", str(Path.home() / "projects" / "agentwire"),
    ])

    # Start Claude in the session
    subprocess.run([
        "tmux", "send-keys", "-t", session_name,
        "claude --dangerously-skip-permissions", "Enter"
    ])

    # Wait for Claude to start
    time.sleep(3)

    # Send the init prompt
    init_prompt = load_init_prompt()
    send_to_session(session_name, init_prompt)

    print(f"\n✓ Orchestrator started with init instructions")
    print(f"\nAttaching to session... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])

    return 0
```

**Acceptance criteria:**
- [ ] Creates orchestrator session correctly
- [ ] Waits for Claude to be ready before sending prompt
- [ ] Sends init prompt via `agentwire send`
- [ ] Attaches user to the session
- [ ] Handles existing session gracefully

### 0.4 Init Prompt Questions (AskUserQuestion)

The orchestrator init session should use these structured questions:

**Q1: Setup Type**
```
Question: "What kind of setup do you have?"
Options:
  - "Just this machine" → Skip to single-machine config
  - "Multiple machines" → Continue to machine setup
  - "Help me decide" → Explain trade-offs, then re-ask
```

**Q2: TTS Location**
```
Question: "Where should voice synthesis (TTS) run?"
Options:
  - "This machine (requires NVIDIA GPU)"
  - "A separate GPU machine (I'll provide details)"
  - "Skip voice features for now"
```

**Q3: Add Machine (repeated)**
```
Question: "What type of machine is this?"
Options:
  - "GPU server (for TTS)"
  - "Worker machine (for Claude sessions)"
  - "Portal host (lightweight, serves web UI)"
  - "All-in-one (does everything)"
```

**Q4: Machine Details (text input)**
```
Question: "What's the hostname or IP for this machine?"
Type: text input

Question: "What's the SSH username?"
Type: text input (default: same as current user)

Question: "Where are projects stored on this machine?"
Type: text input (default: ~/projects)
```

**Q5: Verification**
```
Question: "I've configured your network. Ready to test everything?"
Options:
  - "Yes, run tests"
  - "Show me the config first"
  - "Let me make changes first"
```

**Acceptance criteria:**
- [ ] All critical decisions use AskUserQuestion
- [ ] Options cover all realistic scenarios
- [ ] "Help me decide" options explain trade-offs
- [ ] Text inputs have sensible defaults

---

## Wave 1: Human Actions (RUNTIME BLOCKING)

These must be completed before testing, but agents can write code immediately.

- [ ] **1.1** Ensure all machines have SSH access to each other
  - Test: `ssh dotdev-pc "echo ok"` from each machine
  - Add SSH keys if needed

- [ ] **1.2** Sync config files across machines
  - Same `~/.agentwire/config.yaml` on all machines
  - Same `~/.agentwire/machines.json` on all machines
  - Consider: symlink to shared location? git repo? manual sync?

---

## Wave 2: Config & Validation Foundation

### 2.1 Config Schema Extension

**File:** `agentwire/config.py`

Add `services` section to config schema:

```python
@dataclass
class ServiceConfig:
    machine: Optional[str]  # None = local, or machine ID
    port: int
    health_endpoint: str = "/health"

@dataclass
class ServicesConfig:
    portal: ServiceConfig
    tts: ServiceConfig
```

**Acceptance criteria:**
- [ ] `load_config()` parses `services` section
- [ ] Missing `services` section uses sensible defaults (all local)
- [ ] Invalid config raises clear `ConfigError` with fix instructions

### 2.2 Config Validator

**File:** `agentwire/validation.py` (NEW)

Create comprehensive config validation:

```python
def validate_config(config: dict) -> list[ConfigWarning | ConfigError]:
    """
    Validate config and return issues.

    Checks:
    - services.*.machine references exist in machines.json
    - ports are valid
    - no circular dependencies
    - machines are reachable (optional, slow)
    """
```

**Error message format:**
```
ERROR: Unknown machine 'gpu-server' in services.tts.machine

The TTS service is configured to run on 'gpu-server', but this machine
is not registered in ~/.agentwire/machines.json.

To fix, either:
  1. Add the machine:    agentwire machine add gpu-server --host 192.168.1.50
  2. Fix the config:     Edit ~/.agentwire/config.yaml services.tts.machine

To see registered machines: agentwire machine list
```

**Acceptance criteria:**
- [ ] All validation errors include WHAT/WHY/HOW
- [ ] `agentwire config validate` command runs all checks
- [ ] Validation runs automatically on CLI startup (with caching)

### 2.3 Network Context Helper

**File:** `agentwire/network.py` (NEW)

Core helper for determining "where am I" and "how do I reach X":

```python
class NetworkContext:
    """Understands the network topology and how to reach services."""

    def __init__(self, config: Config, machines: list[Machine]):
        self.config = config
        self.machines = {m.id: m for m in machines}
        self.local_machine_id = self._detect_local_machine()

    def is_local(self, service: str) -> bool:
        """Is this service running on the current machine?"""

    def get_service_url(self, service: str) -> str:
        """Get URL to reach service (via tunnel or direct)."""

    def get_required_tunnels(self) -> list[TunnelSpec]:
        """What tunnels does THIS machine need?"""

    def get_ssh_target(self, service: str) -> Optional[str]:
        """If service is remote, return SSH target for commands."""
```

**Acceptance criteria:**
- [ ] Correctly detects current machine (hostname matching)
- [ ] Returns correct tunnel requirements per machine role
- [ ] Handles edge case: machine not in machines.json (standalone mode)

---

## Wave 3: Tunnel Management

### 3.1 Tunnel Manager

**File:** `agentwire/tunnels.py` (NEW)

Manage SSH tunnels lifecycle:

```python
@dataclass
class TunnelSpec:
    local_port: int
    remote_machine: str
    remote_port: int

@dataclass
class TunnelStatus:
    spec: TunnelSpec
    pid: Optional[int]
    status: Literal["up", "down", "stale", "error"]
    error: Optional[str]

class TunnelManager:
    """Manages SSH tunnels for service routing."""

    def create_tunnel(self, spec: TunnelSpec) -> TunnelStatus:
        """Create SSH tunnel. Handle errors gracefully."""

    def check_tunnel(self, spec: TunnelSpec) -> TunnelStatus:
        """Check if tunnel is alive and working."""

    def kill_tunnel(self, spec: TunnelSpec) -> bool:
        """Tear down tunnel."""

    def get_all_tunnels(self) -> list[TunnelStatus]:
        """List all AgentWire tunnels (by PID file or process scan)."""
```

**Error scenarios to handle:**

| Scenario | Detection | Error Message |
|----------|-----------|---------------|
| Port already in use | `OSError` on bind | "Port {port} already in use. Check: lsof -i :{port}" |
| SSH connection failed | Exit code != 0 | "Cannot SSH to {machine}: {error}. Test: ssh {machine} echo ok" |
| Remote port not listening | Tunnel up but no response | "Tunnel up but {service} not responding on {machine}:{port}. Check: agentwire {service} status" |
| SSH key not authorized | Permission denied | "SSH permission denied for {machine}. Add your key: ssh-copy-id {machine}" |
| Host key changed | Host key verification failed | "SSH host key changed for {machine}. If expected: ssh-keygen -R {machine}" |
| Network unreachable | Connection timeout | "Cannot reach {machine}. Check network connectivity and firewall." |

**Acceptance criteria:**
- [ ] Creates tunnels with proper SSH flags (`-f -N -L`)
- [ ] Stores PID for cleanup (`~/.agentwire/tunnels/{spec}.pid`)
- [ ] Detects stale tunnels (PID exists but process dead)
- [ ] All errors have actionable messages

### 3.2 Tunnel CLI Commands

**File:** `agentwire/__main__.py`

```bash
agentwire tunnels up      # Create all needed tunnels
agentwire tunnels down    # Tear down all tunnels
agentwire tunnels status  # Show tunnel health
agentwire tunnels check   # Verify tunnels are working (with health checks)
```

**`tunnels status` output:**
```
AgentWire Tunnels
─────────────────────────────────────────────────────
Portal → TTS (localhost:8100 → dotdev-pc:8100)
  Status: ✓ UP (PID 12345)
  Health: ✓ TTS responding (latency: 45ms)

Portal → Workers not needed (workers reach portal, not vice versa)
─────────────────────────────────────────────────────

To create missing tunnels: agentwire tunnels up
```

**`tunnels up` output:**
```
Creating tunnels for this machine (portal-vps)...

[1/1] Portal → TTS (localhost:8100 → dotdev-pc:8100)
      ✓ Tunnel created (PID 12345)
      ✓ Health check passed

All tunnels up. Services should be reachable.
```

**`tunnels up` error output:**
```
Creating tunnels for this machine (dev-macbook)...

[1/1] Dev → Portal (localhost:8765 → portal-vps:8765)
      ✗ Failed: Connection refused

ERROR: Cannot create tunnel to portal-vps

The portal machine (portal-vps) is not accepting SSH connections.

Possible causes:
  1. Machine is powered off or unreachable
  2. SSH server not running on portal-vps
  3. Firewall blocking port 22

To diagnose:
  ping portal-vps              # Check network
  ssh portal-vps echo ok       # Test SSH

To skip this tunnel: agentwire tunnels up --skip portal
```

**Acceptance criteria:**
- [ ] `tunnels up` is idempotent (safe to run multiple times)
- [ ] `tunnels down` cleans up PID files
- [ ] `tunnels status` shows actionable info for broken tunnels
- [ ] `tunnels check` does actual health checks through tunnels

---

## Wave 4: Remote-Aware Service Commands

### 4.1 Portal Commands (Remote-Aware)

**File:** `agentwire/__main__.py` - modify `cmd_portal_*`

Make portal commands work from any machine:

```python
def cmd_portal_start(args) -> int:
    ctx = NetworkContext.from_config()

    if ctx.is_local("portal"):
        # Current behavior - start locally
        return start_portal_local(args)
    else:
        # SSH to portal machine and start there
        machine = ctx.get_ssh_target("portal")
        print(f"Portal runs on {machine}, starting remotely...")
        return start_portal_remote(machine, args)

def cmd_portal_status(args) -> int:
    ctx = NetworkContext.from_config()

    if ctx.is_local("portal"):
        return check_portal_local()
    else:
        # Check via tunnel/network
        return check_portal_remote(ctx)
```

**Scenarios:**

| You're on | Command | Behavior |
|-----------|---------|----------|
| portal machine | `portal start` | Start locally (current behavior) |
| worker machine | `portal start` | SSH to portal machine, start there |
| any machine | `portal status` | Check via health endpoint (tunnel or direct) |

**Acceptance criteria:**
- [ ] `portal start` works from any machine
- [ ] `portal stop` works from any machine (SSH + tmux kill)
- [ ] `portal status` checks health endpoint, shows machine info
- [ ] Clear error if portal machine unreachable

### 4.2 TTS Commands (Remote-Aware)

**File:** `agentwire/__main__.py` - modify `cmd_tts_*`

Same pattern as portal:

```python
def cmd_tts_start(args) -> int:
    ctx = NetworkContext.from_config()

    if ctx.is_local("tts"):
        return start_tts_local(args)
    else:
        machine = ctx.get_ssh_target("tts")
        print(f"TTS runs on {machine}, starting remotely...")
        return start_tts_remote(machine, args)
```

**Acceptance criteria:**
- [ ] `tts start` works from any machine
- [ ] `tts stop` works from any machine
- [ ] `tts status` checks health endpoint through tunnel
- [ ] Handles venv activation on remote (current manual workaround)

### 4.3 remote-say Config-Aware

**File:** `agentwire/__main__.py` or wherever `remote-say` is implemented

Update `remote-say` to use config instead of file:

```python
def get_portal_url() -> str:
    """Get portal URL from config, with fallbacks."""
    ctx = NetworkContext.from_config()

    if ctx.is_local("portal"):
        return "https://localhost:8765"

    # Check if tunnel exists
    if ctx.tunnel_exists("portal"):
        return "https://localhost:8765"  # Via tunnel

    # Fall back to direct connection
    portal_machine = ctx.machines[ctx.config.services.portal.machine]
    return f"https://{portal_machine.host}:{ctx.config.services.portal.port}"
```

**Acceptance criteria:**
- [ ] Works when on portal machine (localhost)
- [ ] Works from worker machine via tunnel
- [ ] Falls back to direct if tunnel not up (with warning)
- [ ] Clear error if portal unreachable

---

## Wave 5: Startup Integration & DX

### 5.1 Auto-Tunnel on Portal Start

When `portal start` runs, automatically ensure required tunnels exist:

```python
def cmd_portal_start(args) -> int:
    ctx = NetworkContext.from_config()

    if ctx.is_local("portal"):
        # Ensure tunnel to TTS if TTS is remote
        if not ctx.is_local("tts"):
            print("TTS is remote, ensuring tunnel...")
            ensure_tunnel(ctx, "tts")

        return start_portal_local(args)
```

**Acceptance criteria:**
- [ ] `portal start` creates TTS tunnel if needed
- [ ] `portal start` warns if TTS unreachable but continues
- [ ] `portal stop` optionally tears down tunnels (`--with-tunnels`)

### 5.2 Network Status Command

**New command:** `agentwire network status`

Show complete network health at a glance:

```
AgentWire Network Status
═══════════════════════════════════════════════════════════════

You are on: dev-macbook

Machines
────────────────────────────────────────────────────────────────
  dev-macbook     (this machine)    ✓ reachable
  portal-vps      192.168.1.10      ✓ reachable (ssh: 23ms)
  dotdev-pc       192.168.1.50      ✓ reachable (ssh: 12ms)

Services
────────────────────────────────────────────────────────────────
  Portal          portal-vps:8765   ✓ running (via tunnel)
  TTS             dotdev-pc:8100    ✓ running (via portal tunnel)

Tunnels (this machine)
────────────────────────────────────────────────────────────────
  → Portal        localhost:8765    ✓ up (PID 12345)

Worker Sessions
────────────────────────────────────────────────────────────────
  dev-macbook     3 sessions        api, auth, frontend
  portal-vps      1 session         monitoring

Everything looks good! 🟢
```

**Error state example:**
```
AgentWire Network Status
═══════════════════════════════════════════════════════════════

You are on: dev-macbook

⚠️  Issues detected:

  1. TTS not responding
     Service: TTS on dotdev-pc:8100
     Error: Connection refused

     To fix:
       agentwire tts start          # Start TTS server
       agentwire tunnels check      # Verify tunnel health

  2. Missing tunnel
     Required: dev-macbook → portal-vps:8765
     Status: Not created

     To fix:
       agentwire tunnels up

────────────────────────────────────────────────────────────────

Run: agentwire doctor    # Auto-fix common issues
```

**Acceptance criteria:**
- [ ] Shows complete network topology
- [ ] Identifies all issues with fix instructions
- [ ] Fast (parallel health checks)
- [ ] Works offline (shows what it can)

### 5.3 Doctor Command

**New command:** `agentwire doctor`

Auto-diagnose and fix common issues:

```bash
$ agentwire doctor

AgentWire Doctor
═══════════════════════════════════════════════════════════════

Checking configuration...
  ✓ Config file valid
  ✓ Machines.json valid
  ✓ All referenced machines exist

Checking SSH connectivity...
  ✓ portal-vps: reachable
  ✓ dotdev-pc: reachable

Checking tunnels...
  ✗ Missing tunnel: localhost:8765 → portal-vps:8765
    → Creating tunnel... ✓ created (PID 12345)

Checking services...
  ✓ Portal: responding on portal-vps:8765
  ✗ TTS: not responding on dotdev-pc:8100
    → Starting TTS... ✓ started

All issues resolved! 🟢
```

**Acceptance criteria:**
- [ ] Non-destructive (only fixes obvious issues)
- [ ] Asks before taking action with `--interactive`
- [ ] `--dry-run` shows what it would do
- [ ] Logs all actions for debugging

---

## Wave 6: Documentation & Onboarding

### 6.1 Update CLAUDE.md

Add network architecture section explaining:
- Service topology concept
- How tunnels work
- Config requirements for multi-machine setup
- Troubleshooting guide

### 6.2 Config Template

Create `~/.agentwire/config.example.yaml` with documented `services` section:

```yaml
# Service locations - where each service runs in your network
# machine: null means "this machine", or use a machine ID from machines.json
services:
  portal:
    machine: null          # Portal runs on this machine
    port: 8765

  tts:
    machine: "gpu-server"  # TTS runs on GPU machine (needs CUDA)
    port: 8100

# If all services run locally, you can omit this section entirely.
# The defaults assume everything is local.
```

### 6.3 Error Message Catalog

Create consistent error messages in `agentwire/errors.py`:

```python
class NetworkError(AgentWireError):
    """Base class for network-related errors."""

    def __init__(self, message: str, context: dict, fix_steps: list[str]):
        self.message = message
        self.context = context
        self.fix_steps = fix_steps

    def __str__(self):
        lines = [
            f"ERROR: {self.message}",
            "",
            "Context:",
        ]
        for k, v in self.context.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append("To fix:")
        for i, step in enumerate(self.fix_steps, 1):
            lines.append(f"  {i}. {step}")
        return "\n".join(lines)
```

---

## Edge Cases & Error Scenarios

### Configuration Errors

| Scenario | Detection Point | Error Message |
|----------|-----------------|---------------|
| Missing config.yaml | CLI startup | "Config not found. Run: agentwire init" |
| Invalid YAML syntax | Config load | "Config syntax error at line {n}: {detail}" |
| Unknown machine reference | Validation | "Unknown machine '{id}'. Run: agentwire machine list" |
| Invalid port number | Validation | "Invalid port {port}. Must be 1-65535" |
| Missing machines.json | Config load | "machines.json not found. Run: agentwire init" |

### Network Errors

| Scenario | Detection Point | Error Message |
|----------|-----------------|---------------|
| SSH connection refused | Tunnel creation | "SSH refused by {machine}. Is SSH server running?" |
| SSH permission denied | Tunnel creation | "SSH permission denied. Run: ssh-copy-id {user}@{host}" |
| SSH timeout | Tunnel creation | "SSH timeout to {machine}. Check: ping {host}" |
| SSH host key changed | Tunnel creation | "Host key changed for {machine}. If expected: ssh-keygen -R {host}" |
| Port already bound | Tunnel creation | "Port {port} in use. Check: lsof -i :{port}" |
| Tunnel process died | Tunnel check | "Tunnel died (was PID {pid}). Run: agentwire tunnels up" |

### Service Errors

| Scenario | Detection Point | Error Message |
|----------|-----------------|---------------|
| Service not running | Health check | "{service} not running on {machine}. Run: agentwire {service} start" |
| Service unhealthy | Health check | "{service} running but unhealthy: {detail}" |
| Service port conflict | Service start | "Port {port} already in use on {machine}" |
| tmux not installed | Remote command | "tmux not found on {machine}. Install: apt install tmux" |
| Python/venv issues | TTS start | "Python environment issue on {machine}: {detail}" |

### Runtime Errors

| Scenario | Detection Point | Error Message |
|----------|-----------------|---------------|
| Tunnel dropped mid-request | remote-say | "Lost connection to portal. Run: agentwire tunnels check" |
| Service crashed | Health check | "{service} was running but stopped. Check logs: agentwire {service} logs" |
| Network partition | Any remote op | "Cannot reach {machine}. Network issue or machine down." |

---

## Completion Criteria

### Onboarding
- [ ] `agentwire init` guides new users through local setup
- [ ] Init wizard is idempotent (safe to re-run)
- [ ] Orchestrator init session walks through network setup
- [ ] All setup choices use AskUserQuestion
- [ ] New user can go from zero to working system with guidance

### Network-Aware CLI
- [ ] `agentwire tunnels up/down/status` works
- [ ] `agentwire portal start/stop/status` works from any machine
- [ ] `agentwire tts start/stop/status` works from any machine
- [ ] `remote-say` works from any machine
- [ ] `agentwire network status` shows full topology
- [ ] `agentwire doctor` auto-fixes common issues

### Error Handling
- [ ] All error messages include WHAT/WHY/HOW
- [ ] Config validated on startup with clear errors
- [ ] SSH failures have specific, actionable messages
- [ ] Tunnel failures explain how to diagnose

### Documentation
- [ ] CLAUDE.md updated with network architecture docs
- [ ] Init prompt template is comprehensive
- [ ] Config example file documents all options

### Regression
- [ ] Single-machine setup still works (no config changes needed)
- [ ] Works after reboot with just `agentwire tunnels up`

---

## Testing Scenarios

### Fresh Install (New User)
- No ~/.agentwire/ directory
- Run `agentwire init` → guided wizard
- Complete orchestrator init → working system
- Test: voice input/output, session creation

### Single Machine (Regression)
- All services local, no tunnels needed
- Everything should work as before
- No services section in config → defaults to local

### Two Machine (Current Setup)
- Portal + Workers on macOS
- TTS on dotdev-pc
- One tunnel: local → dotdev-pc:8100

### Three Machine (Target)
- Portal on portal-vps
- TTS on dotdev-pc
- Workers on dev-macbook
- Tunnels: portal→tts, dev→portal

### Re-Init (Existing User)
- Has existing config
- Run `agentwire init` → offers keep/replace/merge
- Can add new machines to existing network
- Doesn't break existing setup

### Degraded States
- TTS machine down → Portal works, voice fails gracefully
- Portal machine down → Workers work locally, no voice/remote-say
- Tunnel dies → Clear error, easy recovery
- SSH key revoked → Specific error with fix instructions
