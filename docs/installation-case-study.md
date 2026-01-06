# AgentWire First-Time Installation Case Study

**Date:** January 6, 2026
**Setup:** Mac Mini (M-series) as portal host, 2 Ubuntu remote devboxes (DigitalOcean)
**User Level:** Technical, familiar with CLI and SSH
**Time Taken:** ~2 hours for full setup including troubleshooting

## Overview

This case study documents a first-time AgentWire installation across 3 machines, capturing every issue encountered and how they were resolved. The goal is to identify pain points and improve the installation experience.

## System Configuration

### Portal Host (Mac Mini)

- **OS:** macOS Sequoia (Darwin 24.5.0)
- **Python:** 3.9.6 (system) → upgraded to 3.12.0 via pyenv
- **Role:** Portal server, orchestrator session

### Remote Workers

- **devbox1:** Ubuntu on DigitalOcean (134.122.35.134)
- **devbox2:** Ubuntu on DigitalOcean (138.197.145.5)
- **Python:** 3.12.3 (system, externally managed)
- **Role:** Claude Code worker sessions

## Installation Timeline

### Phase 1: Initial Installation Attempt

**Issue #1: Python Version Incompatibility**

**Problem:**
```
ERROR: Package 'agentwire-dev' requires a different Python: 3.9.6 not in '>=3.10'
```

**Context:** Mac Mini had system Python 3.9.6, but agentwire requires Python 3.10+

**Solution:**
```bash
pyenv install 3.12.0
pyenv global 3.12.0
export PATH="$HOME/.pyenv/shims:$PATH"
eval "$(pyenv init -)"
pip3 install git+https://github.com/dotdevdotdev/agentwire.git
```

**Lesson:** Installation docs should check Python version upfront and provide clear upgrade instructions for macOS users (pyenv) and Linux users (apt/system package manager).

---

### Phase 2: Portal and Machine Configuration

**Issue #2: Missing Configuration File**

**Problem:** Portal wouldn't start with TTS/STT backends - no config.yaml

**Context:** First-time installation had no `~/.agentwire/config.yaml`

**Solution:** Manually created config.yaml with required sections:

```yaml
server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    enabled: true
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

tts:
  backend: "chatterbox"
  url: "https://tts.serverofdreams.com"
  default_voice: "dotdev"

stt:
  backend: "whisperkit"
  language: "en"
  model_path: "~/Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930"

projects:
  dir: "~/projects"
```

**Lesson:** `agentwire init` command should exist to create a starter config.yaml with sensible defaults and guide users through choices (TTS backend, voice, projects directory).

---

### Phase 3: Reverse SSH Tunnels

**Issue #3: Tunnel Setup Not Obvious**

**Problem:** User didn't realize reverse tunnels were needed for remote-say to work

**Context:** Documentation mentioned tunnels but wasn't clear they were mandatory for portal accessibility from devboxes

**Solution:** Manually created tunnels:
```bash
ssh -R 8765:localhost:8765 -N -f dev@134.122.35.134
ssh -R 8765:localhost:8765 -N -f dev@138.197.145.5
```

**Verification:**
```bash
ps aux | grep "ssh -R 8765"
```

**Lesson:**
- `agentwire machine add` should offer to create tunnels automatically
- `agentwire doctor` should detect missing tunnels and offer to create them
- Clear warning if portal won't be reachable from remote machines

---

### Phase 4: Remote Machine Setup

**Issue #4: Externally-Managed Python Environment (Ubuntu)**

**Problem:**
```
error: externally-managed-environment
× This environment is externally managed
```

**Context:** Ubuntu 24.04+ uses PEP 668 to prevent pip from modifying system Python

**Solution Used (not recommended):** Used `--break-system-packages` flag:
```bash
ssh dev@134.122.35.134 "pip3 install --break-system-packages git+https://github.com/dotdevdotdev/agentwire.git"
```

**Better Solution (recommended):** Create venv for isolation:
```bash
# On remote machine
python3 -m venv ~/.agentwire-venv
source ~/.agentwire-venv/bin/activate
pip install git+https://github.com/dotdevdotdev/agentwire.git

# Add to ~/.bashrc for persistence
echo 'source ~/.agentwire-venv/bin/activate' >> ~/.bashrc
```

**Lesson:** Installation wizard should guide Ubuntu users to create venv with automatic setup, making the better practice approach just as easy as --break-system-packages.

---

### Phase 5: Skills and Hooks Installation

**Issue #5: Skills Installation Path Confusion**

