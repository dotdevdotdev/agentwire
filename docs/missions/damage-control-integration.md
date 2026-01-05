# Mission: Damage Control Integration

> Living document. Update this, don't create new versions.

**Status**: Active
**Branch**: `mission/damage-control`
**Priority**: High
**Estimated Scope**: 4 waves, comprehensive integration

---

## Overview

Integrate the Claude Code Damage Control security hooks system into AgentWire to provide defense-in-depth protection for parallel agent execution. Blocks dangerous commands and protects sensitive files via PreToolUse hooks.

**Why Critical**: AgentWire's parallel remote agent execution multiplies risk. A single `rm -rf /` in a remote session is unrecoverable. Multi-agent missions amplify the chance of catastrophic mistakes.

**Scope Decisions**:
- ✅ Single comprehensive mission (all 4 phases)
- ✅ Python/UV only (matches AgentWire stack)
- ✅ Global scope (like Claude Code, not per-session)
- ✅ Audit logging in Wave 2/3 (not Wave 1)

---

## Source Material

**Reference Codebase**: `~/projects/claude-code-damage-control/`

**Key Files to Study**:
- `.claude/skills/damage-control/patterns.yaml` - 300+ security patterns
- `.claude/skills/damage-control/hooks/damage-control-python/bash-tool-damage-control.py`
- `.claude/skills/damage-control/hooks/damage-control-python/edit-tool-damage-control.py`
- `.claude/skills/damage-control/hooks/damage-control-python/write-tool-damage-control.py`
- `.claude/skills/damage-control/hooks/damage-control-python/test-damage-control.py`

---

## Wave 1: Core Hook Infrastructure

**Goal**: Get basic damage control hooks working in AgentWire with existing patterns.

**Tasks**:

- [x] **1.1**: Create `.agentwire/hooks/damage-control/` directory structure
  - Files: `~/.agentwire/hooks/damage-control/` (global scope)
  - Copy base structure from claude-code-damage-control

- [x] **1.2**: Port `patterns.yaml` to AgentWire
  - Source: `.claude/skills/damage-control/patterns.yaml`
  - Target: `~/.agentwire/hooks/damage-control/patterns.yaml`
  - Keep all 300+ patterns intact initially

- [x] **1.3**: Adapt `bash-tool-damage-control.py` for AgentWire
  - Source: `hooks/damage-control-python/bash-tool-damage-control.py`
  - Target: `~/.agentwire/hooks/damage-control/bash-tool-damage-control.py`
  - Update config path resolution for AgentWire (`$AGENTWIRE_DIR` instead of `$CLAUDE_PROJECT_DIR`)
  - Keep all pattern matching logic identical

- [x] **1.4**: Adapt `edit-tool-damage-control.py` for AgentWire
  - Source: `hooks/damage-control-python/edit-tool-damage-control.py`
  - Target: `~/.agentwire/hooks/damage-control/edit-tool-damage-control.py`
  - Update config path resolution
  - Ensure glob pattern matching works

- [x] **1.5**: Adapt `write-tool-damage-control.py` for AgentWire
  - Source: `hooks/damage-control-python/write-tool-damage-control.py`
  - Target: `~/.agentwire/hooks/damage-control/write-tool-damage-control.py`
  - Update config path resolution

