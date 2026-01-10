# Installation

> Living document. Update this, don't create new versions.

## Prerequisites

| Requirement | Minimum Version | Check Command |
|-------------|-----------------|---------------|
| Python | 3.10+ | `python3 --version` |
| tmux | Any recent | `tmux -V` |
| ffmpeg | Any recent | `ffmpeg -version` |

**Install dependencies:**

| Platform | Command |
|----------|---------|
| macOS | `brew install tmux ffmpeg` |
| Ubuntu/Debian | `sudo apt install tmux ffmpeg` |
| WSL2 | `sudo apt install tmux ffmpeg` |

---

## Platform-Specific Notes

### macOS

- If Python < 3.10, install via pyenv:
  ```bash
  brew install pyenv
  pyenv install 3.12.0
  pyenv global 3.12.0
  ```
- For WhisperKit STT, install MacWhisper: https://goodsnooze.gumroad.com/l/macwhisper
- SSL certificates work out of the box for localhost

### Ubuntu 24.04+ (Externally-Managed Python)

**Recommended:** Use venv instead of `--break-system-packages`:

```bash
python3 -m venv ~/.agentwire-venv
source ~/.agentwire-venv/bin/activate
pip install git+https://github.com/dotdevdotdev/agentwire.git
echo 'source ~/.agentwire-venv/bin/activate' >> ~/.bashrc
```

This avoids conflicts with system packages.

### WSL2

- Audio support may be limited (no browser audio in WSL)
- Use as remote worker with portal on host machine

---

## Quick Install

```bash
# Standard installation
pip install git+https://github.com/dotdevdotdev/agentwire.git

# Interactive setup
agentwire init

# Generate SSL certificates
agentwire generate-certs

# Install Claude Code skills and hooks
agentwire skills install

# Start portal
agentwire portal start
```

**Expected time:**
- First-time install: 20-30 minutes (including config, dependencies)
- Subsequent installs: 5 minutes (if dependencies already installed)

---

## Post-Install Setup

### 1. Initialize Configuration

```bash
agentwire init
```

Creates `~/.agentwire/` with default config files.

### 2. Generate SSL Certificates

```bash
agentwire generate-certs
```

Required for HTTPS on localhost. Creates `~/.agentwire/cert.pem` and `~/.agentwire/key.pem`.

### 3. Install Claude Code Integration

```bash
agentwire skills install
```

Installs:
- Skills in `~/.claude/skills/agentwire`
- Hooks in `~/.claude/hooks/`

### 4. Start the Portal

```bash
agentwire portal start
```

Opens https://localhost:8765 in your browser.

---

## Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| Python version too old | macOS: `brew install pyenv && pyenv install 3.12.0`<br>Ubuntu: `sudo apt install python3.12` |
| Externally-managed error | Use venv (see Ubuntu notes above) |
| ffmpeg not found | macOS: `brew install ffmpeg`<br>Ubuntu: `sudo apt install ffmpeg` |
| agentwire command not found | Add to PATH: `export PATH="$HOME/.local/bin:$PATH"` |
| SSL certificate warnings | Run `agentwire generate-certs` |
| Push-to-talk doesn't work | Install ffmpeg, check browser mic permissions |

For detailed troubleshooting, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

---

## Updating

### From Source (Development)

```bash
cd ~/projects/agentwire
git pull
agentwire rebuild   # Clears uv cache and reinstalls
```

### From pip

```bash
pip install --upgrade git+https://github.com/dotdevdotdev/agentwire.git
```

---

## Uninstalling

```bash
# Remove the CLI tool
agentwire uninstall

# Remove configuration (optional)
rm -rf ~/.agentwire

# Remove Claude Code integration (optional)
agentwire skills uninstall
```
