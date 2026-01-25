<!-- Run this command to execute:
/ralph-loop @docs/prompts/ralphloop/codebase-quality-review.md --completion-promise "COMPLETE" --max-iterations 20
-->

# Codebase Quality Review for Open Source Release

## Task
Review and improve the AgentWire codebase (~17.5k lines, 41 Python files) for open source release. Focus on extracting reusable utilities from duplicated patterns and adding developer documentation.

**Pre-launch project:** No backwards compatibility needed. Change things completely.

## Success Criteria
When ALL of the following are true, output <promise>COMPLETE</promise>:
- [ ] `agentwire/utils/` directory exists with extracted utilities
- [ ] Subprocess calls consolidated (currently 370+ scattered across 13 files)
- [ ] JSON/YAML load/save consolidated (currently 71 occurrences)
- [ ] All public functions have Google-style docstrings
- [ ] `ruff check agentwire/` passes with no errors
- [ ] CONTRIBUTING.md exists with dev setup and code patterns
- [ ] progress.txt shows all files reviewed

## Codebase Inventory (actual line counts)

**Large files (split candidates):**
- `__main__.py` - 5,762 lines (CLI commands - very large)
- `server.py` - 3,050 lines (WebSocket server)
- `onboarding.py` - 1,469 lines (setup wizard)

**Medium files (review for DRY):**
- `cli_safety.py` - 517 lines
- `pane_manager.py` - 484 lines
- `config.py` - 404 lines (good pattern to follow)
- `listen.py` - 393 lines
- `history.py` - 394 lines
- `tunnels.py` - 382 lines
- `validation.py` - 362 lines (good pattern to follow)
- `voiceclone.py` - 309 lines
- `errors.py` - 224 lines (excellent pattern to follow)

**Smaller files:**
- `tts_server.py` - 214 lines
- `network.py` - 205 lines
- `worktree.py` - 197 lines
- `projects.py` - 235 lines
- `init_agentwire.py` - 189 lines
- `project_config.py` - 171 lines

**Subdirectories:**
- `agents/tmux.py` - 400 lines, `agents/base.py` - 96 lines
- `tts/runpod_backend.py` - 231 lines, `tts/runpod_handler.py` - 294 lines
- `tts/chatterbox.py` - 96 lines, `tts/base.py` - 33 lines
- `stt/whisperkit.py` - 90 lines, `stt/base.py` - 26 lines

## Specific DRY Violations Found

### Priority 1: Extract to `agentwire/utils/subprocess.py`
370+ subprocess calls across 13 files with repeated patterns:
- `__main__.py` (166 calls), `server.py` (37), `onboarding.py` (44)
- `pane_manager.py` (47), `listen.py` (19), `voiceclone.py` (12)

Create helpers:
```python
def run_command(cmd: list[str], capture: bool = True, timeout: int = 30) -> tuple[int, str, str]:
    """Run subprocess with consistent error handling."""

def run_command_async(cmd: list[str]) -> subprocess.Popen:
    """Start background process."""
```

### Priority 2: Extract to `agentwire/utils/file_io.py`
71 JSON/YAML load/dump occurrences with duplicated try-except:
```python
def load_json(path: Path, default: dict = None) -> dict:
    """Load JSON with error context."""

def save_json(path: Path, data: dict) -> None:
    """Save JSON atomically."""

def load_yaml(path: Path) -> dict:
    """Load YAML config file."""
```

### Priority 3: Extract to `agentwire/utils/paths.py`
68 Path.home() calls scattered throughout:
```python
def agentwire_dir() -> Path:
    """Return ~/.agentwire, creating if needed."""

def config_path() -> Path:
    """Return path to config.yaml."""

def logs_dir() -> Path:
    """Return path to logs directory."""
```