- [x] **1.6**: Create AgentWire hook registration in settings
  - File: `~/.agentwire/settings.json` (create if doesn't exist)
  - Add PreToolUse hooks for Bash, Edit, Write tools
  - Use UV runtime: `uv run ~/.agentwire/hooks/damage-control/bash-tool-damage-control.py`

- [x] **1.7**: Write basic integration tests
  - File: `tests/hooks/test_damage_control_basic.py`
  - Test: Bash hook blocks `rm -rf /`
  - Test: Edit hook blocks `~/.ssh/id_rsa`
  - Test: Write hook blocks `.env` files
  - Test: Allow safe commands (`ls`, `git status`)

---

## Wave 2: AgentWire-Specific Patterns

**Goal**: Extend patterns.yaml with AgentWire-specific protections and add audit logging.

**Tasks**:

- [x] **2.1**: Add AgentWire infrastructure protection patterns
  - File: `~/.agentwire/hooks/damage-control/patterns.yaml`
  - Add bashToolPatterns:
    - `tmux kill-server` (kills all sessions)
    - `tmux kill-session -t agentwire-*` (kills AgentWire sessions)
    - `agentwire destroy` (if we add this command)
    - `rm -rf ~/.agentwire/` (destroys state)

- [x] **2.2**: Add AgentWire path protections
  - File: `~/.agentwire/hooks/damage-control/patterns.yaml`
  - Add to zeroAccessPaths:
    - `~/.agentwire/credentials/`
    - `~/.agentwire/api-keys/`
    - `~/.agentwire/secrets/`
  - Add to noDeletePaths:
    - `~/.agentwire/sessions/`
    - `~/.agentwire/missions/`
    - `.agentwire/mission.md`

- [x] **2.3**: Add remote execution safeguards
  - File: `~/.agentwire/hooks/damage-control/patterns.yaml`
  - Add patterns for dangerous remote operations:
    - `ssh ... rm -rf` variations
    - Remote database drops
    - Remote service shutdowns

- [x] **2.4**: Implement audit logging framework
  - File: `~/.agentwire/hooks/damage-control/audit_logger.py`
  - Log structure: `{timestamp, session, agent, tool, command, blocked_by, user_approved}`
  - Storage: `~/.agentwire/logs/damage-control/YYYY-MM-DD.jsonl`
  - Functions: `log_blocked()`, `log_allowed()`, `log_asked()`

- [x] **2.5**: Integrate audit logging into hooks
  - Files: All three damage-control hooks (bash, edit, write)
  - Import audit_logger
  - Log every block, ask, and allow decision
  - Include session context if available

- [x] **2.6**: Create audit log query tool
  - File: `~/.agentwire/hooks/damage-control/query_audit.py`
  - CLI: `python query_audit.py --today` (show today's blocks)
  - CLI: `python query_audit.py --session mission/auth` (show session blocks)
  - CLI: `python query_audit.py --pattern "rm -rf"` (show specific pattern blocks)

---

## Wave 3: Testing & Documentation

**Goal**: Comprehensive testing and documentation for AgentWire integration.

**Tasks**:

- [x] **3.1**: Port interactive test tool for AgentWire
  - Source: `hooks/damage-control-python/test-damage-control.py`
  - Target: `~/.agentwire/hooks/damage-control/test-damage-control.py`
  - Update to use AgentWire config paths
  - Keep interactive mode (`-i`) functionality
  - ✅ Complete - Test tool ported and working

- [x] **3.2**: Create AgentWire-specific test scenarios
  - File: `tests/hooks/test_agentwire_patterns.py`
  - Test: AgentWire tmux protections
  - Test: Session file protections
  - Test: Remote execution blocks
  - Test: Audit logging integration
  - ✅ Complete - Comprehensive test suite created with 40+ test cases

- [ ] **3.3**: Test with real AgentWire sessions
  - Create test mission that intentionally triggers blocks
  - Verify blocks propagate to session agents
  - Verify audit logs capture all events
  - Test ask patterns with user confirmation
  - ⚠️  Blocked - Waiting for Wave 1 hook implementation

- [x] **3.4**: Write integration documentation
  - File: `docs/security/damage-control.md`
  - Overview of protection system
  - How to customize patterns
  - How to query audit logs
  - Troubleshooting guide
  - ✅ Complete - Comprehensive docs with examples, FAQ, troubleshooting

- [x] **3.5**: Create migration guide
  - File: `docs/security/damage-control-migration.md`
  - How to enable damage control in existing AgentWire installations
  - How to customize for specific use cases
  - How to disable temporarily if needed
  - ✅ Complete - Step-by-step migration with rollback instructions

---

## Wave 4: Advanced Features & CLI Integration

**Goal**: Polish the integration with CLI commands and advanced safety features.

**Tasks**:

- [x] **4.1**: Add `agentwire safety check` command
  - File: `agentwire/cli_safety.py`
  - Command: `agentwire safety check "rm -rf /tmp"`
  - Output: Would be blocked/allowed/asked, which pattern matched
  - Dry-run testing without execution
  - ✅ Complete - Integrated into main CLI

- [x] **4.2**: Add `agentwire safety status` command
  - File: `agentwire/cli_safety.py`
  - Command: `agentwire safety status`
  - Output: Show loaded patterns count, recent blocks, audit log location
  - ✅ Complete - Shows pattern counts and recent blocks

- [x] **4.3**: Add `agentwire safety logs` command
  - File: `agentwire/cli_safety.py`
  - Command: `agentwire safety logs --tail 20`
  - Output: Show recent audit log entries (blocked/asked operations)
  - Options: `--session`, `--today`, `--pattern`
  - ✅ Complete - All filters implemented

- [x] **4.4**: Mission safety validation
  - File: `agentwire/mission_safety.py`
  - Function: `validate_mission_safety(mission_file) -> List[Warning]`
  - Parse mission commands, check against patterns
  - Warn before executing mission if dangerous commands detected
  - ✅ Complete - Standalone validator module with CLI

- [x] **4.5**: Session context integration
  - Files: Audit logger already supports `$AGENTWIRE_SESSION_ID` and `$AGENTWIRE_AGENT_ID`
  - Read session ID from environment in audit_logger.py (line 44-49)
  - Include in audit logs for better traceability
  - Session context appears in all logged events
  - ✅ Complete - Already implemented in Wave 2

- [x] **4.6**: Create installation CLI
  - File: `agentwire/cli_safety.py`
  - Command: `agentwire safety install`
  - Interactive: Ask user to confirm installation
  - Validates hook directory exists
  - Provides next steps guidance
  - ✅ Complete - Interactive installation with verification

---

## Completion Criteria

**Functional Requirements**:
- [ ] Hooks block all dangerous commands from base patterns.yaml
- [ ] Hooks block AgentWire-specific dangerous operations
- [ ] Audit logging captures all security decisions
- [ ] Interactive test tool works for AgentWire
- [ ] CLI commands (`agentwire safety check/status/logs`) functional

**Quality Requirements**:
- [ ] All tests pass (`pytest tests/hooks/`)
- [ ] Documentation complete and accurate
- [ ] Audit logs queryable and useful
- [ ] Real AgentWire session tested successfully

**Integration Requirements**:
- [ ] Hooks work in parallel agent sessions
- [ ] Session context appears in audit logs
- [ ] No performance degradation in command execution
- [ ] Graceful degradation if hooks fail

---

## Technical Notes

### Config Path Resolution

AgentWire uses `$AGENTWIRE_DIR` instead of `$CLAUDE_PROJECT_DIR`:

```python
def get_config_path() -> Path:
    # 1. Check AgentWire hooks directory
    agentwire_dir = os.environ.get("AGENTWIRE_DIR", os.path.expanduser("~/.agentwire"))
    config = Path(agentwire_dir) / "hooks" / "damage-control" / "patterns.yaml"
    if config.exists():
        return config

    # 2. Fallback to script directory
    return Path(__file__).parent / "patterns.yaml"
```

### Hook Registration Format

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "uv run ~/.agentwire/hooks/damage-control/bash-tool-damage-control.py",
          "timeout": 5
        }]
      },
      {
        "matcher": "Edit",
        "hooks": [{
          "type": "command",
          "command": "uv run ~/.agentwire/hooks/damage-control/edit-tool-damage-control.py",
          "timeout": 5
        }]
      },
      {
        "matcher": "Write",
        "hooks": [{
          "type": "command",
          "command": "uv run ~/.agentwire/hooks/damage-control/write-tool-damage-control.py",
          "timeout": 5
        }]
      }
    ]
  }
}
```

### Audit Log Format

```json
{
  "timestamp": "2026-01-05T13:45:22Z",
  "session_id": "mission/damage-control",
  "agent_id": "wave-2-task-1",
  "tool": "Bash",
  "command": "rm -rf /tmp/test",
  "decision": "blocked",
  "blocked_by": "bashToolPattern: rm with recursive flags",
  "user_approved": null,
  "pattern_matched": "\\brm\\s+-[rRf]"
}
```

---

## Dependencies

- **UV Runtime**: Already used by AgentWire (✓)
- **PyYAML**: Add to AgentWire dependencies
- **Base Damage Control**: Clone from `~/projects/claude-code-damage-control`

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hooks slow down commands | Medium | Use 5s timeout, optimize pattern matching |
| False positives block valid commands | High | Thorough testing, use ask patterns for gray areas |
| Audit logs grow too large | Low | Implement log rotation (30 day retention) |
| Hooks fail and commands proceed | High | Test hook failure scenarios, alert on hook errors |
| Pattern updates require restart | Low | Document restart requirement, consider hot reload later |

---

## Success Metrics

- **Security**: Zero catastrophic commands executed in testing
- **Performance**: Hook overhead <100ms per command
- **Coverage**: 95%+ of dangerous patterns blocked
- **Usability**: Installation takes <5 minutes
- **Observability**: Audit logs enable debugging of all blocks

---

## Future Enhancements (Deferred)

- Per-session pattern overrides
- Per-mission safety.yaml files
- Wave-based restrictions (Wave 1 more restrictive than Wave 2)
- Remote machine-specific profiles
- Hot reload of patterns without restart
- Web UI for audit log exploration
- Integration with AgentWire notification system
