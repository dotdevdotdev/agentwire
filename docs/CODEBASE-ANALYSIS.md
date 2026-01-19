# AgentWire Codebase Analysis

> Temporary analysis report for open source release prep. Delete after code quality review is complete.

**Generated:** 2026-01-19
**Status:** Pre-refactor baseline
**Total:** ~17,455 lines of Python across 41 files

## File Inventory

### Large Files (Decomposition Candidates)

| File | Lines | Purpose | Notes |
|------|-------|---------|-------|
| `__main__.py` | 5,762 | CLI entry point | Very large - contains all CLI commands |
| `server.py` | 3,050 | WebSocket portal server | Large - HTTP handlers, session logic |
| `onboarding.py` | 1,469 | Interactive setup wizard | Moderate - self-contained |

### Medium Files (Review for DRY)

| File | Lines | Purpose | DRY Issues |
|------|-------|---------|------------|
| `cli_safety.py` | 517 | Damage control patterns | Clean |
| `pane_manager.py` | 484 | Tmux pane management | 47 subprocess calls |
| `config.py` | 404 | Configuration management | **Good pattern to follow** |
| `listen.py` | 393 | Voice listening/recording | 19 subprocess, audio patterns |
| `history.py` | 394 | Conversation history | 6 JSON loads, SSH commands |
| `tunnels.py` | 382 | SSH tunnel management | 7 subprocess calls |
| `validation.py` | 362 | Config validation | **Good pattern to follow** |
| `voiceclone.py` | 309 | Voice recording/upload | 12 subprocess, shares patterns with listen.py |
| `errors.py` | 224 | Error classes | **Excellent pattern to follow** |

### Smaller Files

| File | Lines | Purpose |
|------|-------|---------|
| `tts_server.py` | 214 | TTS HTTP server |
| `network.py` | 205 | Network topology helper |
| `projects.py` | 235 | Project discovery |
| `worktree.py` | 197 | Git worktree management |
| `init_agentwire.py` | 189 | Setup wizard |
| `project_config.py` | 171 | Project-level config |

### Subdirectory Files

| File | Lines | Purpose |
|------|-------|---------|
| `agents/tmux.py` | 400 | Tmux backend implementation |
| `agents/base.py` | 96 | Abstract agent backend |
| `tts/runpod_backend.py` | 231 | RunPod TTS backend |
| `tts/runpod_handler.py` | 294 | RunPod serverless handler |
| `tts/chatterbox.py` | 96 | Chatterbox TTS backend |
| `tts/base.py` | 33 | Abstract TTS backend |
| `stt/whisperkit.py` | 90 | WhisperKit STT backend |
| `stt/base.py` | 26 | Abstract STT backend |

## DRY Violations (Quantified)

### Priority 1: Subprocess Calls (370+ occurrences)

Scattered across 13 files with repeated patterns (capture output, error handling, timeout):

| File | Count | Pattern |
|------|-------|---------|
| `__main__.py` | 166 | Mixed sync/async subprocess |
| `pane_manager.py` | 47 | Tmux commands |
| `onboarding.py` | 44 | System checks |
| `server.py` | 37 | Tmux commands via CLI |
| `listen.py` | 19 | Audio/ffmpeg commands |
| `voiceclone.py` | 12 | Audio recording |
| `init_agentwire.py` | 11 | Setup commands |
| `worktree.py` | 9 | Git commands |
| `agents/tmux.py` | 8 | Tmux backend |
| `tunnels.py` | 7 | SSH commands |
| `history.py` | 6 | SSH commands |
| `projects.py` | 3 | Git commands |
| `stt/whisperkit.py` | 1 | Whisper CLI |

**Recommendation:** Create `agentwire/utils/subprocess.py`
```python
def run_command(cmd: list[str], capture: bool = True, timeout: int = 30) -> tuple[int, str, str]
def run_command_async(cmd: list[str]) -> subprocess.Popen
```

### Priority 2: JSON/YAML Load/Dump (71 occurrences)

Duplicated try-except patterns for file I/O:

| File | Count | Operations |
|------|-------|------------|
| `__main__.py` | 37 | JSON load/dump for session state |
| `server.py` | 10 | JSON responses, config loading |
| `history.py` | 6 | JSON history files |
| `onboarding.py` | 3 | Config writing |
| `tunnels.py` | 3 | Tunnel state |
| `cli_safety.py` | 2 | Pattern loading |
| + hooks | ~10 | Various |

**Recommendation:** Create `agentwire/utils/file_io.py`
```python
def load_json(path: Path, default: dict = None) -> dict
def save_json(path: Path, data: dict) -> None
def load_yaml(path: Path) -> dict
```

