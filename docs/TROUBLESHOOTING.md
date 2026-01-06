# AgentWire Installation Troubleshooting

Common issues and solutions for installing and configuring AgentWire across different platforms.

## Python Version Errors

### Problem: "Package 'agentwire-dev' requires a different Python: X.X.X not in '>=3.10'"

AgentWire requires Python 3.10 or higher. Check your version:

```bash
python3 --version
```

### Solutions by Platform

**macOS:**

```bash
# Install pyenv
brew install pyenv

# Install Python 3.12
pyenv install 3.12.0
pyenv global 3.12.0

# Add to shell profile (~/.zshrc or ~/.bashrc)
export PATH="$HOME/.pyenv/shims:$PATH"
eval "$(pyenv init -)"

# Reload shell
source ~/.zshrc  # or source ~/.bashrc

# Verify
python3 --version  # Should show 3.12.0
```

**Ubuntu/Debian:**

```bash
# Update package list
sudo apt update

# Install Python 3.12
sudo apt install python3.12 python3.12-venv python3-pip

# Set as default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Verify
python3 --version
```

**Alternative - Use pyenv on Linux:**

```bash
# Install dependencies
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# Install pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.12
pyenv install 3.12.0
pyenv global 3.12.0
```

---

## Externally-Managed Python Environments (Ubuntu 24.04+)

### Problem: "error: externally-managed-environment"

Ubuntu 24.04+ prevents pip from modifying system Python to avoid conflicts with system packages.

**Full Error:**
```
error: externally-managed-environment
× This environment is externally managed
```

### Solution 1: Use venv (Recommended)

Create a dedicated virtual environment for AgentWire:

```bash
# Create venv
python3 -m venv ~/.agentwire-venv

# Activate
source ~/.agentwire-venv/bin/activate

# Install AgentWire
pip install git+https://github.com/dotdevdotdev/agentwire.git

# Make activation persistent
echo 'source ~/.agentwire-venv/bin/activate' >> ~/.bashrc
```

**Why this is better:**
- Isolated from system Python
- No risk of breaking system packages
- Standard Python best practice
- Easy to remove/recreate

### Solution 2: --break-system-packages (Not Recommended)

```bash
pip3 install --break-system-packages git+https://github.com/dotdevdotdev/agentwire.git
```

**Downsides:**
- Can conflict with system packages
- May break system tools that depend on Python
- Not recommended by Python/Ubuntu maintainers

---

## Missing Dependencies

### ffmpeg Not Found

**Symptom:** Push-to-talk doesn't work, portal logs show audio conversion errors

**Check:**
```bash
which ffmpeg
```

**Install:**

| Platform | Command |
|----------|---------|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| WSL2 | `sudo apt install ffmpeg` |

**Verify:**
```bash
ffmpeg -version
```

### whisperkit-cli Not Found (macOS)

**Symptom:** Voice transcription fails, portal logs show "whisperkit-cli not found"

**Requirements:**
- macOS with Apple Silicon (M1/M2/M3)
- MacWhisper app with models

**Install MacWhisper:**

1. Download from: https://goodsnooze.gumroad.com/l/macwhisper
2. Install the app
3. Run once to download models
4. Verify models exist:

```bash
ls -la ~/Library/Application\ Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/
```

**Install whisperkit-cli:**

```bash
brew install whisperkit-cli

# Verify
which whisperkit-cli
```

**Configure in config.yaml:**

```yaml
stt:
  backend: "whisperkit"
  model_path: "~/Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930"
  language: "en"
```

### OpenAI API Key Missing

**Symptom:** Voice transcription fails with OpenAI backend

**Check:**
```bash
echo $OPENAI_API_KEY
```

**Set permanently:**

```bash
# Add to ~/.bashrc or ~/.zshrc
export OPENAI_API_KEY="sk-..."

# Reload shell
source ~/.bashrc
```

**Verify:**
```bash
echo $OPENAI_API_KEY  # Should show your key
```

---

## PATH Issues

### Problem: "command not found: agentwire" (even after install)

**Symptom:** Installation succeeds but commands aren't found

**Cause:** Installation directory not in PATH

### Check Installation Location

```bash
pip3 show agentwire-dev | grep Location
```

Common locations:
- `/usr/local/lib/python3.X/dist-packages` (system-wide)
- `~/.local/lib/python3.X/site-packages` (user install)
- `~/.pyenv/versions/3.X.X/lib/python3.X/site-packages` (pyenv)

### Fix PATH

**For ~/.local/bin:**

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Reload
source ~/.bashrc
```

**For pyenv:**

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.pyenv/shims:$PATH"
eval "$(pyenv init -)"

# Reload
source ~/.bashrc
```

**Verify:**

```bash
which agentwire
agentwire --version
```

### Problem: Scripts installed but not executable

```bash
# Make scripts executable
chmod +x $(which agentwire)
chmod +x ~/.local/bin/say ~/.local/bin/remote-say  # If applicable
```

---

## SSL Certificate Errors

### Problem: "SSL: CERTIFICATE_VERIFY_FAILED" or browser shows "Not Secure"

**Cause:** Self-signed certificates aren't trusted by browser/system

### Solution 1: Accept in Browser (Recommended for Development)

1. Navigate to `https://localhost:8765`
2. Click "Advanced"
3. Click "Proceed to localhost (unsafe)"

This is safe for localhost development.

### Solution 2: Regenerate Certificates

```bash
agentwire generate-certs
```

Certificates are stored at:
- `~/.agentwire/cert.pem`
- `~/.agentwire/key.pem`

### Solution 3: Trust Certificate System-Wide (macOS)

```bash
# Add to Keychain
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.agentwire/cert.pem
```

