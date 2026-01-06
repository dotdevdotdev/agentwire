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

- [x] Create `detect_remote_python_version()` helper function
- [x] Create `check_remote_externally_managed()` helper function
- [x] Create `setup_remote_machine()` that:
  - Checks Python version via SSH (requires >= 3.10)
  - Detects externally-managed environments (Ubuntu)
  - Recommends venv for Ubuntu (creates ~/.agentwire-venv, adds to bashrc)
  - Installs agentwire package via pip/venv
  - Creates config files via `setup_remote_machine_config()`
  - Installs skills and scripts
  - Verifies remote-say command exists
- [x] Integrate into onboarding wizard (Section 7: Remote Machines)
- [x] Show detailed progress and status during installation

### 4.2 Reverse tunnel setup

**Files:** `agentwire/onboarding.py`

- [x] Create `create_reverse_tunnel()` function that:
  - Creates SSH reverse tunnel: `ssh -R 8765:localhost:8765 -N -f user@host`
  - Verifies tunnel with health check
  - Returns success/failure status
- [x] Create `offer_autossh_setup()` function that:
  - Checks for autossh availability
  - Shows autossh command for persistence
  - Provides platform-specific installation instructions
- [x] Integrate into onboarding wizard after successful remote setup
- [x] Offer tunnel creation per machine (default: Yes)
- [x] Offer autossh setup after tunnel creation

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

- [x] Sections:
  - [x] Python version errors (platform-specific fixes)
  - [x] Externally-managed environments (Ubuntu)
  - [x] Missing dependencies (ffmpeg, whisperkit-cli)
  - [x] PATH issues (~/.local/bin not in PATH)
  - [x] SSL certificate errors
  - [x] Remote machine connectivity

### 6.2 Update CLAUDE.md installation section

**Files:** `CLAUDE.md`

- [x] Add:
  - [x] Pre-requisites section (Python >=3.10, ffmpeg)
  - [x] Platform-specific notes (macOS vs Ubuntu)
  - [x] Common issues and quick fixes
  - [x] Link to full troubleshooting guide

### 6.3 Update README.md quick start

**Files:** `README.md`

- [x] Clarify:
  - [x] System requirements (Python version, dependencies)
  - [x] Platform-specific installation steps
  - [x] Expected install time (20-30 min first time, 5 min after)

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

- [x] `agentwire init` checks Python version, ffmpeg, STT dependencies
- [x] `agentwire init` offers automated remote machine setup
- [x] `agentwire init` can create reverse tunnels automatically
- [x] `agentwire skills install` installs say/remote-say scripts
- [x] `agentwire doctor` validates all dependencies
- [x] `agentwire doctor` can fix missing scripts/hooks
- [x] `agentwire doctor` validates remote machine setup
- [ ] Installation time reduced to 20-30 minutes for first-timers
- [x] Documentation covers all platform-specific issues from case study

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
