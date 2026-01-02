"""
SessionWatcher for real-time tmux output monitoring via pipe-pane.

This module provides the infrastructure for streaming tmux session output
through FIFOs and matching patterns against that output in real-time.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import aiofiles

if TYPE_CHECKING:
    from agentwire.actions import ActionRegistry

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


@dataclass
class Trigger:
    """A pattern-based trigger that fires actions when matched.

    Triggers watch output streams and execute actions when their patterns match.
    Two modes are supported:
    - transient: Matches against each chunk as it arrives (fire for each match)
    - persistent: Matches against accumulated buffer (state tracking for appear/disappear)

    Attributes:
        name: Unique identifier for the trigger.
        pattern: Compiled regex pattern to match.
        mode: "transient" for chunk-based, "persistent" for buffer-based matching.
        action: Action name to fire on match ("tts", "popup", "notify", etc.)
        config: Action-specific configuration (template, title, etc.)
        enabled: Whether this trigger is active.
        builtin: True for built-in triggers (say_command, ask_question).
    """

    name: str
    pattern: re.Pattern[str]
    mode: Literal["transient", "persistent"]
    action: str
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    builtin: bool = False


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


def _session_exists(session: str) -> bool:
    """Check if a tmux session exists.

    Args:
        session: The tmux session name.

    Returns:
        True if session exists, False otherwise.
    """
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        logger.error("tmux not found")
        return False
    except Exception as e:
        logger.error(f"Failed to check session existence: {e}")
        return False


def _start_pipe_pane(session: str, pipe_path: Path) -> bool:
    """Start tmux pipe-pane to stream output to FIFO.

    Stops any existing pipe-pane on the session first to prevent duplicates.

    Args:
        session: The tmux session name.
        pipe_path: Path to the FIFO.

    Returns:
        True if pipe-pane started successfully, False otherwise.
    """
    try:
        # Stop any existing pipe-pane first to prevent duplicates
        subprocess.run(
            ["tmux", "pipe-pane", "-t", session],  # Empty command stops piping
            capture_output=True,
            text=True,
        )

        # Start new pipe-pane
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
    runs triggers against the output, and fires actions when patterns match.

    Attributes:
        session: The tmux session name to watch.
        triggers: List of triggers to check against output.
        actions: Action registry for firing handlers.
        room: The Room object for action handlers.
        buffer: Rolling buffer for persistent pattern matching.
    """

    session: str
    triggers: list[Trigger] = field(default_factory=list)
    actions: ActionRegistry | None = None
    room: Any = None
    buffer: RollingBuffer = field(default_factory=lambda: RollingBuffer(max_lines=100))

    # Internal state
    _pipe_path: Path | None = field(default=None, init=False, repr=False)
    _task: asyncio.Task | None = field(default=None, init=False, repr=False)
    _running: bool = field(default=False, init=False, repr=False)
    # Persistent trigger state: tracks last match for each trigger to detect appear/disappear
    _persistent_state: dict[str, re.Match[str] | None] = field(
        default_factory=dict, init=False, repr=False
    )

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
        Fails gracefully if session doesn't exist.

        Returns:
            True if started successfully, False otherwise.
        """
        if self._running:
            logger.warning(f"Watcher for {self.session} already running")
            return True

        # Check if session exists before starting
        if not _session_exists(self.session):
            logger.warning(f"Session '{self.session}' not found - watcher not started")
            return False

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
        data. Each chunk is processed for triggers and added to the buffer.

        The loop handles:
        - EOF gracefully (session ended or pipe-pane stopped)
        - FIFO removal (cleanup in progress)
        - Pipe read errors (broken pipe, etc.)
        - Session disappearing while watching

        Continues running until explicitly stopped.
        """
        if not self._pipe_path:
            return

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self._running:
            try:
                # Open FIFO for reading (blocks until writer connects)
                # Using 'r' mode - FIFO acts like a regular file with async reads
                async with aiofiles.open(self._pipe_path, 'r') as f:
                    consecutive_errors = 0  # Reset on successful open

                    async for chunk in f:
                        if not self._running:
                            break

                        if not chunk:
                            # EOF - writer disconnected (session ended or pipe-pane stopped)
                            # Check if session still exists
                            if not _session_exists(self.session):
                                logger.info(
                                    f"Session '{self.session}' ended - stopping watcher"
                                )
                                self._running = False
                                break
                            # Session exists but EOF - pipe-pane may have stopped
                            # Brief pause before reopening FIFO
                            await asyncio.sleep(0.1)
                            continue

                        # Process chunk (includes ANSI stripping, buffer append, triggers)
                        await self._process_chunk(chunk)

            except asyncio.CancelledError:
                break
            except FileNotFoundError:
                # FIFO was removed - watcher should stop
                logger.warning(f"FIFO disappeared for {self.session}")
                break
            except BrokenPipeError:
                # Pipe writer closed unexpectedly
                if self._running:
                    logger.debug(f"Broken pipe for {self.session} - will retry")
                    await asyncio.sleep(0.1)
            except OSError as e:
                if self._running:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(
                            f"Too many consecutive errors for {self.session}, "
                            f"stopping watcher: {e}"
                        )
                        break
                    logger.warning(f"FIFO read error for {self.session}: {e}")
                    # Brief delay before retrying
                    await asyncio.sleep(0.1)
            except IOError as e:
                if self._running:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(
                            f"Too many consecutive I/O errors for {self.session}, "
                            f"stopping watcher: {e}"
                        )
                        break
                    logger.warning(f"I/O error reading FIFO for {self.session}: {e}")
                    await asyncio.sleep(0.1)
            except Exception as e:
                if self._running:
                    consecutive_errors += 1
                    logger.error(
                        f"Unexpected error in watcher loop for {self.session}: {e}"
                    )
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many errors, stopping watcher for {self.session}")
                        break
                    await asyncio.sleep(0.1)

        # Cleanup on exit
        logger.debug(f"Watch loop ended for {self.session}")

    async def _process_chunk(self, chunk: str) -> None:
        """Process a chunk of output from the FIFO.

        Strips ANSI codes, adds to buffer, and runs all triggers.

        Args:
            chunk: Raw text chunk from the FIFO.
        """
        # Strip ANSI codes
        clean_chunk = strip_ansi(chunk)

        # Add to buffer for persistent matching
        self.buffer.append(clean_chunk)

        # Run transient triggers against the chunk
        await self._run_transient_triggers(clean_chunk)

        # Run persistent triggers against the buffer
        await self._run_persistent_triggers()

    async def _run_transient_triggers(self, chunk: str) -> None:
        """Run transient triggers against a chunk of text.

        Transient triggers match against each chunk as it arrives.
        Each match fires the action immediately.

        Args:
            chunk: Clean text chunk (ANSI codes already stripped).
        """
        for trigger in self.triggers:
            if not trigger.enabled:
                continue
            if trigger.mode != "transient":
                continue

            # Find all matches in the chunk
            for match in trigger.pattern.finditer(chunk):
                await self._fire_action(trigger, match)

    async def _run_persistent_triggers(self) -> None:
        """Run persistent triggers against the buffer.

        Persistent triggers track state to detect when patterns appear or
        disappear from the buffer. Actions fire on state transitions:
        - appear: None -> match (pattern newly found)
        - disappear: match -> None (pattern no longer present)

        The config can specify "on": "appear" (default), "disappear", or "both".
        """
        buffer_text = self.buffer.get_text()

        for trigger in self.triggers:
            if not trigger.enabled:
                continue
            if trigger.mode != "persistent":
                continue

            # Get current match state
            current_match = trigger.pattern.search(buffer_text)

            # Get previous match state
            prev_match = self._persistent_state.get(trigger.name)

            # Detect state transitions
            appeared = prev_match is None and current_match is not None
            disappeared = prev_match is not None and current_match is None

            # Update state
            self._persistent_state[trigger.name] = current_match

            # Fire based on configured behavior (default: appear)
            fire_on = trigger.config.get("on", "appear")

            if appeared and fire_on in ("appear", "both"):
                await self._fire_action(trigger, current_match)
            elif disappeared and fire_on in ("disappear", "both"):
                # For disappear, pass the previous match (we have no current)
                await self._fire_action(trigger, prev_match)

    async def _fire_action(self, trigger: Trigger, match: re.Match[str] | None) -> None:
        """Fire the action for a trigger match.

        Args:
            trigger: The trigger that matched.
            match: The regex match object (may be None for disappear events).
        """
        if match is None:
            return

        if self.actions is None:
            logger.debug(
                "Trigger '%s' matched but no action registry configured", trigger.name
            )
            return

        logger.debug(
            "Firing trigger '%s' action '%s' for match: %s",
            trigger.name,
            trigger.action,
            match.group(0)[:50],
        )

        await self.actions.fire(trigger.action, trigger, match, self.room)