### Problem: Portal requires HTTPS but remote-say uses HTTP

**Fix config.yaml:**

```yaml
server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    enabled: true
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"
```

**Create portal_url file:**

```bash
echo "https://localhost:8765" > ~/.agentwire/portal_url
```

---

## Remote Machine Connectivity

### SSH Connection Issues

**Problem: "Connection refused" when adding remote machine**

**Check:**
```bash
ssh user@host echo "test"
```

**Common fixes:**

1. **SSH key not configured:**
   ```bash
   # Generate key
   ssh-keygen -t ed25519

   # Copy to remote
   ssh-copy-id user@host
   ```

2. **Host unreachable:**
   ```bash
   ping host
   # Check firewall, network connectivity
   ```

3. **Wrong username:**
   ```bash
   # Check SSH config
   cat ~/.ssh/config

   # Or specify explicitly
   ssh -l username host
   ```

### Tunnel Creation Failures

**Problem: "Address already in use" when creating tunnel**

**Find what's using the port:**
```bash
lsof -i :8765
```

**Kill conflicting process:**
```bash
kill -9 <PID>
```

**Or use different port in config.yaml:**
```yaml
server:
  port: 8766  # Changed from 8765
```

### Remote Installation Issues

**Problem: AgentWire not installed on remote machine**

**Verify:**
```bash
ssh user@host "which agentwire"
```

**Install on remote:**
```bash
ssh user@host "pip3 install git+https://github.com/dotdevdotdev/agentwire.git"
```

**For Ubuntu externally-managed:**
```bash
ssh user@host "python3 -m venv ~/.agentwire-venv && source ~/.agentwire-venv/bin/activate && pip install git+https://github.com/dotdevdotdev/agentwire.git"
```

### portal_url Not Set on Remote

**Problem: remote-say fails with connection error**

**Fix:**
```bash
ssh user@host "echo 'https://localhost:8765' > ~/.agentwire/portal_url"
```

For remote machines, use the tunnel endpoint (localhost) not the portal host IP.

---

## Voice/Audio Issues

### Microphone Not Working

**Browser permissions:**
1. Check browser mic permissions (usually prompted on first use)
2. If blocked, go to browser settings and allow microphone for `https://localhost:8765`

**macOS system permissions:**
1. System Settings → Privacy & Security → Microphone
2. Ensure browser has permission

**Select correct device:**
1. In portal UI, use mic selector dropdown
2. Test by speaking and watching for visual feedback

### TTS Not Playing

**Check TTS configuration:**

```yaml
tts:
  backend: "chatterbox"
  url: "http://localhost:8100"  # Or remote TTS server
  default_voice: "your-voice"
```

**Test TTS endpoint:**
```bash
curl http://localhost:8100/voices
```

**Check voice exists:**
```bash
curl http://localhost:8100/voices | grep "your-voice"
```

**Common issues:**

1. **Wrong TTS URL:** Update config.yaml with correct URL
2. **TTS server not running:** `agentwire tts start` (on GPU machine)
3. **Voice doesn't exist:** Use `agentwire voiceclone` to create or change `default_voice` in config

---

## Configuration Issues

### Config File Not Found

**Problem: Portal won't start, no config.yaml**

**Run interactive setup:**
```bash
agentwire init
```

This creates `~/.agentwire/config.yaml` with guided prompts.

**Or create manually:**

```yaml
server:
  host: "0.0.0.0"
  port: 8765

tts:
  backend: "none"  # Or "chatterbox" if available

stt:
  backend: "none"  # Or "whisperkit", "whispercpp", "openai"

projects:
  dir: "~/projects"
  worktrees:
    enabled: true
```

### Invalid YAML Syntax

**Symptom:** Portal fails to start with YAML parse error

**Validate:**
```bash
python3 -c "import yaml; yaml.safe_load(open('$HOME/.agentwire/config.yaml'))"
```

**Common issues:**
- Tabs instead of spaces (use spaces for indentation)
- Missing quotes around paths with special characters
- Incorrect nesting

---

## Permission/Hooks Issues

### Skills Not Found in Claude Code

**Problem: `/sessions`, `/send` commands not recognized**

**Install skills:**
```bash
agentwire skills install
```

**Verify:**
```bash
ls -la ~/.claude/skills/agentwire
```

Should show symlink to agentwire package.

**Restart Claude Code** after installing skills.

### Damage Control Hooks Not Working

**Problem: Dangerous commands not being blocked**

**Install hooks:**
```bash
agentwire safety install
```

**Verify hooks registered:**
```bash
cat ~/.claude/settings.json | grep -A 10 "PreToolUse"
```

**Test:**
```bash
agentwire safety check "rm -rf /tmp"
# Should show: ✗ Decision: BLOCK
```

---

## Getting More Help

### Run Diagnostics

```bash
# Full system check
agentwire doctor

# Auto-fix common issues
agentwire doctor --yes

# Show what would be fixed (dry-run)
agentwire doctor --dry-run
```

### Check Logs

```bash
# Portal logs
agentwire output -s agentwire-portal -n 50

# TTS logs (if running)
agentwire output -s agentwire-tts -n 50

# Damage control audit logs
agentwire safety logs --tail 20
```

### Verify Installation

```bash
# Python version
python3 --version  # Should be >= 3.10

# Package installed
pip3 show agentwire-dev

# Commands available
which agentwire

# Dependencies
which ffmpeg
which tmux
```

### Community Support

- **GitHub Issues:** https://github.com/dotdevdotdev/agentwire/issues
- **Documentation:** See `CLAUDE.md` for detailed configuration reference
- **Case Study:** See `docs/installation-case-study.md` for real-world setup example
