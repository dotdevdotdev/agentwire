> Living document. Update this, don't create new versions.

# Mission: Cloudflare Tunnel for Remote Access

Securely expose the AgentWire portal to the internet using Cloudflare Tunnel and Cloudflare Access for authentication.

## Status: Complete (Core Failsafes)

### Completed
- [x] Phase 1: cloudflared installed via Homebrew
- [x] Phase 2: Authenticated with Cloudflare (cert.pem exists)
- [x] Phase 3: Tunnel created (`agentwire`, ID: `0495a277-931e-474f-bd43-35896dac7b59`)
- [x] Phase 4: Config file created (`~/.cloudflared/config.yml`)
- [x] Phase 5: DNS route created (`agentwire.solodev.dev`)
- [x] Phase 6: Set up Cloudflare Access (dashboard) - portal, SSH, VNC apps created
- [x] Phase 7: Install tunnel as service (`/Library/LaunchDaemons/com.cloudflare.cloudflared.plist`)
- [x] Phase 8: Verify setup from phone - SSH and VNC browser access working
- [x] Phase 8b: Termux SSH setup (`ssh mac` works from Android)
- [x] Phase 8c: Caffeinate service installed (prevents Mac sleep)

### Remaining (Nice to Have)
- [ ] Phase 9: Install remote presence scripts (webcam, mic, screenshot)
- [ ] Phase 10: Implement secure sudo in portal
- [ ] Reboot test to verify all services come back up

## Value Proposition

- Access AgentWire portal from anywhere (phone, tablet, remote laptop)
- Push-to-talk voice control while away from home
- No open ports on local network (outbound tunnel only)
- Zero Trust authentication via Cloudflare Access
- Free tier sufficient for personal use

## Architecture

```
Phone/Remote Device
        │
        ▼
Cloudflare Access (authentication gate)
        │ ✓ authenticated
        ▼
Cloudflare Edge (tunnel endpoint)
        │
        ▼ (outbound connection from Mac)
cloudflared daemon (Mac Mini)
        │
        ▼
AgentWire Portal (localhost:8765)
```

## Prerequisites

- Cloudflare account (free tier works)
- Domain managed by Cloudflare DNS (or use `*.cfargotunnel.com` for testing)
- `cloudflared` CLI installed on Mac

## Implementation Plan

### Phase 1: Install cloudflared

```bash
# Install via Homebrew
brew install cloudflare/cloudflare/cloudflared

# Verify installation
cloudflared --version
```

### Phase 2: Authenticate with Cloudflare

```bash
# Login (opens browser)
cloudflared tunnel login

# This creates ~/.cloudflared/cert.pem
```

### Phase 3: Create Tunnel

```bash
# Create a named tunnel
cloudflared tunnel create agentwire

# This creates ~/.cloudflared/<tunnel-id>.json (credentials)
# Note the tunnel ID for later
```

### Phase 4: Configure Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <tunnel-id>
credentials-file: /Users/dotdev/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: agentwire.solodev.dev
    service: https://localhost:8765
    originRequest:
      noTLSVerify: true  # Portal uses self-signed cert
  - service: http_status:404  # Catch-all
```

### Phase 5: Create DNS Record

```bash
# Create CNAME pointing to tunnel
cloudflared tunnel route dns agentwire agentwire.solodev.dev
```

### Phase 6: Set Up Cloudflare Access

In Cloudflare Dashboard → Zero Trust → Access → Applications:

1. **Add Application** → Self-hosted
2. **Application name**: AgentWire Portal
3. **Session duration**: 24 hours (or preference)
4. **Application domain**: `agentwire.solodev.dev`

Create Access Policy:
1. **Policy name**: Allow Me
2. **Action**: Allow
3. **Include rule**: 
   - Emails: `your-email@gmail.com`
   - OR Login Methods: Google/GitHub

### Phase 7: Run Tunnel as Service

```bash
# Install as launchd service
sudo cloudflared service install