**Problem:** On devbox2, skills installed to `~/.local/bin` which wasn't in PATH

**Warning Message:**
```
WARNING: The script agentwire is installed in '/home/dev/.local/bin' which is not on PATH.
```

**Solution:**
- Installation worked despite warning
- Users should add to ~/.bashrc: `export PATH="$HOME/.local/bin:$PATH"`

**Actual Installation Locations:**
- **Mac Mini:** `/Users/jordan/.pyenv/versions/3.12.0/lib/python3.12/site-packages`
- **devbox1:** `/usr/local/lib/python3.12/dist-packages` (system-wide via --break-system-packages)
- **devbox2:** `/home/dev/.local/lib/python3.12/site-packages` (user install)

**Skills Installation Output:**
```
Linked skills: ~/.claude/skills/agentwire -> <package_location>/agentwire/skills
Installed permission hook to ~/.claude/hooks/agentwire-permission.sh
Claude Code skills installed. Available commands:
  /sessions, /send, /output, /spawn, /new, /kill, /status, /jump
```

**Lesson:** Detect if `~/.local/bin` is in PATH and provide actionable fix command if missing.

---

### Phase 6: Speech-to-Text (STT) Setup

**Issue #6: Missing ffmpeg Dependency**

**Problem:** Push-to-talk button didn't work, portal logs showed:
```
ERROR agentwire.stt.whisperkit: whisperkit-cli not found. Install WhisperKit.
```

**Context:** WhisperKit STT backend requires:
- MacWhisper app (for models)
- whisperkit-cli command-line tool
- ffmpeg (for audio processing)

**Solution:**
```bash
brew install ffmpeg
brew install whisperkit-cli
```

**Model Path Discovery:**
```bash
ls -la ~/Library/Application\ Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/
# Found: openai_whisper-large-v3-v20240930
```

**Lesson:**
- STT setup should check for dependencies upfront
- Provide clear instructions for installing MacWhisper (download link)
- Auto-detect available models and suggest paths
- Consider simpler default: OpenAI API (just needs API key) vs local setup

---

### Phase 7: Text-to-Speech (TTS) Setup

**Issue #7: Voice List Not Appearing**

**Problem:** Portal showed no voices in dropdown

**Context:** Initially used wrong default voice "bashbunni" which was being removed

**Solution:** Changed default_voice to "dotdev":
```yaml
tts:
  backend: "chatterbox"
  url: "https://tts.serverofdreams.com"
  default_voice: "dotdev"
```

**Verification:**
```bash
curl -s https://tts.serverofdreams.com/voices
# Returns: {"voices":[{"name":"dotdev","duration":42.47},...]}
```

**Lesson:** Portal should gracefully handle missing voices and show error if default_voice doesn't exist.

---

### Phase 8: SSL/HTTPS Configuration

**Issue #8: Portal Running on HTTP, remote-say Expected HTTPS**

**Problem:**
```
Error: Exit code 1
Failed to send to portal: <urlopen error [SSL] record layer failure (_ssl.c:1000)>
```

**Context:**
- `agentwire say --room` hardcodes `https://` in portal URL
- Portal was running on HTTP (no SSL config)
- Self-signed certificates existed but weren't being used

**Solution:**

Generated SSL certificates:
```bash
agentwire generate-certs
# Created: ~/.agentwire/cert.pem and key.pem
```

Added SSL config to config.yaml:
```yaml
server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    enabled: true
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"
```

Created portal_url file:
```bash
echo "https://localhost:8765" > ~/.agentwire/portal_url
```

Restarted portal

**Verification:**
```bash
curl -k https://localhost:8765/health
# {"status": "ok", "version": "0.1.0"}
```

**Lesson:**
- SSL should be enabled by default
- `agentwire init` should run generate-certs automatically
- Portal should detect missing SSL config and warn user
- Better: Use HTTP by default for localhost, HTTPS only for remote access

---

### Phase 9: Shell Script Installation

**Issue #9: Missing say and remote-say Commands**

**Problem:** Claude tried to use remote-say command but got:
```
Error: Exit code 127
(eval):1: command not found: remote-say
```

**Context:** Documentation mentioned `say` and `remote-say` scripts but they weren't installed anywhere

**Root Cause:** These scripts don't exist in the repository and aren't installed by `agentwire skills install`

**Solution:** Manually created wrapper scripts:

`say`:
```bash
#!/bin/bash
# Local TTS playback
agentwire say "$@"
```

`remote-say`:
```bash
#!/bin/bash
# Remote TTS via portal
room="${AGENTWIRE_ROOM:-$(tmux display-message -p '#S')}"
agentwire say --room "$room" "$@"
```

