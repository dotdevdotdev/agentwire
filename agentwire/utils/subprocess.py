"""
Subprocess execution utilities with consistent error handling.

Provides wrappers around subprocess.run() that handle:
- Timeouts with clear error messages
- stdout/stderr capture and decoding
- Consistent return types
"""

import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommandResult:
    """Result of a command execution.

    Attributes:
        returncode: Exit code (0 = success).
        stdout: Captured stdout as string.
        stderr: Captured stderr as string.
        timed_out: Whether the command timed out.
    """
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        """True if command succeeded (returncode == 0)."""
        return self.returncode == 0


def run_command(
    cmd: list[str],
    capture: bool = True,
    timeout: Optional[int] = 30,
    check: bool = False,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
) -> CommandResult:
    """Run a subprocess command with consistent handling.

    Args:
        cmd: Command and arguments as list.
        capture: Whether to capture stdout/stderr.
        timeout: Seconds before timeout, None for no timeout.
        check: Whether to raise on non-zero exit.
        cwd: Working directory for the command.
        env: Environment variables (extends current env).

    Returns:
        CommandResult with returncode, stdout, stderr, timed_out.

    Raises:
        subprocess.CalledProcessError: If check=True and command fails.

    Example:
        result = run_command(["ls", "-la"])
        if result.success:
            print(result.stdout)
        else:
            print(f"Error: {result.stderr}")
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            check=check,
        )
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s: {' '.join(cmd)}",
            timed_out=True,
        )
    except FileNotFoundError:
        return CommandResult(
            returncode=-1,
            stdout="",
            stderr=f"Command not found: {cmd[0]}",
        )


def run_command_check(
    cmd: list[str],
    timeout: Optional[int] = 30,
    cwd: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
    """Run a command and return stdout, raising on failure.

    Convenience wrapper for simple "run and get output" patterns.

    Args:
        cmd: Command and arguments as list.
        timeout: Seconds before timeout.
        cwd: Working directory.
        error_message: Custom error message prefix.

    Returns:
        stdout as string (stripped).

    Raises:
        RuntimeError: If command fails or times out.

    Example:
        branch = run_command_check(["git", "branch", "--show-current"])
    """
    result = run_command(cmd, timeout=timeout, cwd=cwd)

    if not result.success:
        prefix = error_message or f"Command failed: {' '.join(cmd)}"
        raise RuntimeError(f"{prefix}\n{result.stderr}")

    return result.stdout.strip()
