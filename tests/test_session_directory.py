"""Test session directory initialization.

Verifies that sessions always start in the correct directory.
This prevents regression of the issue where sessions created with -c /path
didn't have Claude running from that directory.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest


@pytest.fixture
def test_session_name():
    """Provide a unique test session name."""
    return "test-dir-verification"


@pytest.fixture
def cleanup_session(test_session_name):
    """Clean up test session after test."""
    yield
    # Cleanup - kill session if it exists
    subprocess.run(
        ["agentwire", "kill", "-s", test_session_name],
        capture_output=True,
    )


def test_session_starts_in_correct_directory(test_session_name, cleanup_session):
    """Verify session pwd matches specified path.

    Tests that when creating a session with a specific path,
    Claude starts in that directory and can detect git repos,
    create commits, etc.
    """
    # Use the current project directory as test path
    test_path = str(Path(__file__).parent.parent.resolve())

    # Create session with specific path
    result = subprocess.run(
        ["agentwire", "new", "-s", test_session_name, "-p", test_path],
        capture_output=True,
        text=True,
    )

    # Check session was created successfully
    assert result.returncode == 0, f"Failed to create session: {result.stderr}"

    # Wait for Claude to start
    time.sleep(3)

    # Send pwd command to verify working directory
    subprocess.run(
        ["agentwire", "send", "-s", test_session_name, "pwd"],
        capture_output=True,
    )
    time.sleep(1)

    # Read output and verify path
    output_result = subprocess.run(
        ["agentwire", "output", "-s", test_session_name, "-n", "50"],
        capture_output=True,
        text=True,
    )

    expected_path = test_path
    assert expected_path in output_result.stdout, (
        f"Expected path '{expected_path}' not found in output:\n{output_result.stdout}"
    )


def test_worktree_session_detects_git_repo(cleanup_session):
    """Verify worktree sessions can detect git repo.

    Tests that sessions created in worktrees can see the git repo
    and perform git operations.
    """
    # Use a timestamp-based branch name to avoid conflicts
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session_name = f"agentwire/test-git-{timestamp}"

    # Create worktree session in the agentwire project itself
    result = subprocess.run(
        ["agentwire", "new", "-s", session_name],
        capture_output=True,
        text=True,
    )

    # Check session was created successfully
    assert result.returncode == 0, f"Failed to create session: {result.stderr}"

    # Wait for Claude to start
    time.sleep(3)

    # Send git status command
    subprocess.run(
        ["agentwire", "send", "-s", session_name, "git status"],
        capture_output=True,
    )
    time.sleep(1)

    # Read output and verify git works
    output_result = subprocess.run(
        ["agentwire", "output", "-s", session_name, "-n", "50"],
        capture_output=True,
        text=True,
    )

    # Should see "On branch" indicating git repo is detected
    assert "On branch" in output_result.stdout, (
        f"Git repo not detected in worktree session:\n{output_result.stdout}"
    )

    # Cleanup
    subprocess.run(
        ["agentwire", "kill", "-s", session_name],
        capture_output=True,
    )


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])