**Installation:**
```bash
# Mac Mini
cp say remote-say ~/.pyenv/versions/3.12.0/bin/
chmod +x ~/.pyenv/versions/3.12.0/bin/{say,remote-say}

# devbox1 and devbox2
scp say remote-say dev@<host>:/tmp/
ssh dev@<host> "sudo mv /tmp/{say,remote-say} /usr/local/bin/ && sudo chmod +x /usr/local/bin/{say,remote-say}"
```

**Lesson:**
- `agentwire skills install` should install say and remote-say scripts to PATH
- Detect system type (pyenv vs system Python) and install to appropriate location
- Verify they're executable and in PATH after installation

---

### Missing Configuration Files on Remote Machines

**Issue #10: No portal_url on Devboxes**

**Problem:** Not discovered during initial setup, but would cause issues when workers try to use remote-say

**Required Setup** (not done, but documented for completeness):
```bash
# On each devbox
mkdir -p ~/.agentwire
echo "https://localhost:8765" > ~/.agentwire/portal_url
```

**Lesson:** Machine setup should automatically configure portal_url on remote workers pointing to tunnel endpoint.

---

## Working Configuration Summary

### Mac Mini (~/.agentwire/config.yaml)

```yaml
server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    enabled: true
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

tts:
  backend: "chatterbox"
  url: "https://tts.serverofdreams.com"
  default_voice: "dotdev"

stt:
  backend: "whisperkit"
  language: "en"
  model_path: "~/Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930"

projects:
  dir: "~/projects"
```

### devbox1 and devbox2 (~/.agentwire/config.yaml)

```yaml
tts:
  backend: "chatterbox"
  url: "https://tts.serverofdreams.com"
  default_voice: "dotdev"

projects:
  dir: "~/projects"
```

### Machines Configuration (Mac Mini ~/.agentwire/machines.json)

```json
{
  "machines": [
    {
      "id": "devbox1",
      "host": "134.122.35.134",
      "user": "dev"
    },
    {
      "id": "devbox2",
      "host": "138.197.145.5",
      "user": "dev"
    }
  ]
}
```

---

## Time Breakdown

| Phase | Time | Notes |
|-------|------|-------|
| Initial pip install attempt | 5 min | Hit Python version error |
| Python upgrade (pyenv) | 10 min | Install 3.12.0, set global |
| Install agentwire (Mac Mini) | 3 min | Successful after Python fix |
| Configure portal | 15 min | Created config.yaml manually |
| Set up reverse tunnels | 5 min | Manual ssh -R commands |
| Install on devbox1 | 5 min | --break-system-packages |
| Install on devbox2 | 5 min | Same as devbox1 |
| Skills installation | 5 min | All 3 machines |
| Add machines to portal | 3 min | agentwire machine add |
| STT troubleshooting | 20 min | ffmpeg, whisperkit-cli, config |
| TTS troubleshooting | 10 min | Change default voice |
| SSL setup | 15 min | Generate certs, configure, restart |
| say/remote-say scripts | 15 min | Create and install on all machines |
| Testing and verification | 10 min | End-to-end tests |
| **Total** | **~2 hours** | With external assistance |

**Estimated Time with Improved Install:** 20-30 minutes for experienced users, 45-60 minutes for first-timers

---

## What Went Well

✅ **Python package installation:** Once Python version was fixed, pip install worked flawlessly
✅ **Skills installation:** `agentwire skills install` worked perfectly on all machines
✅ **Portal startup:** Once config.yaml existed, portal started reliably
✅ **TTS server:** External TTS server (tts.serverofdreams.com) worked without any setup
✅ **Documentation:** CLAUDE.md file was comprehensive and accurate for reference

---

## Conclusion

The core agentwire functionality is solid, but the first-time installation experience has significant friction points:

❌ **No initialization wizard** - users must manually create config files
❌ **Undocumented dependencies** - ffmpeg, whisperkit-cli, MacWhisper not mentioned in install steps
❌ **Missing scripts** - say/remote-say referenced but not installed
❌ **SSL confusion** - not clear whether HTTP or HTTPS should be used
❌ **Platform-specific issues** - Python version, externally-managed environments not addressed

With the recommended improvements (init wizard, doctor command, better error messages, verification script), installation time could be reduced by 60-70% while dramatically improving the first-time user experience.

The fact that this installation succeeded with external assistance suggests the documentation is good for debugging, but the automated setup needs significant enhancement for a smooth installation experience.
