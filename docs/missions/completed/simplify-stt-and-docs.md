# Mission: Simplify STT to Remote-Only + Gut Installation Docs

Simplify STT to a single `remote` backend (URL-based) and remove installation/onboarding documentation that's constantly changing.

## Context

**Current state:**
- 4 STT backends: `whisperkit`, `whispercpp`, `remote`, `none`
- Complex onboarding wizard with STT backend selection, dependency checks
- ~1200 lines of installation/troubleshooting docs that need constant updates
- Platform-specific logic scattered throughout

**Target state:**
- 2 STT backends: `remote` (default), `none`
- Simple config: just `stt.url` pointing to agentwire-stt (Docker, cloud, wherever)
- Minimal docs focused on what works, not installation edge cases
- agentwire-stt can run anywhere - Docker, cloud, GPU server - portal just needs URL

**Why this works:**
- Portal hold-to-talk → `/transcribe` → RemoteSTT → URL → agentwire-stt
- agentwire-stt uses faster-whisper, can run on any hardware
- One solution that scales: local Docker, remote GPU, cloud service

---

## Wave 1: Delete STT Backend Files

**Task 1.1: Delete local STT backends**
- Delete `agentwire/stt/openai.py`
- Delete `agentwire/stt/whisperkit.py`
- Delete `agentwire/stt/whispercpp.py`

**Keep:**
- `agentwire/stt/base.py` - base class
- `agentwire/stt/remote.py` - the only real backend
- `agentwire/stt/none.py` - for disabling STT
- `agentwire/stt/stt_server.py` - the actual STT service
- `agentwire/stt/__init__.py` - will be updated

---

## Wave 2: Simplify STT Code

**Task 2.1: Update `agentwire/stt/__init__.py`**
- Remove imports for WhisperKitSTT, WhisperCppSTT, OpenAISTT
- Remove from `__all__`
- Simplify `get_stt_backend()`:
  - `remote` → RemoteSTT (requires url)
  - `none` → NoSTT
  - Any other value → error

**Task 2.2: Update `agentwire/config.py`**
- Delete `_default_stt_backend()` function
- Simplify `STTConfig`:
  ```python
  @dataclass
  class STTConfig:
      url: str | None = None  # STT server URL (e.g., http://localhost:8100)
      timeout: int = 30
  ```
- Remove: `backend`, `model_path`, `language` fields
- Update `load_config()` to use simplified STTConfig

**Task 2.3: Update `agentwire/server.py`**
- Update STT initialization to use URL-based approach
- Remove any backend selection logic
- If `stt.url` is set → RemoteSTT, else → NoSTT

---

## Wave 3: Simplify Onboarding Wizard

**Task 3.1: Gut STT section in `agentwire/onboarding.py`**
- Remove `check_stt_dependencies()` function (~35 lines)
- Remove `get_stt_dependency_fix()` function (~15 lines)
- Remove STT backend selection (Section 5)
- Replace with simple URL prompt:
  ```
  STT URL (leave empty to disable): http://localhost:8100
  ```
- Remove `stt_backend` from config dict, use `stt_url`
- Update generated config to use simplified format

**Task 3.2: Update `agentwire/skills/init.md`**
- Remove STT backend selection section
- Simplify to just URL configuration
- Remove WhisperKit/whisper.cpp references

---

## Wave 4: Delete/Simplify Documentation

**Task 4.1: Delete installation/troubleshooting docs (USER ACTION)**
- Delete `docs/installation.md` (163 lines)
- Delete `docs/TROUBLESHOOTING.md` (574 lines)
- Delete `docs/installation-case-study.md` (448 lines)
- Delete `docs/cli-review.md` (task doc, marked "RESOLVED")

**Task 4.2: Simplify `docs/configuration.md`**
- Remove all STT backend details
- Simplify STT section to:
  ```yaml
  stt:
    url: "http://localhost:8100"  # URL to agentwire-stt server
    timeout: 30
  ```
- Remove OPENAI_API_KEY, model_path references

**Task 4.3: Update `README.md`**
- Remove STT backends table
- Simplify to: "STT requires agentwire-stt running somewhere (Docker, cloud, etc.)"
- Update example config

**Task 4.4: Update `docs/deployment.md`**
- Remove STT backend selection examples
- Focus on Docker deployment with agentwire-stt

**Task 4.5: Update `docs/architecture.md`**
- Remove WhisperKit/whisper.cpp mentions

---

## Wave 5: Update Example Configs

**Task 5.1: Update `examples/config.yaml`**
- Simplify STT section to just url/timeout

**Task 5.2: Update `examples/config-docker.yaml`**
- Already uses remote, just simplify comments

**Task 5.3: Update `examples/config-distributed.yaml`** (if exists)
- Same simplification

---

## Completion Criteria

- [ ] Only `remote` and `none` STT backends exist
- [ ] `agentwire/stt/` contains only: `__init__.py`, `base.py`, `remote.py`, `none.py`, `stt_server.py`
- [ ] STTConfig has only `url` and `timeout` fields
- [ ] Onboarding just asks for STT URL (no backend selection)
- [ ] No WhisperKit/whisper.cpp/OpenAI references in active code
- [ ] Installation docs deleted (installation.md, TROUBLESHOOTING.md, installation-case-study.md, cli-review.md)
- [ ] README and deployment docs simplified
