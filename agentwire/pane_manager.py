"""
Pane management for tmux-based worker agents.

Workers are spawned as panes within the orchestrator's session,
enabling a visual dashboard where all agents are visible simultaneously.
"""

import os
import subprocess
import time
from dataclasses import dataclass


@dataclass
class PaneInfo:
    """Information about a tmux pane."""
    index: int
    pane_id: str  # e.g., %37
    pid: int
    command: str
    active: bool = False


def get_current_session() -> str | None:
    """Get the session name from the current tmux environment.

    Returns None if not running inside tmux.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return None

    result = subprocess.run(
        ["tmux", "display", "-t", tmux_pane, "-p", "#{session_name}"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_current_pane_index() -> int | None:
    """Get the pane index from the current tmux environment.

    Returns None if not running inside tmux.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return None

    result = subprocess.run(
        ["tmux", "display", "-t", tmux_pane, "-p", "#{pane_index}"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return int(result.stdout.strip())
    return None


def _get_window_dimensions(session: str) -> tuple[int, int]:
    """Get window width and height for smart split direction."""
    result = subprocess.run(
        ["tmux", "display", "-t", f"{session}:0", "-p", "#{window_width}:#{window_height}"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        parts = result.stdout.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    return 120, 40  # default to landscape


def spawn_worker_pane(
    session: str | None = None,
    cwd: str | None = None,
    cmd: str | None = None
) -> int:
    """Spawn a new pane in the session and return its index.

    Args:
        session: Target session (default: auto-detect from $TMUX_PANE)
        cwd: Working directory for the new pane
        cmd: Command to run in the pane (sent after creation)

    Returns:
        The pane index of the newly created pane.

    Raises:
        RuntimeError: If not in tmux and no session specified, or if spawn fails.
    """
    if session is None:
        session = get_current_session()
        if session is None:
            raise RuntimeError("Not in tmux session and no session specified")

    # Smart split direction based on terminal dimensions
    # Default to stacked panes (-v) which works well on tablets/portrait
    # Only use side-by-side (-h) when terminal is very wide (ultrawide/landscape)
    width, height = _get_window_dimensions(session)
    # Use side-by-side only if width is >2.5x height (clearly ultrawide)
    split_flag = "-h" if width > height * 2.5 else "-v"

    # Build split-window command
    # -d: don't change focus to new pane
    # -P: print pane info
    # -F: format string
    split_cmd = [
        "tmux", "split-window",
        "-t", f"{session}:0",  # target window 0
        split_flag,  # smart split direction
        "-d",  # detached (don't steal focus)
        "-P", "-F", "#{pane_index}:#{pane_id}"  # return pane info
    ]

    if cwd:
        split_cmd.extend(["-c", cwd])

    result = subprocess.run(split_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create pane: {result.stderr}")

    # Parse output: "1:%42"
    output = result.stdout.strip()
    pane_index = int(output.split(":")[0])

    # Wait for shell to be ready (race condition fix)
    time.sleep(0.4)

    # Send command if provided
    if cmd:
        send_to_pane(session, pane_index, cmd)

    # Rebalance panes - use layout matching split direction
    # even-vertical = stacked (for -v), even-horizontal = side by side (for -h)
    layout = "even-horizontal" if split_flag == "-h" else "even-vertical"
    subprocess.run(
        ["tmux", "select-layout", "-t", f"{session}:0", layout],
        capture_output=True
    )

    return pane_index


def list_panes(session: str | None = None) -> list[PaneInfo]:
    """List all panes in a session.

    Args:
        session: Target session (default: auto-detect from $TMUX_PANE)

    Returns:
        List of PaneInfo objects for each pane.
    """
    if session is None:
        session = get_current_session()
        if session is None:
            raise RuntimeError("Not in tmux session and no session specified")

    result = subprocess.run(
        [
            "tmux", "list-panes",
            "-t", f"{session}:0",
            "-F", "#{pane_index}:#{pane_id}:#{pane_pid}:#{pane_current_command}:#{pane_active}"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return []

    panes = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 5:
            panes.append(PaneInfo(
                index=int(parts[0]),
                pane_id=parts[1],
                pid=int(parts[2]),
                command=parts[3],
                active=parts[4] == "1"
            ))

    return panes


def send_to_pane(session: str | None, pane_index: int, text: str, enter: bool = True):
    """Send text to a specific pane.

    Args:
        session: Target session (default: auto-detect from $TMUX_PANE)
        pane_index: Target pane index
        text: Text to send
        enter: Whether to send Enter key after text
    """
    if session is None:
        session = get_current_session()
        if session is None:
            raise RuntimeError("Not in tmux session and no session specified")

    target = f"{session}:0.{pane_index}"

    # Send text first
    subprocess.run(["tmux", "send-keys", "-t", target, text], capture_output=True)

    if enter:
        # Wait for text to be displayed before sending Enter
        # Longer text needs more time (Claude Code shows "[Pasted text...]")
        wait_time = 0.5 if len(text) < 200 else 1.0
        time.sleep(wait_time)
        subprocess.run(["tmux", "send-keys", "-t", target, "Enter"], capture_output=True)

        # For multi-line text, send another Enter to confirm paste
        if "\n" in text or len(text) > 200:
            time.sleep(0.5)
            subprocess.run(["tmux", "send-keys", "-t", target, "Enter"], capture_output=True)


def capture_pane(
    session: str | None,
    pane_index: int,
    lines: int | None = None
) -> str:
    """Capture output from a specific pane.

    Args:
        session: Target session (default: auto-detect from $TMUX_PANE)
        pane_index: Target pane index
        lines: Number of lines to capture (default: all history)

    Returns:
        The captured pane content.
    """
    if session is None:
        session = get_current_session()
        if session is None:
            raise RuntimeError("Not in tmux session and no session specified")

    target = f"{session}:0.{pane_index}"
    cmd = ["tmux", "capture-pane", "-t", target, "-p"]

    if lines is None:
        # Capture full history
        cmd.extend(["-S", "-"])
    else:
        # Capture last N lines
        cmd.extend(["-S", f"-{lines}"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def kill_pane(session: str | None, pane_index: int):
    """Kill a specific pane.

    Args:
        session: Target session (default: auto-detect from $TMUX_PANE)
        pane_index: Target pane index

    Raises:
        RuntimeError: If trying to kill pane 0 (orchestrator)
    """
    if pane_index == 0:
        raise RuntimeError("Cannot kill pane 0 (orchestrator)")

    if session is None:
        session = get_current_session()
        if session is None:
            raise RuntimeError("Not in tmux session and no session specified")

    target = f"{session}:0.{pane_index}"
    subprocess.run(["tmux", "kill-pane", "-t", target], capture_output=True)


def focus_pane(session: str | None, pane_index: int):
    """Focus (jump to) a specific pane.

    Args:
        session: Target session (default: auto-detect from $TMUX_PANE)
        pane_index: Target pane index
    """
    if session is None:
        session = get_current_session()
        if session is None:
            raise RuntimeError("Not in tmux session and no session specified")

    target = f"{session}:0.{pane_index}"
    subprocess.run(["tmux", "select-pane", "-t", target], capture_output=True)


def get_pane_info(tmux_pane_id: str) -> PaneInfo | None:
    """Get info about a specific pane by its tmux ID.

    Args:
        tmux_pane_id: The pane ID (e.g., %37)

    Returns:
        PaneInfo if found, None otherwise.
    """
    result = subprocess.run(
        [
            "tmux", "display", "-t", tmux_pane_id,
            "-p", "#{pane_index}:#{pane_id}:#{pane_pid}:#{pane_current_command}:#{pane_active}"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return None

    parts = result.stdout.strip().split(":")
    if len(parts) >= 5:
        return PaneInfo(
            index=int(parts[0]),
            pane_id=parts[1],
            pid=int(parts[2]),
            command=parts[3],
            active=parts[4] == "1"
        )

    return None
