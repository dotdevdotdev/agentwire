# Mission: Installation Experience Improvements

> Reduce first-time installation from 2 hours to 20-30 minutes with better dependency checks, automation, and documentation.

## Objective

Based on the January 6, 2026 case study (Mac Mini + 2 DigitalOcean devboxes), eliminate all manual steps and undocumented requirements from the installation process.

## Reference

See `docs/installation-case-study.md` for complete timeline and pain points.

**Current state:** 2 hours with manual intervention
**Target state:** 20-30 minutes fully automated

## Wave 1: Human Actions (BLOCKING)

**Decisions made:**
- ✅ say/remote-say: Shell wrapper scripts (simple, works anywhere)
- ✅ Remote setup: Fully automated (install + configure + tunnels)
- ✅ Ubuntu approach: Recommend venv (better practice over --break-system-packages)
- ✅ Priority: All waves (dependency checks, scripts, remote setup, doctor enhancements)

- [ ] Review case study one more time for any missed issues
- [ ] Verify shell script installation paths are correct for all platforms

## Wave 2: Dependency Detection & Pre-Flight Checks

### 2.1 Python version check in init

**Files:** `agentwire/onboarding.py`

- Add Python version check at start of `run_onboarding()`
- If < 3.10, show platform-specific upgrade instructions:
  - macOS: `pyenv install 3.12.0 && pyenv global 3.12.0`
  - Ubuntu: `sudo apt update && sudo apt install python3.12`
  - With links to installation guides
