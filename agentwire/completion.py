"""Completion detection for scheduled tasks.

Handles:
- Idle detection (session goes quiet)
- System summary prompt (ask agent to write summary)
- Summary file parsing (extract status from YAML front matter)
"""

import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


class CompletionError(Exception):
    """Raised when completion detection fails."""

    pass


class CompletionTimeout(CompletionError):
    """Raised when waiting for completion times out."""

    pass


class SummaryResult(NamedTuple):
    """Parsed result from a task summary file."""

    status: str  # complete, incomplete, failed
    summary: str  # One-line summary
    files_modified: list[str]  # List of modified files
    blockers: list[str]  # List of blockers (if any)
    raw_content: str  # Full file content


# System prompt sent after task completion to get structured summary
SYSTEM_SUMMARY_PROMPT = """Write a task summary to {summary_file} in YAML front matter format:

```markdown
---
status: complete | incomplete | failed
summary: one line describing what you accomplished
files_modified:
  - path/to/file1
  - path/to/file2
blockers:
  - any issues preventing completion
---

Additional notes about what was done, challenges encountered, etc.
```

Status meanings:
- complete: Task finished successfully
- incomplete: Task partially done, more work needed (not a failure)
- failed: Task could not be completed due to errors

Write the file now."""


def generate_summary_filename(task_name: str) -> str:
    """Generate a timestamped summary filename.

    Args:
        task_name: Task name (for context, not used in filename currently)

    Returns:
        Relative path like .agentwire/task-summary-2024-01-15T07-00-00.md
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return f".agentwire/task-summary-{timestamp}.md"


def get_summary_prompt(summary_file: str) -> str:
    """Get the system summary prompt with the filename filled in.

    Args:
        summary_file: Path to the summary file to create

    Returns:
        Complete prompt string
    """
    return SYSTEM_SUMMARY_PROMPT.format(summary_file=summary_file)


def is_session_idle(session: str, idle_threshold: float = 3.0) -> bool:
    """Check if a session is currently idle.

    Uses the portal's cached status if available, otherwise checks tmux activity.

    Args:
        session: Session name
        idle_threshold: Seconds of inactivity to consider idle

    Returns:
        True if session is idle, False otherwise
    """
    # Try to get activity time from tmux
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", f"={session}", "#{pane_last_activity}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            last_activity = int(result.stdout.strip())
            current_time = int(time.time())
            idle_seconds = current_time - last_activity
            return idle_seconds >= idle_threshold
    except (subprocess.TimeoutExpired, ValueError, subprocess.SubprocessError):
        pass

    # Fallback: check if output is changing
    # This is less reliable but works as a backup
    return False


def wait_for_idle(
    session: str,
    timeout: float = 300.0,
    idle_threshold: float = 3.0,
    poll_interval: float = 2.0,
    stable_count: int = 3,
) -> bool:
    """Wait for a session to become idle.

    "Idle" means the session has not produced output for idle_threshold seconds
    for stable_count consecutive checks.

    Args:
        session: Session name
        timeout: Maximum seconds to wait
        idle_threshold: Seconds of inactivity to consider idle
        poll_interval: Seconds between checks
        stable_count: Number of consecutive idle checks required

    Returns:
        True if session became idle, False if timeout

    Raises:
        CompletionTimeout: If timeout is exceeded
    """
    start_time = time.time()
    consecutive_idle = 0
    last_output_hash = None

    while True:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            raise CompletionTimeout(
                f"Timeout waiting for session '{session}' to become idle "
                f"after {timeout:.0f}s"
            )

        # Check if session is still running
        result = subprocess.run(
            ["tmux", "has-session", "-t", f"={session}"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise CompletionError(f"Session '{session}' no longer exists")

        # Get current output snapshot
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", f"={session}", "-p", "-S", "-20"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            time.sleep(poll_interval)
            continue

        current_hash = hash(result.stdout)

        if current_hash == last_output_hash:
            consecutive_idle += 1
            if consecutive_idle >= stable_count:
                return True
        else:
            consecutive_idle = 0
            last_output_hash = current_hash

        time.sleep(poll_interval)


def wait_for_file(
    path: Path,
    timeout: float = 60.0,
    poll_interval: float = 1.0,
) -> bool:
    """Wait for a file to be created.

    Args:
        path: Path to the file
        timeout: Maximum seconds to wait
        poll_interval: Seconds between checks

    Returns:
        True if file was created

    Raises:
        CompletionTimeout: If timeout is exceeded
    """
    start_time = time.time()

    while True:
        if path.exists() and path.stat().st_size > 0:
            # Give a moment for the file to be fully written
            time.sleep(0.5)
            return True

        elapsed = time.time() - start_time
        if elapsed >= timeout:
            raise CompletionTimeout(
                f"Timeout waiting for file '{path}' after {timeout:.0f}s"
            )

        time.sleep(poll_interval)


def parse_summary_file(path: Path) -> SummaryResult:
    """Parse a task summary file with YAML front matter.

    Expected format:
        ---
        status: complete
        summary: Did the thing
        files_modified:
          - path/to/file
        blockers: []
        ---

        Additional notes here...

    Args:
        path: Path to the summary file

    Returns:
        SummaryResult with parsed fields

    Raises:
        CompletionError: If file cannot be parsed
    """
    try:
        content = path.read_text()
    except OSError as e:
        raise CompletionError(f"Cannot read summary file: {e}")

    # Default values
    status = "incomplete"
    summary = ""
    files_modified: list[str] = []
    blockers: list[str] = []

    # Parse YAML front matter
    if content.startswith("---"):
        # Find closing ---
        end_match = re.search(r"\n---\s*\n", content[3:])
        if end_match:
            yaml_content = content[3:3 + end_match.start()]

            # Track which list we're currently parsing
            current_list: str | None = None

            for line in yaml_content.split("\n"):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                if stripped.startswith("status:"):
                    status = stripped.split(":", 1)[1].strip()
                    current_list = None
                elif stripped.startswith("summary:"):
                    summary = stripped.split(":", 1)[1].strip()
                    current_list = None
                elif stripped.startswith("files_modified:"):
                    current_list = "files"
                elif stripped.startswith("blockers:"):
                    current_list = "blockers"
                elif stripped.startswith("- "):
                    item = stripped[2:].strip()
                    if current_list == "files":
                        files_modified.append(item)
                    elif current_list == "blockers":
                        blockers.append(item)

    # Validate status
    if status not in ("complete", "incomplete", "failed"):
        # Default to incomplete if status is unrecognized
        status = "incomplete"

    return SummaryResult(
        status=status,
        summary=summary,
        files_modified=files_modified,
        blockers=blockers,
        raw_content=content,
    )


def status_to_exit_code(status: str) -> int:
    """Convert status string to exit code.

    Args:
        status: Task status (complete, incomplete, failed)

    Returns:
        Exit code (0=complete, 1=failed, 2=incomplete)
    """
    if status == "complete":
        return 0
    elif status == "failed":
        return 1
    else:
        return 2
