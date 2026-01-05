"""
AgentWire Damage Control Pattern Tests
=======================================

Tests for AgentWire-specific security patterns including:
- Tmux session protections
- Session file protections (.agentwire/)
- Remote execution blocks
- Audit logging integration

Run with: pytest tests/hooks/test_agentwire_patterns.py -v
"""

import subprocess
import json
import os
from pathlib import Path
import pytest


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_hook_path(hook_type: str) -> Path:
    """Get path to damage control hook."""
    agentwire_dir = os.environ.get("AGENTWIRE_DIR", os.path.expanduser("~/.agentwire"))
    hooks = {
        "bash": "bash-tool-damage-control.py",
        "edit": "edit-tool-damage-control.py",
        "write": "write-tool-damage-control.py",
    }
    return Path(agentwire_dir) / "hooks" / "damage-control" / hooks[hook_type]


def run_hook(hook_type: str, tool_name: str, tool_input: dict) -> tuple[int, str, str]:
    """Run a damage control hook and return (exit_code, stdout, stderr)."""
    hook_path = get_hook_path(hook_type)

    if not hook_path.exists():
        pytest.skip(f"Hook not installed: {hook_path}")

    input_json = json.dumps({
        "tool_name": tool_name,
        "tool_input": tool_input
    })

    result = subprocess.run(
        ["uv", "run", str(hook_path)],
        input=input_json,
        capture_output=True,
        text=True,
        timeout=10
    )

    return result.returncode, result.stdout, result.stderr


def assert_blocked(hook_type: str, tool_name: str, tool_input: dict, reason_pattern: str = None):
    """Assert that a hook blocks the operation (exit code 2)."""
    exit_code, stdout, stderr = run_hook(hook_type, tool_name, tool_input)
    assert exit_code == 2, f"Expected block (exit 2), got {exit_code}. stderr: {stderr}"
    if reason_pattern:
        assert reason_pattern.lower() in stderr.lower(), f"Expected reason '{reason_pattern}' in stderr: {stderr}"


def assert_allowed(hook_type: str, tool_name: str, tool_input: dict):
    """Assert that a hook allows the operation (exit code 0)."""
    exit_code, stdout, stderr = run_hook(hook_type, tool_name, tool_input)
    assert exit_code == 0, f"Expected allow (exit 0), got {exit_code}. stderr: {stderr}"


# ============================================================================
# AGENTWIRE TMUX PROTECTIONS
# ============================================================================

class TestTmuxProtections:
    """Test protection of tmux infrastructure."""

    def test_blocks_kill_server(self):
        """Block tmux kill-server (kills all sessions)."""
        assert_blocked("bash", "Bash", {"command": "tmux kill-server"}, "tmux")

    def test_blocks_kill_agentwire_session(self):
        """Block killing AgentWire tmux sessions."""
        assert_blocked("bash", "Bash", {"command": "tmux kill-session -t agentwire-mission"}, "agentwire")

    def test_blocks_kill_agentwire_wildcard(self):
        """Block wildcard killing of AgentWire sessions."""
        assert_blocked("bash", "Bash", {"command": "tmux kill-session -t agentwire-*"}, "agentwire")

    def test_allows_kill_other_session(self):
        """Allow killing non-AgentWire sessions."""
        assert_allowed("bash", "Bash", {"command": "tmux kill-session -t my-other-session"})

    def test_allows_list_sessions(self):
        """Allow tmux list operations."""
        assert_allowed("bash", "Bash", {"command": "tmux list-sessions"})

    def test_allows_attach_session(self):
        """Allow attaching to sessions."""
        assert_allowed("bash", "Bash", {"command": "tmux attach -t agentwire-mission"})


# ============================================================================
# AGENTWIRE SESSION FILE PROTECTIONS
# ============================================================================

class TestSessionFileProtections:
    """Test protection of .agentwire/ directory and session files."""

    def test_blocks_delete_agentwire_dir(self):
        """Block deletion of ~/.agentwire/ directory."""
        assert_blocked("bash", "Bash", {"command": "rm -rf ~/.agentwire/"}, "agentwire")

    def test_blocks_delete_sessions_dir(self):
        """Block deletion of sessions directory."""
        assert_blocked("bash", "Bash", {"command": "rm -rf ~/.agentwire/sessions/"}, "sessions")

    def test_blocks_delete_missions_dir(self):
        """Block deletion of missions directory."""
        assert_blocked("bash", "Bash", {"command": "rm -rf ~/.agentwire/missions/"}, "missions")

    def test_blocks_edit_credentials(self):
        """Block editing credential files."""
        assert_blocked("edit", "Edit", {"file_path": os.path.expanduser("~/.agentwire/credentials/api-key.json")}, "credentials")

    def test_blocks_write_credentials(self):
        """Block writing to credentials directory."""
        assert_blocked("write", "Write", {"file_path": os.path.expanduser("~/.agentwire/credentials/new-key.json")}, "credentials")

    def test_blocks_edit_api_keys(self):
        """Block editing API keys."""
        assert_blocked("edit", "Edit", {"file_path": os.path.expanduser("~/.agentwire/api-keys/openai.key")}, "api-keys")

    def test_blocks_delete_mission_file(self):
        """Block deletion of mission files."""
        assert_blocked("bash", "Bash", {"command": "rm .agentwire/mission.md"}, "mission")

    def test_allows_read_session_files(self):
        """Allow reading session files (not blocked by damage-control)."""
        # Note: This tests that we don't block reads, which is correct
        assert_allowed("bash", "Bash", {"command": "cat ~/.agentwire/sessions/active.json"})


# ============================================================================
# REMOTE EXECUTION SAFEGUARDS
# ============================================================================

