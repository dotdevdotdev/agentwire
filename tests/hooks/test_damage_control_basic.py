"""
Basic integration tests for damage control hooks.

Tests that the hooks properly block dangerous commands and allow safe ones.
"""

import json
import subprocess
import sys
from pathlib import Path


def run_hook(hook_script: str, tool_name: str, tool_input: dict) -> tuple[int, str, str]:
    """Run a damage control hook script and return exit code, stdout, stderr."""
    hook_path = Path.home() / ".agentwire" / "hooks" / "damage-control" / hook_script

    input_data = {
        "tool_name": tool_name,
        "tool_input": tool_input
    }

    result = subprocess.run(
        ["uv", "run", str(hook_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr


def test_bash_hook_blocks_rm_rf():
    """Test that bash hook blocks 'rm -rf /' command."""
    exit_code, stdout, stderr = run_hook(
        "bash-tool-damage-control.py",
        "Bash",
        {"command": "rm -rf /"}
    )

    assert exit_code == 2, f"Expected exit code 2, got {exit_code}"
    assert "SECURITY" in stderr, f"Expected SECURITY in stderr, got: {stderr}"
    assert "rm with recursive" in stderr.lower(), f"Expected 'rm with recursive' in stderr, got: {stderr}"
    print("✓ Bash hook blocks 'rm -rf /'")


def test_bash_hook_blocks_git_push_force():
    """Test that bash hook blocks 'git push --force' command."""
    exit_code, stdout, stderr = run_hook(
        "bash-tool-damage-control.py",
        "Bash",
        {"command": "git push origin main --force"}
    )

    assert exit_code == 2, f"Expected exit code 2, got {exit_code}"
    assert "SECURITY" in stderr, f"Expected SECURITY in stderr, got: {stderr}"
    assert "force" in stderr.lower(), f"Expected 'force' in stderr, got: {stderr}"
    print("✓ Bash hook blocks 'git push --force'")


def test_bash_hook_allows_safe_commands():
    """Test that bash hook allows safe commands like 'ls' and 'git status'."""
    # Test ls
    exit_code, stdout, stderr = run_hook(
        "bash-tool-damage-control.py",
        "Bash",
        {"command": "ls -la"}
    )
    assert exit_code == 0, f"Expected exit code 0 for 'ls -la', got {exit_code}. Stderr: {stderr}"

    # Test git status
    exit_code, stdout, stderr = run_hook(
        "bash-tool-damage-control.py",
        "Bash",
        {"command": "git status"}
    )
    assert exit_code == 0, f"Expected exit code 0 for 'git status', got {exit_code}. Stderr: {stderr}"

    print("✓ Bash hook allows safe commands (ls, git status)")


def test_edit_hook_blocks_ssh_key():
    """Test that edit hook blocks editing ~/.ssh/id_rsa."""
    exit_code, stdout, stderr = run_hook(
        "edit-tool-damage-control.py",
        "Edit",
        {"file_path": "~/.ssh/id_rsa"}
    )

    assert exit_code == 2, f"Expected exit code 2, got {exit_code}"
    assert "SECURITY" in stderr, f"Expected SECURITY in stderr, got: {stderr}"
    assert "zero-access" in stderr.lower(), f"Expected 'zero-access' in stderr, got: {stderr}"
    print("✓ Edit hook blocks ~/.ssh/id_rsa")


def test_edit_hook_blocks_env_file():
    """Test that edit hook blocks editing .env files."""
    exit_code, stdout, stderr = run_hook(
        "edit-tool-damage-control.py",
        "Edit",
        {"file_path": "/path/to/project/.env"}
    )

    assert exit_code == 2, f"Expected exit code 2, got {exit_code}"
    assert "SECURITY" in stderr, f"Expected SECURITY in stderr, got: {stderr}"
    print("✓ Edit hook blocks .env files")


def test_edit_hook_allows_normal_files():
    """Test that edit hook allows editing normal files."""
    exit_code, stdout, stderr = run_hook(
        "edit-tool-damage-control.py",
        "Edit",
        {"file_path": "/path/to/project/src/main.py"}
    )

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}. Stderr: {stderr}"
    print("✓ Edit hook allows normal files")


def test_write_hook_blocks_env_file():
    """Test that write hook blocks writing .env files."""
    exit_code, stdout, stderr = run_hook(
        "write-tool-damage-control.py",
        "Write",
        {"file_path": ".env.local"}
    )

    assert exit_code == 2, f"Expected exit code 2, got {exit_code}"
    assert "SECURITY" in stderr, f"Expected SECURITY in stderr, got: {stderr}"
    print("✓ Write hook blocks .env files")


def test_write_hook_blocks_pem_files():
    """Test that write hook blocks writing .pem files."""
    exit_code, stdout, stderr = run_hook(
        "write-tool-damage-control.py",
        "Write",
        {"file_path": "/path/to/cert.pem"}
    )

    assert exit_code == 2, f"Expected exit code 2, got {exit_code}"
    assert "SECURITY" in stderr, f"Expected SECURITY in stderr, got: {stderr}"
    print("✓ Write hook blocks .pem files")


def test_write_hook_allows_normal_files():
    """Test that write hook allows writing normal files."""
    exit_code, stdout, stderr = run_hook(
        "write-tool-damage-control.py",
        "Write",
        {"file_path": "/path/to/project/README.md"}
    )

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}. Stderr: {stderr}"
    print("✓ Write hook allows normal files")


def main():
    """Run all tests."""
    print("\nRunning damage control basic integration tests...\n")

    tests = [
        test_bash_hook_blocks_rm_rf,
        test_bash_hook_blocks_git_push_force,
        test_bash_hook_allows_safe_commands,
        test_edit_hook_blocks_ssh_key,
        test_edit_hook_blocks_env_file,
        test_edit_hook_allows_normal_files,
        test_write_hook_blocks_env_file,
        test_write_hook_blocks_pem_files,
        test_write_hook_allows_normal_files,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            failed += 1

    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")

    if failed > 0:
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