# Or run manually for testing
cloudflared tunnel run agentwire
```

LaunchDaemon will be created at:
`/Library/LaunchDaemons/com.cloudflare.cloudflared.plist`

### Phase 8: Verify Setup

1. Visit `https://agentwire.solodev.dev` from phone
2. Cloudflare Access prompts for login
3. Authenticate with Google/GitHub
4. Portal loads
5. Test push-to-talk

### Phase 9: Remote Presence Tools

Install helper scripts for remote monitoring (not in repo, personal tools only).

#### Prerequisites

```bash
# Install imagesnap for webcam capture
brew install imagesnap

# ffmpeg for audio capture (may already be installed)
brew install ffmpeg
```

#### Create Scripts Directory

```bash
mkdir -p ~/.local/bin
```

#### ~/.local/bin/webcam-snap

```bash
#!/bin/bash
# Capture a photo from the webcam
OUTPUT="${1:-$HOME/.agentwire/uploads/webcam-$(date +%Y%m%d-%H%M%S).jpg}"
mkdir -p "$(dirname "$OUTPUT")"
imagesnap -q "$OUTPUT"
echo "$OUTPUT"
```

#### ~/.local/bin/mic-listen

```bash
#!/bin/bash
# Record audio from microphone
DURATION="${1:-10}"  # Default 10 seconds
OUTPUT="${2:-$HOME/.agentwire/uploads/audio-$(date +%Y%m%d-%H%M%S).mp3}"
mkdir -p "$(dirname "$OUTPUT")"
ffmpeg -f avfoundation -i ":0" -t "$DURATION" -y -loglevel error "$OUTPUT"
echo "$OUTPUT"
```

#### ~/.local/bin/desktop-screenshot

```bash
#!/bin/bash
# Capture screenshot of the desktop
OUTPUT="${1:-$HOME/.agentwire/uploads/screenshot-$(date +%Y%m%d-%H%M%S).png}"
mkdir -p "$(dirname "$OUTPUT")"
screencapture -x "$OUTPUT"
echo "$OUTPUT"
```

#### ~/.local/bin/play-sound

```bash
#!/bin/bash
# Play a sound or speak text through speakers
if [ -f "$1" ]; then
    afplay "$1"
else
    say "$*"
fi
```

#### Make Executable

```bash
chmod +x ~/.local/bin/webcam-snap
chmod +x ~/.local/bin/mic-listen
chmod +x ~/.local/bin/desktop-screenshot
chmod +x ~/.local/bin/play-sound
```

#### Ensure Scripts in PATH

Add to `~/.zshrc` or `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

#### Usage (via Claude)

When connected remotely, ask Claude to:

- "Take a webcam photo" → runs `webcam-snap`
- "Listen to the room for 30 seconds" → runs `mic-listen 30`
- "Take a screenshot" → runs `desktop-screenshot`
- "Say hello through the speakers" → runs `play-sound "hello"`

Files are saved to `~/.agentwire/uploads/` and accessible via portal at `/uploads/filename`.

### Phase 10: Secure Remote Sudo

Enable running sudo commands remotely with password authentication through the portal.

#### Security Model

```
Phone → [HTTPS/TLS] → Cloudflare Access → [HTTPS/TLS] → Portal → [stdin] → sudo -S
```

| Layer | Protection |
|-------|------------|
| Phone → Cloudflare | TLS encryption |
| Cloudflare Access | Only authenticated user can reach portal |
| Cloudflare → Portal | TLS via tunnel |
| Portal → sudo | Password via stdin (`sudo -S`), in memory only |

This is equivalent to SSH with password auth - the password is encrypted in transit and only briefly in memory on the target machine.

#### Portal API Endpoint

Add `POST /api/sudo` endpoint to portal:

```python
@app.route('/api/sudo', methods=['POST'])
async def sudo_command(request):
    """Execute a command with sudo, password via stdin."""
    data = await request.json()
    command = data.get('command')
    password = data.get('password')

    # SECURITY: Never log the password
    logger.info(f"Sudo request for command: {command}")

    # Run sudo with -S flag (read password from stdin)
    proc = await asyncio.create_subprocess_exec(
        'sudo', '-S', 'sh', '-c', command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Send password to stdin
    stdout, stderr = await proc.communicate(input=f"{password}\n".encode())

    # Clear password from memory
    password = None

    return {
        'exit_code': proc.returncode,
        'stdout': stdout.decode(),
        'stderr': stderr.decode()
    }
```

#### Portal UI Component

Add password prompt modal to portal UI:

```javascript
// When sudo is needed, show modal
async function runSudo(command) {
    const password = await showPasswordPrompt('Enter sudo password:');
    if (!password) return null;

    const response = await fetch('/api/sudo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, password })
    });

    return response.json();
}
```

#### MCP Tool

```python
@mcp.tool()
def sudo_run(command: str) -> str:
    """Run a command with sudo (requires password via portal).

    When called remotely, the portal will prompt for password.
    Password is transmitted securely over HTTPS and passed to sudo via stdin.

    Args:
        command: Shell command to run with sudo

    Returns:
        Command output or error message
    """
