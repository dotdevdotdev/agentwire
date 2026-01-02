"""
SessionWatcher for real-time tmux output monitoring via pipe-pane.

This module provides the infrastructure for streaming tmux session output
through FIFOs and matching patterns against that output in real-time.
"""

import asyncio
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import aiofiles

logger = logging.getLogger(__name__)

# ANSI escape sequence pattern for stripping terminal formatting
ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*m|\x1b\].*?\x07')


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text.

    Args:
        text: Text potentially containing ANSI escape sequences.

    Returns:
        Clean text with all ANSI codes removed.
    """
    return ANSI_PATTERN.sub('', text)


class RollingBuffer:
    """Fixed-size rolling buffer of text lines for persistent trigger matching.

    Maintains the last N lines of output, allowing patterns that span multiple
    chunks or persist on screen to be detected.

    Attributes:
        max_lines: Maximum number of lines to retain.
    """

    def __init__(self, max_lines: int = 100):
        """Initialize the rolling buffer.

        Args:
            max_lines: Maximum number of lines to keep in the buffer.
        """
        self.max_lines = max_lines
        self._lines: list[str] = []

    def append(self, text: str) -> None:
        """Append new text to the buffer, maintaining max_lines limit.

        Text is split into lines and added. If the total exceeds max_lines,
        the oldest lines are dropped.

        Args:
            text: Text to append (may contain multiple lines).
        """
        new_lines = text.splitlines(keepends=True)
        self._lines.extend(new_lines)

        # Trim to max_lines if exceeded
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines:]

    def get_text(self) -> str:
        """Get the full buffer contents as a single string.

        Returns:
            All buffered lines joined together.
        """
        return ''.join(self._lines)

    def clear(self) -> None:
        """Clear all buffered content."""
        self._lines = []

    def __len__(self) -> int:
        """Return the number of lines in the buffer."""
        return len(self._lines)


def _get_pipe_path(session: str) -> Path:
    """Get the FIFO path for a session.

    Args:
        session: The tmux session name.

    Returns:
        Path to the session's FIFO.
    """
    # Sanitize session name for filesystem (replace / and @ with -)
    safe_name = session.replace('/', '-').replace('@', '-')
    return Path(f"/tmp/agentwire-{safe_name}.pipe")


def create_fifo(session: str) -> Path:
    """Create a FIFO (named pipe) for the session.

    If the FIFO already exists, it is removed and recreated to ensure
    a clean state.

    Args:
        session: The tmux session name.

    Returns:
        Path to the created FIFO.

    Raises:
        OSError: If FIFO creation fails.
    """
    pipe_path = _get_pipe_path(session)

    # Clean up existing pipe if present
    if pipe_path.exists():
        try:
            pipe_path.unlink()
        except OSError as e:
            logger.warning(f"Failed to remove existing pipe {pipe_path}: {e}")

    # Create new FIFO
    os.mkfifo(pipe_path, mode=0o600)
    logger.debug(f"Created FIFO: {pipe_path}")
    return pipe_path


def cleanup_fifo(session: str) -> None:
    """Remove the FIFO for a session.

    Args:
        session: The tmux session name.
    """
    pipe_path = _get_pipe_path(session)
    try:
        if pipe_path.exists():
            pipe_path.unlink()
            logger.debug(f"Removed FIFO: {pipe_path}")
    except OSError as e:
        logger.warning(f"Failed to cleanup pipe {pipe_path}: {e}")


def _start_pipe_pane(session: str, pipe_path: Path) -> bool:
    """Start tmux pipe-pane to stream output to FIFO.

    Args:
        session: The tmux session name.
        pipe_path: Path to the FIFO.

    Returns:
        True if pipe-pane started successfully, False otherwise.
    """
    try:
        result = subprocess.run(
            ["tmux", "pipe-pane", "-t", session, f"cat >> {pipe_path}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.debug(f"Started pipe-pane for {session}")
            return True
        else:
            logger.error(f"pipe-pane failed for {session}: {result.stderr}")
            return False
    except FileNotFoundError:
        logger.error("tmux not found")
        return False
    except Exception as e:
        logger.error(f"Failed to start pipe-pane for {session}: {e}")
        return False


def _stop_pipe_pane(session: str) -> bool:
    """Stop tmux pipe-pane for a session.

    Args:
        session: The tmux session name.

    Returns:
        True if pipe-pane stopped successfully, False otherwise.
    """
    try:
        result = subprocess.run(
            ["tmux", "pipe-pane", "-t", session],  # Empty command stops piping
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.debug(f"Stopped pipe-pane for {session}")
            return True
        else:
            # Session might not exist anymore - not an error
            logger.debug(f"pipe-pane stop returned {result.returncode} for {session}")
            return True
    except Exception as e:
        logger.warning(f"Failed to stop pipe-pane for {session}: {e}")
        return False


@dataclass
class SessionWatcher:
    """Watches a tmux session via pipe-pane, streaming output through a FIFO.

    This class manages the lifecycle of real-time output monitoring for a
    tmux session. It creates a FIFO, starts pipe-pane to stream output,
    and provides an async iteration interface for reading chunks.

    Attributes:
        session: The tmux session name to watch.
        buffer: Rolling buffer for persistent pattern matching.
        on_chunk: Optional callback invoked for each chunk received.
    """

    session: str
    buffer: RollingBuffer = field(default_factory=lambda: RollingBuffer(max_lines=100))
    on_chunk: Callable[[str], None] | None = None

    _pipe_path: Path | None = field(default=None, init=False, repr=False)
    _task: asyncio.Task | None = field(default=None, init=False, repr=False)
    _running: bool = field(default=False, init=False, repr=False)

    @property
    def pipe_path(self) -> Path | None:
        """Get the current FIFO path, or None if not started."""
        return self._pipe_path

    @property
    def running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running

    async def start(self) -> bool:
        """Start watching the session.

        Creates the FIFO, starts pipe-pane, and begins the async read loop.

        Returns:
            True if started successfully, False otherwise.
        """
        if self._running:
            logger.warning(f"Watcher for {self.session} already running")
            return True

        # Create FIFO
        try:
            self._pipe_path = create_fifo(self.session)
        except OSError as e:
            logger.error(f"Failed to create FIFO for {self.session}: {e}")
            return False

        # Start pipe-pane
        if not _start_pipe_pane(self.session, self._pipe_path):
            cleanup_fifo(self.session)
            self._pipe_path = None
            return False

        # Start async read loop
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info(f"Started watcher for session: {self.session}")
        return True

    async def stop(self) -> None:
        """Stop watching the session.

        Cancels the read loop, stops pipe-pane, and cleans up the FIFO.
        """
        if not self._running:
            return

        self._running = False

        # Cancel the read task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Stop pipe-pane
        _stop_pipe_pane(self.session)

        # Cleanup FIFO
        cleanup_fifo(self.session)
        self._pipe_path = None

        logger.info(f"Stopped watcher for session: {self.session}")

    async def _watch_loop(self) -> None:
        """Async loop that reads from the FIFO and processes chunks.

        This loop opens the FIFO in read mode and iterates over incoming
        data. Each chunk is stripped of ANSI codes, added to the buffer,
        and passed to the on_chunk callback if set.

        The loop handles EOF gracefully (session ended) and continues
        running until explicitly stopped.
        """
        if not self._pipe_path:
            return

        while self._running:
            try:
                # Open FIFO for reading (blocks until writer connects)
                # Using 'r' mode - FIFO acts like a regular file with async reads
                async with aiofiles.open(self._pipe_path, 'r') as f:
                    async for chunk in f:
                        if not self._running:
                            break

                        if not chunk:
                            # EOF - writer disconnected
                            continue

                        # Strip ANSI codes
                        clean_chunk = strip_ansi(chunk)

                        # Add to buffer for persistent matching
                        self.buffer.append(clean_chunk)

                        # Invoke callback if set
                        if self.on_chunk:
                            try:
                                self.on_chunk(clean_chunk)
                            except Exception as e:
                                logger.error(f"on_chunk callback error: {e}")

            except asyncio.CancelledError:
                break
            except FileNotFoundError:
                # FIFO was removed - watcher should stop
                logger.warning(f"FIFO disappeared for {self.session}")
                break
            except OSError as e:
                if self._running:
                    logger.error(f"FIFO read error for {self.session}: {e}")
                    # Brief delay before retrying
                    await asyncio.sleep(0.1)
            except Exception as e:
                if self._running:
                    logger.error(f"Unexpected error in watcher loop for {self.session}: {e}")
                    await asyncio.sleep(0.1)
