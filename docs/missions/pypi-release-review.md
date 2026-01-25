# Mission: PyPI Release Review

> Comprehensive codebase review to ensure production-readiness for PyPI release.

## Objective

Audit the entire codebase for quality, security, documentation accuracy, and removal of any legacy/deprecated code paths before publishing to PyPI.

## Review Checklist

### 1. Documentation Accuracy

- [ ] `CLAUDE.md` - Verify all CLI commands are accurate and up-to-date
- [ ] `docs/PORTAL.md` - Verify API endpoints and UI descriptions match implementation
- [ ] `docs/architecture.md` - Verify architecture descriptions are current
- [ ] `docs/TROUBLESHOOTING.md` - Verify troubleshooting steps work
- [ ] `docs/SHELL_ESCAPING.md` - Verify escaping documentation is accurate
- [ ] `docs/runpod-tts.md` - Verify RunPod TTS setup instructions
- [ ] `docs/tts-self-hosted.md` - Verify self-hosted TTS instructions
- [ ] `docs/remote-machines.md` - Verify remote machine setup
- [ ] `docs/security/damage-control.md` - Verify security hook documentation
- [ ] Code comments throughout - Remove stale/confusing comments
- [ ] Docstrings - Ensure functions have accurate docstrings

### 2. Dead Code & Legacy Patterns

- [ ] Unused CSS classes/rules
- [ ] Unused JavaScript functions
- [ ] Unused Python functions/classes
- [ ] Commented-out code blocks
- [ ] TODO/FIXME comments that should be resolved
- [ ] Backwards compatibility shims (none should exist - pre-launch)
- [ ] Deprecated function calls
- [ ] Unused imports
- [ ] Dead code paths (unreachable conditions)

### 3. Code Quality

- [ ] Consistent error handling patterns
- [ ] No hardcoded secrets or credentials
- [ ] No debug print statements left in
- [ ] Proper logging levels (not INFO spam)
- [ ] Type hints where appropriate (Python)
- [ ] JSDoc comments for public JS functions
- [ ] Consistent naming conventions

### 4. Security Review

- [ ] Input validation on all API endpoints
- [ ] Path traversal protection
- [ ] Command injection prevention
- [ ] XSS prevention in web UI
- [ ] CORS configuration
- [ ] SSL/TLS configuration
- [ ] Sensitive data handling (API keys, tokens)
- [ ] Damage control hooks are comprehensive
- [ ] No secrets in code or comments

### 5. Configuration & Packaging

- [ ] `pyproject.toml` - Correct metadata, dependencies, entry points
- [ ] `setup.py` - If exists, should be minimal or removed
- [ ] `.gitignore` - Comprehensive
- [ ] No sensitive files tracked
- [ ] README.md exists and is accurate (if public)
- [ ] LICENSE file exists

### 6. Testing & CI

- [ ] Tests exist and pass
- [ ] CI/CD configuration (if any)
- [ ] No test files with hardcoded paths/credentials

### 7. JavaScript/Frontend

- [ ] No console.log statements (except intentional debug)
- [ ] Proper error handling in async functions
- [ ] No memory leaks (event listener cleanup)
- [ ] Consistent UI patterns

### 8. Python/Backend

- [ ] Proper async/await usage
- [ ] Resource cleanup (file handles, connections)
- [ ] Exception handling that doesn't swallow errors
- [ ] Proper use of logging vs print

## Files to Review

### Core Python
- `agentwire/__main__.py` - CLI implementation
- `agentwire/server.py` - Portal server
- `agentwire/config.py` - Configuration handling
- `agentwire/agent.py` - Agent/tmux interaction
- `agentwire/damage_control.py` - Security hooks

### JavaScript
- `agentwire/static/js/desktop.js` - Main desktop manager
- `agentwire/static/js/desktop-manager.js` - Desktop state
- `agentwire/static/js/session-window.js` - Session windows
- `agentwire/static/js/list-window.js` - List window base
- `agentwire/static/js/windows/*.js` - Window implementations

### CSS
- `agentwire/static/css/desktop.css` - Main styles

### Templates
- `agentwire/templates/*.html` - HTML templates

### Configuration
- `pyproject.toml` - Package configuration

### Documentation
- `CLAUDE.md` - Main project docs
- `docs/*.md` - All documentation files

## Findings

### Critical (Must Fix)
_(None yet)_

### High Priority
_(None yet)_

### Medium Priority
_(None yet)_

### Low Priority / Cleanup
_(None yet)_

## Progress

- [ ] Phase 1: Documentation review
- [ ] Phase 2: Python code review
- [ ] Phase 3: JavaScript code review
- [ ] Phase 4: CSS cleanup
- [ ] Phase 5: Security audit
- [ ] Phase 6: Final verification

## Notes

- Branch: `pypi-release-review`
- All changes should be atomic commits
- Each finding should be fixed before moving to next