- Exit if version too old (don't proceed with broken config)

### 2.2 ffmpeg detection

**Files:** `agentwire/onboarding.py`

- Check for `ffmpeg` binary in PATH
- If missing, show install command:
  - macOS: `brew install ffmpeg`
  - Ubuntu: `sudo apt install ffmpeg`
  - Show warning that push-to-talk won't work without it
- Store result in config for later validation

### 2.3 STT backend dependency checks

**Files:** `agentwire/onboarding.py`

When user selects STT backend, verify dependencies:

**whisperkit:**
- Check for `whisperkit-cli` binary
- Check for MacWhisper models directory
- If missing: Provide download link to MacWhisper (https://goodsnooze.gumroad.com/l/macwhisper)
- Show model discovery: list available models at `~/Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/`

**whispercpp:**
- Check for model file at specified path
- If missing: Show download instructions for whisper.cpp models

**openai:**
- Check for `OPENAI_API_KEY` environment variable
- If missing: Show instructions to set it

### 2.4 Add dependency summary at end of init

Before writing config, show summary:

```
✓ Python 3.12.0 (required: >=3.10)
✓ ffmpeg installed
✗ whisperkit-cli not found
  → Install MacWhisper: https://goodsnooze.gumroad.com/l/macwhisper
  → Or choose different STT backend

Continue anyway? [y/N]
```

## Wave 3: say/remote-say Script Installation

### 3.1 Create executable shell scripts

**Files:** `agentwire/scripts/say`, `agentwire/scripts/remote-say`

**say:**
```bash
#!/bin/bash
# Local TTS playback via agentwire CLI
agentwire say "$@"
```

**remote-say:**
```bash
#!/bin/bash
# Remote TTS via portal (auto-detects room from AGENTWIRE_ROOM or tmux session)
room="${AGENTWIRE_ROOM:-$(tmux display-message -p '#S' 2>/dev/null)}"
if [ -z "$room" ]; then
  echo "Error: Not in a tmux session and AGENTWIRE_ROOM not set" >&2
  exit 1
fi
agentwire say --room "$room" "$@"
```

### 3.2 Install scripts during skills installation

**Files:** `agentwire/__main__.py` (cmd_skills_install)

- Detect installation location (pyenv vs system vs user)
- Copy scripts to appropriate bin directory:
  - pyenv: `~/.pyenv/versions/X.Y.Z/bin/`
  - system: `/usr/local/bin/` (requires sudo)
  - user: `~/.local/bin/` (add to PATH if needed)
- Make executable
- Verify they work: `say --version` should succeed

### 3.3 Add to package artifacts

**Files:** `pyproject.toml`

```toml
[tool.hatch.build.targets.wheel]
packages = ["agentwire"]
artifacts = [
    "agentwire/skills/*.md",
    "agentwire/sample_templates/*.yaml",
    "agentwire/scripts/say",
    "agentwire/scripts/remote-say",
]
```

## Wave 4: Remote Machine Setup Automation

### 4.1 Automated remote installation

**Files:** `agentwire/onboarding.py` (setup_remote_machine function)

When user adds a remote machine in init wizard, offer automated setup:

```
Machine 'devbox1' added successfully.

Set up AgentWire on devbox1 now? [Y/n]
  → Install agentwire package
  → Install skills and scripts
  → Configure portal_url
  → Test remote-say connectivity
```

Implementation:
- SSH to remote machine
- Detect Python version (exit if < 3.10 with upgrade instructions)
- Detect externally-managed environment (Ubuntu):
  - Recommend venv (better practice)
  - Create ~/.agentwire-venv automatically
  - Add activation to ~/.bashrc
  - Show alternative: --break-system-packages (if user prefers)
- Install: `pip install git+https://github.com/dotdevdotdev/agentwire.git`
- Create `~/.agentwire/config.yaml` with minimal config (TTS URL, projects dir)
- Create `~/.agentwire/portal_url` pointing to tunnel endpoint
- Run `agentwire skills install` on remote
- Verify: SSH and run `remote-say "test"`, check if portal receives it

### 4.2 Reverse tunnel setup

**Files:** `agentwire/onboarding.py`

For portal hosts, offer to create reverse tunnels:

```
Create reverse SSH tunnels for remote machines? [Y/n]

This allows workers to reach the portal via localhost:8765.

  devbox1: ssh -R 8765:localhost:8765 -N -f dev@134.122.35.134
  devbox2: ssh -R 8765:localhost:8765 -N -f dev@138.197.145.5

Keep tunnels running with autossh? [Y/n]
```

- Create tunnels automatically
- Offer autossh for persistence
- Verify tunnel works: `ssh dev@host "curl -k https://localhost:8765/health"`

## Wave 5: doctor Command Enhancements

### 5.1 Add dependency checks to doctor

**Files:** `agentwire/__main__.py` (cmd_doctor)

Add new check sections:

**Python version:**
```
Checking Python version...
  [ok] Python 3.12.0 (>=3.10 required)
```

**System dependencies:**
```
Checking system dependencies...
  [ok] ffmpeg: /opt/homebrew/bin/ffmpeg
  [!!] whisperkit-cli: not found
      → Install MacWhisper: https://goodsnooze.gumroad.com/l/macwhisper
```

**Scripts:**
```
Checking AgentWire scripts...
  [ok] say: /Users/jordan/.pyenv/versions/3.12.0/bin/say
  [!!] remote-say: not found
      → Run: agentwire skills install
```

**Hooks:**
```
Checking Claude Code hooks...
  [ok] Permission hook: ~/.claude/hooks/agentwire-permission.sh
  [!!] Skills not linked
      → Run: agentwire skills install
```

### 5.2 Add auto-fix for missing scripts

If say/remote-say missing, offer to install:

```
  [!!] say command not found

  Fix: Install say/remote-say scripts? [Y/n]
```

Run skills install if user confirms.

### 5.3 Remote machine validation

**Files:** `agentwire/__main__.py` (cmd_doctor)

For each remote machine:
- SSH and check agentwire is installed
- Check portal_url is set
- Test remote-say works
- Verify skills are installed

```
Checking remote machines...
  devbox1:
    [ok] SSH connectivity (34ms)
    [ok] agentwire installed (0.1.0)
    [!!] portal_url not set
        → Create: echo "https://localhost:8765" > ~/.agentwire/portal_url
    [!!] Skills not installed
        → Run: ssh dev@devbox1 "agentwire skills install"
```

## Wave 6: Documentation Updates

### 6.1 Add installation troubleshooting guide

**Files:** `docs/TROUBLESHOOTING.md` (new)

Sections:
- Python version errors (platform-specific fixes)
- Externally-managed environments (Ubuntu)
- Missing dependencies (ffmpeg, whisperkit-cli)
- PATH issues (~/.local/bin not in PATH)
- SSL certificate errors
- Remote machine connectivity

### 6.2 Update CLAUDE.md installation section

**Files:** `CLAUDE.md`

Add:
- Pre-requisites section (Python >=3.10, ffmpeg)
- Platform-specific notes (macOS vs Ubuntu)
- Common issues and quick fixes
- Link to full troubleshooting guide

### 6.3 Update README.md quick start

**Files:** `README.md`

Clarify:
- System requirements (Python version, dependencies)
- Platform-specific installation steps
- Expected install time (20-30 min first time, 5 min after)

## Wave 7: Platform-Specific Error Messages

### 7.1 Improve pip install errors

**Files:** `pyproject.toml`, setup.py metadata

Current:
```
ERROR: Package 'agentwire-dev' requires a different Python: 3.9.6 not in '>=3.10'
```

Can't change this (pip controlled), but we can:
- Add Python version check to `agentwire init`
- Add Python version check to `agentwire --version`
- Show helpful error before pip even runs (in README install instructions)

### 7.2 Detect externally-managed environments

**Files:** `agentwire/__main__.py` (new helper)

Detect Ubuntu externally-managed error before it happens:

```python
def check_pip_environment():
    """Check if we're in an externally-managed environment."""
    if sys.platform.startswith('linux'):
        # Check for EXTERNALLY-MANAGED marker
        marker = Path(sys.prefix) / "EXTERNALLY-MANAGED"
        if marker.exists():
            print("⚠️  Externally-managed Python environment detected (Ubuntu 24.04+)")
            print()
            print("Recommended approach - Use venv:")
            print("  python3 -m venv ~/.agentwire-venv")
            print("  source ~/.agentwire-venv/bin/activate")
            print("  pip install git+https://github.com/dotdevdotdev/agentwire.git")
            print()
            print("  Add to ~/.bashrc for persistence:")
            print("  echo 'source ~/.agentwire-venv/bin/activate' >> ~/.bashrc")
            print()
            print("Alternative (not recommended):")
            print("  pip3 install --break-system-packages git+https://...")
            print()
            return True
    return False
```

Show venv approach as primary method in README installation instructions for Ubuntu.

## Completion Criteria

- [ ] `agentwire init` checks Python version, ffmpeg, STT dependencies
- [ ] `agentwire init` offers automated remote machine setup
- [ ] `agentwire init` can create reverse tunnels automatically
- [ ] `agentwire skills install` installs say/remote-say scripts
- [ ] `agentwire doctor` validates all dependencies
- [ ] `agentwire doctor` can fix missing scripts/hooks
- [ ] `agentwire doctor` validates remote machine setup
- [ ] Installation time reduced to 20-30 minutes for first-timers
- [ ] Documentation covers all platform-specific issues from case study

## Technical Notes

**Key insight from case study:**

The onboarding wizard exists and works well for configuration, but it doesn't validate that the configuration will actually work. Users end up with a config.yaml that references `whisperkit` but they don't have whisperkit-cli installed, or they select Chatterbox TTS but never get the URL.

**Solution:**

Make init wizard **validate dependencies before writing config**, not after portal fails to start.

**Testing checklist:**

After implementation, test on:
- [ ] Fresh macOS (M-series) with system Python 3.9
- [ ] Fresh Ubuntu 24.04 (externally-managed)
- [ ] Remote Ubuntu machine via SSH
- [ ] Verify complete install takes < 30 minutes
- [ ] Verify `agentwire doctor` catches all issues from case study

## Migration Notes

Existing users who already struggled through installation:
- `agentwire doctor` will find their missing dependencies
- `agentwire skills install` will add missing scripts
- No config changes needed
