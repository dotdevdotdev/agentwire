"""Session detection for AgentWire MCP server.

Auto-detects which tmux session is calling the MCP tool by walking up the process tree.
"""

import os
import time
from typing import Optional

import psutil


class SessionDetector:
    """Detect calling tmux session from process tree."""

    def __init__(self):
        """Initialize session detector with cache."""
        self._cache = {}  # pid -> (session_name, timestamp)
        self._cache_ttl = 60  # Cache for 60 seconds

    def get_calling_session(self) -> Optional[str]:
        """
        Walk up process tree to find tmux session.

        Returns session name or None if not in tmux.
        """
        caller_pid = self._get_caller_pid()

        # Check cache first
        if caller_pid in self._cache:
            cached_session, cached_time = self._cache[caller_pid]
            if time.time() - cached_time < self._cache_ttl:
                return cached_session

        # Walk up process tree to find tmux
        try:
            process = psutil.Process(caller_pid)
            while process:
                # Check if this process is tmux
                if 'tmux' in process.name().lower():
                    session_name = self._extract_session_name(process)
                    if session_name:
                        # Cache the result
                        self._cache[caller_pid] = (session_name, time.time())
                        return session_name

                # Move to parent
                try:
                    process = process.parent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # Cache None result too (process not in tmux)
        self._cache[caller_pid] = (None, time.time())
        return None

    def _get_caller_pid(self) -> int:
        """Get PID of process that called MCP tool."""
        # MCP protocol provides this in request context
        # For now, use parent process (the Claude Code process)
        return os.getppid()

    def _extract_session_name(self, tmux_process) -> Optional[str]:
        """
        Extract session name from tmux process cmdline.

        Handles various tmux process formats:
        - tmux attach -t session-name
        - tmux: server (session-name)
        - tmux new-session -s session-name
        """
        try:
            cmdline = tmux_process.cmdline()

            # Look for -t flag (attach, send-keys, etc.)
            for i, arg in enumerate(cmdline):
                if arg == '-t' and i + 1 < len(cmdline):
                    return cmdline[i + 1]

            # Look for -s flag (new-session)
            for i, arg in enumerate(cmdline):
                if arg == '-s' and i + 1 < len(cmdline):
                    return cmdline[i + 1]

            # Try parsing from process name
            # Format: "tmux: server (session-name)"
            process_name = tmux_process.name()
            if '(' in process_name and ')' in process_name:
                return process_name.split('(')[1].rstrip(')')

        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            pass

        return None

    def get_room_for_session(self, session_name: str) -> str:
        """
        Map session name to room name.

        Session formats supported:
        - "myproject" → room "myproject"
        - "myproject/branch" → room "myproject/branch"
        - "myproject@machine" → room "myproject@machine"
        - "myproject/branch@machine" → room "myproject/branch@machine"

        Returns:
            Room name (identical to session name in AgentWire)
        """
        # Session name IS the room name in AgentWire (1:1 mapping)
        return session_name