```

#### Security Requirements

1. **Never log passwords** - Audit all logging to ensure password never appears
2. **Clear from memory** - Set password variable to None after use
3. **Rate limiting** - Limit sudo attempts to prevent brute force
4. **Audit logging** - Log all sudo commands (without passwords) for review
5. **Timeout** - Sudo commands timeout after reasonable period

#### Usage

When connected remotely, Claude can run sudo commands:

1. Claude calls `sudo_run("cloudflared service install")`
2. Portal shows password prompt on user's phone
3. User enters password
4. Password sent securely to portal
5. Portal runs `sudo -S` with password via stdin
6. Result returned to Claude

## Configuration Files

### ~/.cloudflared/config.yml

```yaml
tunnel: 0495a277-931e-474f-bd43-35896dac7b59
credentials-file: /Users/dotdev/.cloudflared/0495a277-931e-474f-bd43-35896dac7b59.json

ingress:
  # AgentWire portal
  - hostname: agentwire.solodev.dev
    service: https://localhost:8765
    originRequest:
      noTLSVerify: true

  # SSH backup access (add after setting up Remote Login)
  - hostname: ssh.solodev.dev
    service: ssh://localhost:22

  # Fallback
  - service: http_status:404
```

### Cloudflare Access Policy

| Setting | Value |
|---------|-------|
| Application type | Self-hosted |
| Domain | agentwire.solodev.dev |
| Session duration | 24 hours |
| Policy action | Allow |
| Include | Email = your-email@gmail.com |

## CLI Commands (Future)

Consider adding tunnel management to agentwire CLI:

```bash
# Check tunnel status
agentwire tunnel status

# Start/stop tunnel
agentwire tunnel start
agentwire tunnel stop

# Show public URL
agentwire tunnel url
```

## Security Considerations

### What's Protected

- **Cloudflare Access**: Blocks unauthenticated requests at edge
- **No open ports**: Tunnel is outbound-only
- **SSL/TLS**: End-to-end encryption
- **DDoS protection**: Cloudflare handles attack traffic

### Remaining Risks

| Risk | Mitigation |
|------|------------|
| Cloudflare account compromise | Use strong password + 2FA |
| Stolen session cookie | Short session duration, device binding |
| cloudflared daemon compromise | Keep updated, monitor logs |
| Portal vulnerabilities | Keep portal updated, audit code |
| Sudo password interception | TLS encryption, Cloudflare Access gate, memory-only handling |
| Sudo brute force | Rate limiting on /api/sudo endpoint |

### What We're NOT Adding

- Portal-level authentication (Cloudflare Access is sufficient)
- IP allowlisting (incompatible with mobile)
- Client certificates (too complex for phone)

## Resilience & Recovery

Ensure remote access stays available even when things go wrong.

### Prevent Mac Sleep

The Mac must never sleep or the tunnel dies.

```bash
# Option 1: System Preferences
# System Settings → Energy → Prevent automatic sleeping when display is off