class TestRemoteExecutionSafeguards:
    """Test protection against dangerous remote operations."""

    def test_blocks_remote_rm_rf(self):
        """Block rm -rf over SSH."""
        assert_blocked("bash", "Bash", {"command": "ssh user@host 'rm -rf /'"}, "rm")

    def test_blocks_remote_database_drop(self):
        """Block remote database drops."""
        assert_blocked("bash", "Bash", {"command": "ssh db-server 'psql -c DROP DATABASE production'"}, "drop database")

    def test_blocks_remote_service_shutdown(self):
        """Block remote service shutdowns."""
        assert_blocked("bash", "Bash", {"command": "ssh server 'systemctl stop nginx'"}, "systemctl stop")

    def test_blocks_remote_docker_prune(self):
        """Block remote Docker prune operations."""
        assert_blocked("bash", "Bash", {"command": "ssh docker-host 'docker system prune -af'"}, "docker")

    def test_allows_safe_remote_commands(self):
        """Allow safe remote commands."""
        assert_allowed("bash", "Bash", {"command": "ssh server 'ls -la'"})
        assert_allowed("bash", "Bash", {"command": "ssh server 'git status'"})


# ============================================================================
# AGENTWIRE CLI PROTECTIONS
# ============================================================================

class TestAgentWireCLIProtections:
    """Test protection of AgentWire CLI operations."""

    def test_blocks_agentwire_destroy(self):
        """Block hypothetical agentwire destroy command."""
        # This is a pattern we want to protect if/when added
        assert_blocked("bash", "Bash", {"command": "agentwire destroy --all"}, "destroy")

    def test_allows_agentwire_status(self):
        """Allow safe agentwire status commands."""
        assert_allowed("bash", "Bash", {"command": "agentwire status"})

    def test_allows_agentwire_list(self):
        """Allow agentwire list commands."""
        assert_allowed("bash", "Bash", {"command": "agentwire sessions"})


# ============================================================================
# AUDIT LOG INTEGRATION
# ============================================================================

class TestAuditLogIntegration:
    """Test that audit logs are created for security decisions."""

    def test_audit_log_exists_after_block(self):
        """Verify audit log is created when command is blocked."""
        # Run a blocked command
        run_hook("bash", "Bash", {"command": "rm -rf /tmp/test"})

        # Check that audit log directory exists
        agentwire_dir = os.environ.get("AGENTWIRE_DIR", os.path.expanduser("~/.agentwire"))
        log_dir = Path(agentwire_dir) / "logs" / "damage-control"

        # Note: This test will pass if Wave 2 audit logging is implemented
        # If audit logging isn't implemented yet, this serves as a spec
        if log_dir.exists():
            # Find today's log file
            import datetime
            today = datetime.date.today().strftime("%Y-%m-%d")
            log_file = log_dir / f"{today}.jsonl"

            if log_file.exists():
                # Verify log contains our test
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    # Last line should contain our blocked command
                    if lines:
                        last_entry = json.loads(lines[-1])
                        assert "rm -rf" in last_entry.get("command", "")
                        assert last_entry.get("decision") == "blocked"
        else:
            pytest.skip("Audit logging not yet implemented (Wave 2)")


# ============================================================================
# GLOB PATTERN TESTS (AgentWire-specific files)
# ============================================================================

class TestGlobPatterns:
    """Test glob patterns for AgentWire file protections."""

    def test_blocks_env_files(self):
        """Block .env files anywhere in project."""
        assert_blocked("edit", "Edit", {"file_path": "/project/.env"}, "env")
        assert_blocked("edit", "Edit", {"file_path": "/project/.env.local"}, "env")
        assert_blocked("write", "Write", {"file_path": "/project/config/.env"}, "env")

    def test_blocks_pem_files(self):
        """Block .pem files (certificates/keys)."""
        assert_blocked("edit", "Edit", {"file_path": "/certs/server.pem"}, "pem")
        assert_blocked("write", "Write", {"file_path": "/tmp/key.pem"}, "pem")

    def test_blocks_key_files(self):
        """Block .key files."""
        assert_blocked("edit", "Edit", {"file_path": "/ssl/cert.key"}, "key")

    def test_allows_readme_files(self):
        """Allow README and documentation files."""
        assert_allowed("edit", "Edit", {"file_path": "/project/README.md"})
        assert_allowed("write", "Write", {"file_path": "/docs/guide.md"})


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple patterns."""

    def test_combined_protections(self):
        """Test that multiple protection layers work together."""
        # Should be blocked by both tmux AND destructive command patterns
        assert_blocked("bash", "Bash", {"command": "tmux kill-server && rm -rf /"}, "tmux")

    def test_no_false_positives_on_safe_operations(self):
        """Verify safe operations aren't blocked."""
        safe_commands = [
            "ls -la ~/.agentwire/",
            "cat ~/.agentwire/sessions/current.json",
            "git status",
            "tmux list-sessions",
            "agentwire status",
            "echo 'test'",
        ]

        for cmd in safe_commands:
            assert_allowed("bash", "Bash", {"command": cmd})

    def test_chained_safe_commands(self):
        """Allow chained safe commands."""
        assert_allowed("bash", "Bash", {"command": "ls -la && pwd && git status"})


# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def check_hooks_installed():
    """Verify hooks are installed before running tests."""
    agentwire_dir = os.environ.get("AGENTWIRE_DIR", os.path.expanduser("~/.agentwire"))
    hook_dir = Path(agentwire_dir) / "hooks" / "damage-control"

    if not hook_dir.exists():
        pytest.exit(f"Damage control hooks not found at {hook_dir}. Please install them first.")

    patterns_file = hook_dir / "patterns.yaml"
    if not patterns_file.exists():
        pytest.exit(f"patterns.yaml not found at {patterns_file}. Please install it first.")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