### Priority 4: Consolidate audio recording
`listen.py` and `voiceclone.py` have nearly identical recording infrastructure:
- Both write to `/tmp/agentwire-*.wav`
- Both have debug logging to `/tmp/`
- Both use system notifications and beeps
- Extract common recording logic to `agentwire/utils/audio.py`

### Priority 5: Fix TTS session management
`tts/chatterbox.py` and `tts/runpod_backend.py` have identical `_get_session()`:
- Move to `tts/base.py` as shared method

## Approach

### Phase 1: Create utilities (iterations 1-5)
1. Create `agentwire/utils/__init__.py`
2. Create `subprocess.py` with `run_command()`, `run_command_async()`
3. Create `file_io.py` with `load_json()`, `save_json()`, `load_yaml()`
4. Create `paths.py` with path helpers
5. Commit: "feat: add utility modules for subprocess, file I/O, paths"

### Phase 2: Migrate callers (iterations 6-12)
For each file using duplicated patterns:
1. Import new utilities
2. Replace duplicated code with utility calls
3. Add docstrings to public functions while editing
4. Run `ruff check agentwire/` after each file
5. Commit: "refactor(filename): use utilities, add docstrings"

### Phase 3: Documentation (iterations 13-15)
1. Add module docstrings to all files
2. Create CONTRIBUTING.md with:
   - Dev setup (uv, portal --dev)
   - Code patterns (utilities, error classes)
   - Testing approach
   - PR guidelines
3. Commit: "docs: add module docstrings and CONTRIBUTING.md"

### Phase 4: Cleanup (iterations 16-20)
1. Run `ruff check agentwire/` and fix all issues
2. Search for TODO/FIXME - resolve or remove
3. Final review of progress.txt
4. Commit: "chore: fix linting, resolve TODOs"

## State Tracking
Track in progress.txt:
```
## Utilities Created
- [ ] agentwire/utils/subprocess.py
- [ ] agentwire/utils/file_io.py
- [ ] agentwire/utils/paths.py
- [ ] agentwire/utils/audio.py (if needed)

## Files Migrated to Utilities
- [ ] __main__.py - subprocess, file_io
- [ ] server.py - subprocess, file_io
- [ ] pane_manager.py - subprocess
- [ ] onboarding.py - subprocess, file_io
- [ ] listen.py - subprocess, paths
- [ ] voiceclone.py - subprocess, paths
- [ ] history.py - file_io
- [ ] tunnels.py - subprocess

## Docstrings Added
- [ ] __main__.py (large - track functions done)
- [ ] server.py
- [ ] config.py (already good, verify)
- [ ] pane_manager.py
- [ ] tunnels.py
- [ ] agents/tmux.py

## Ruff Status
- Last run: (timestamp)
- Errors: (count)
- Fixed: (list)
```

## Good Patterns to Follow (already in codebase)

**errors.py** - Excellent error classes:
```python
@dataclass
class AgentWireError:
    """Base error with WHAT/WHY/HOW structure."""
    what: str
    why: str
    how: str
```

**config.py** - Clean dataclass config:
```python
@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
```

**validation.py** - Structured validation:
```python
def validate_config(config: Config) -> list[ValidationResult]:
    """Returns warnings and errors with fix suggestions."""
```

## Docstring Format (Google Style)
```python
def function_name(arg1: str, arg2: int = 10) -> dict:
    """Brief one-line description.

    Longer description if needed explaining purpose
    and important details.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2. Defaults to 10.

    Returns:
        Description of return value.

    Raises:
        ValueError: When arg1 is empty.
    """
```

## Constraints
- Don't change functionality, only improve code quality
- Don't add new features or capabilities
- Use existing code style from config.py, errors.py, validation.py
- Commit after each logical group of changes
- Comments explain "why", not "what"
- Run ruff after each file change

## If Stuck
After 5 iterations without progress:
- Document blocker in BLOCKED.md with:
  - What you tried
  - What's blocking
  - What decision needs human input
- Output: <promise>BLOCKED</promise>