# Option 2: caffeinate in launchd (runs forever)
# Create ~/Library/LaunchAgents/com.user.caffeinate.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.caffeinate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-s</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.user.caffeinate.plist
```

### Portal Auto-Restart

Create launchd job to auto-restart portal if it crashes.

```bash
# Create ~/Library/LaunchAgents/com.agentwire.portal.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.agentwire.portal</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/dotdev/.local/bin/agentwire</string>
        <string>portal</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/dotdev/projects/agentwire-dev</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/dotdev/.agentwire/logs/portal.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/dotdev/.agentwire/logs/portal.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/dotdev/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

**Note:** Requires `agentwire portal start --foreground` flag (runs in foreground instead of spawning tmux). This flag needs to be implemented in the CLI.

### SSH Backup Tunnel

Add SSH as a second ingress point for emergency access.

Update `~/.cloudflared/config.yml`:

```yaml
tunnel: <tunnel-id>
credentials-file: /Users/dotdev/.cloudflared/<tunnel-id>.json

ingress:
  # AgentWire portal
  - hostname: agentwire.solodev.dev
    service: https://localhost:8765
    originRequest:
      noTLSVerify: true

  # SSH backup access
  - hostname: ssh.solodev.dev
    service: ssh://localhost:22

  # Fallback
  - service: http_status:404
```

```bash
# Add DNS route for SSH
cloudflared tunnel route dns agentwire ssh.solodev.dev
```

**Usage (from remote):**

```bash
# Use cloudflared to tunnel SSH
cloudflared access ssh --hostname ssh.solodev.dev

# Or configure ~/.ssh/config
Host mac-remote
    HostName ssh.solodev.dev
    User dotdev
    ProxyCommand cloudflared access ssh --hostname %h
```

**Protect SSH with Access policy** - create separate Access application for ssh.solodev.dev.

**Enable Remote Login on Mac:**
```
System Settings → General → Sharing → Remote Login → On
```

### Reboot Recovery

After reboot, these services must auto-start:

| Service | LaunchDaemon/Agent | Location |
|---------|-------------------|----------|
| Cloudflare Tunnel | LaunchDaemon | `/Library/LaunchDaemons/com.cloudflare.cloudflared.plist` |
| AgentWire Portal | LaunchAgent | `~/Library/LaunchAgents/com.agentwire.portal.plist` |
| Caffeinate | LaunchAgent | `~/Library/LaunchAgents/com.user.caffeinate.plist` |

**Verify after reboot:**

```bash
# Check all services running
launchctl list | grep -E "cloudflared|agentwire|caffeinate"

# Check tunnel connected
cloudflared tunnel info agentwire

# Check portal responding
curl -k https://localhost:8765/health
```

### Health Monitoring

Add health check endpoint to portal for monitoring.

```python
@app.route('/health')
async def health_check(request):
    """Health check endpoint for monitoring."""
    import shutil
    disk = shutil.disk_usage('/')
    disk_free_gb = disk.free / (1024**3)

    import psutil
    memory = psutil.virtual_memory()
    memory_free_gb = memory.available / (1024**3)

    return {
        'status': 'healthy',
        'disk_free_gb': round(disk_free_gb, 1),
        'memory_free_gb': round(memory_free_gb, 1),
        'tunnel': 'connected',  # Check tunnel status
        'sessions': len(list_sessions())
    }
```

**External monitoring (optional):**
- Use Cloudflare's built-in health checks
- Or a free service like UptimeRobot to ping the health endpoint

### tmux Recovery

If tmux server crashes, all sessions are lost. Mitigations:

1. **Auto-recreate sessions on portal start:**
   - Portal checks for expected sessions
   - Recreates missing ones from `.agentwire.yml` configs

2. **Session resurrection (future):**
   - Persist session state to disk
   - Restore on tmux restart

3. **tmux resurrect plugin (manual):**
   ```bash
   # Install tmux-resurrect plugin for manual save/restore
   # https://github.com/tmux-plugins/tmux-resurrect
   ```

### Resource Exhaustion