### Priority 3: Path Operations (68 Path.home() calls)

No centralized path utilities:

| File | Count |
|------|-------|
| `__main__.py` | 22 |
| `config.py` | 9 |
| `server.py` | 4 |
| `listen.py` | 4 |
| Others | 29 |

**Recommendation:** Create `agentwire/utils/paths.py`
```python
def agentwire_dir() -> Path
def config_path() -> Path
def logs_dir() -> Path
def voices_dir() -> Path
def uploads_dir() -> Path
```

### Priority 4: Audio Recording (Duplicated Infrastructure)

`listen.py` and `voiceclone.py` share nearly identical patterns:
- Both write to `/tmp/agentwire-*.wav`
- Both have debug logging to `/tmp/` files
- Both use system notifications and beeps
- Both manage temp file cleanup

**Recommendation:** Extract to `agentwire/utils/audio.py`

### Priority 5: HTTP Session Management (Duplicated in TTS)

`tts/chatterbox.py` and `tts/runpod_backend.py` have identical `_get_session()`:
```python
async def _get_session(self) -> aiohttp.ClientSession:
    if self._session is None or self._session.closed:
        self._session = aiohttp.ClientSession()
    return self._session
```

**Recommendation:** Move to `tts/base.py` as shared method

## Good Patterns (Reference These)

### errors.py - Error Classes

Excellent WHAT/WHY/HOW structure:
```python
@dataclass
class AgentWireError:
    """Base error with actionable structure."""
    what: str  # What happened
    why: str   # Why it happened
    how: str   # How to fix it

# Factory functions for common errors
def tunnel_not_running(machine: str) -> AgentWireError:
    return AgentWireError(
        what=f"Tunnel to {machine} is not running",
        why="The SSH tunnel process has stopped or was never started",
        how=f"Run: agentwire tunnels up"
    )
```

### config.py - Dataclass Configuration

Clean nested dataclasses with defaults:
```python
@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    ssl: SSLConfig = field(default_factory=SSLConfig)

@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    # ...

# Lazy singleton
_config: Config | None = None
def get_config() -> Config:
    global _config
    if _config is None:
        _config = _load_config()
    return _config
```

### validation.py - Structured Validation

Returns warnings vs errors with fix suggestions:
```python
@dataclass
class ValidationResult:
    level: Literal["warning", "error"]
    message: str
    fix: str | None = None

def validate_config(config: Config) -> list[ValidationResult]:
    results = []
    if not config.tts.backend:
        results.append(ValidationResult(
            level="warning",
            message="No TTS backend configured",
            fix="Set tts.backend in ~/.agentwire/config.yaml"
        ))
    return results
```

## Documentation State

### Good Coverage
- `errors.py` - Excellent docstrings
- `config.py` - Clear dataclass definitions
- `validation.py` - Contextual error messages

### Needs Docstrings
- `__main__.py` - 5,762 lines, minimal docstrings
- `server.py` - 3,050 lines, sparse documentation
- `pane_manager.py` - Complex tmux logic undocumented
- `agents/tmux.py` - Backend interface undocumented

### Missing Module Docstrings
Most files lack module-level docstrings explaining their purpose.

## Lint Status

Run `ruff check agentwire/` for current baseline. Common issues:
- Unused imports
- Line length violations
- Missing type annotations in some files

## Proposed Utility Structure

```
agentwire/
├── utils/
│   ├── __init__.py
│   ├── subprocess.py    # run_command(), run_command_async()
│   ├── file_io.py       # load_json(), save_json(), load_yaml()
│   ├── paths.py         # agentwire_dir(), config_path(), etc.
│   └── audio.py         # Recording infrastructure (if extracted)
├── __main__.py          # CLI (uses utils)
├── server.py            # Portal (uses utils)
└── ...
```

## Action Items for Code Quality Review

1. **Create utilities** (Phase 1)
   - `utils/subprocess.py`
   - `utils/file_io.py`
   - `utils/paths.py`

2. **Migrate callers** (Phase 2)
   - Start with smaller files (tunnels.py, history.py)
   - Then medium files (pane_manager.py, listen.py)
   - Finally large files (__main__.py, server.py)

3. **Add docstrings** (Phase 3)
   - Follow Google style
   - Focus on public functions
   - Reference errors.py, config.py patterns

4. **Create CONTRIBUTING.md** (Phase 4)
   - Dev setup instructions
   - Code patterns to follow
   - PR guidelines

## Related Files

- `docs/prompts/ralphloop/codebase-quality-review.md` - Ralph loop prompt for this work
- `progress.txt` - Tracking state for the review