Monitor and prevent disk/memory issues:

```bash
# Add to cron or launchd - check disk space
if [ $(df -h / | tail -1 | awk '{print $5}' | tr -d '%') -gt 90 ]; then
    agentwire say "Warning: Disk space low"
fi

# Clean up old uploads
find ~/.agentwire/uploads -mtime +7 -delete

# Clean up old logs
find ~/.agentwire/logs -name "*.log" -mtime +30 -delete
```

### Recovery Runbook

If locked out remotely:

1. **Portal not responding:**
   - SSH via backup tunnel: `cloudflared access ssh --hostname ssh.solodev.dev`
   - Check portal: `agentwire portal status`
   - Restart: `agentwire portal restart`

2. **Tunnel not connected:**
   - SSH in and check: `cloudflared tunnel info agentwire`
   - Restart tunnel: `sudo launchctl kickstart -k system/com.cloudflare.cloudflared`

3. **Mac appears offline:**
   - Wait for power/network to restore
   - If UPS available, check battery status remotely
   - Call someone local to check physically

4. **Everything broken:**
   - Physical access required
   - Or: smart plug to power cycle Mac (risky but last resort)

## Testing Checklist

- [ ] `cloudflared tunnel run` connects successfully
- [ ] DNS resolves to Cloudflare
- [ ] Access policy blocks unauthenticated requests
- [ ] Authentication flow works on mobile browser
- [ ] Portal loads after authentication
- [ ] Push-to-talk works over tunnel
- [ ] WebSocket connections stable
- [ ] Session persists across page reloads
- [ ] `webcam-snap` captures photo successfully
- [ ] `mic-listen` records audio successfully
- [ ] `desktop-screenshot` captures screen
- [ ] Captured files accessible via portal `/uploads/`
- [ ] Sudo password prompt appears on remote device
- [ ] Sudo commands execute successfully with password
- [ ] Password never appears in logs
- [ ] Mac sleep disabled (caffeinate running)
- [ ] Portal auto-restarts after crash
- [ ] SSH backup tunnel works
- [ ] All services survive reboot
- [ ] Health endpoint returns status

## Troubleshooting

### Tunnel won't connect

```bash
# Check tunnel status
cloudflared tunnel info agentwire

# Test connection
cloudflared tunnel run agentwire --loglevel debug
```

### 502 Bad Gateway

- Portal not running: `agentwire portal status`
- Wrong port in config: verify `localhost:8765`
- TLS issue: ensure `noTLSVerify: true` in config

### Access loop / can't authenticate

- Check Access policy includes your email/identity provider
- Clear browser cookies for the domain
- Check Cloudflare Access logs in dashboard

### WebSocket disconnects

- Cloudflare supports WebSockets by default
- Check for idle timeout settings in Access app config
- May need to adjust portal heartbeat interval

## Cost

| Component | Cost |
|-----------|------|
| Cloudflare Tunnel | Free |
| Cloudflare Access | Free (up to 50 users) |
| Domain (if needed) | ~$10/year |

## Dependencies

- Cloudflare account
- `cloudflared` CLI
- Domain with Cloudflare DNS (or test subdomain)
- `imagesnap` (for webcam capture)
- `ffmpeg` (for audio capture)
- `psutil` Python package (for health monitoring)
- Remote Login enabled on Mac (for SSH backup)

## Success Criteria

1. Portal accessible from phone outside home network
2. Unauthenticated users blocked by Cloudflare Access
3. Push-to-talk works over tunnel
4. Tunnel runs as persistent service (survives reboot)
5. Remote presence tools work (webcam, mic, screenshot)
6. Captured media accessible via portal URL
7. Secure sudo works via portal password prompt
8. Mac never sleeps (caffeinate active)
9. Portal auto-restarts on crash
10. SSH backup access available
11. All services recover after reboot
12. Setup documented for other users

## References

- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Cloudflare Access docs](https://developers.cloudflare.com/cloudflare-one/policies/access/)
- [cloudflared CLI reference](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/)
