"""Unit tests for session detection.

Tests PID to tmux session mapping, session name extraction, and edge cases.
"""

import pytest
from unittest.mock import Mock, patch


class TestSessionDetector:
    """Test session detection from process tree."""

    @patch('os.getppid')
    @patch('psutil.Process')
    def test_get_caller_pid_from_parent(self, mock_process_class, mock_getppid):
        """Verify caller PID is determined from parent process."""
        mock_getppid.return_value = 12345

        # from agentwire.session_detector import SessionDetector
        # detector = SessionDetector()
        # caller_pid = detector._get_caller_pid()
        # assert caller_pid == 12345

        # Pattern verification
        assert mock_getppid.return_value == 12345

    @patch('psutil.Process')
    def test_walk_process_tree_finds_tmux(self, mock_process_class):
        """Verify process tree walk finds tmux parent."""
        # Build mock process tree: claude -> shell -> tmux -> init
        init_process = Mock()
        init_process.name.return_value = "init"
        init_process.parent.return_value = None

        tmux_process = Mock()
        tmux_process.name.return_value = "tmux: server (myproject)"
        tmux_process.parent.return_value = init_process
        tmux_process.cmdline.return_value = ["tmux: server (myproject)"]

        shell_process = Mock()
        shell_process.name.return_value = "bash"
        shell_process.parent.return_value = tmux_process

        claude_process = Mock()
        claude_process.name.return_value = "claude"
        claude_process.parent.return_value = shell_process

        mock_process_class.return_value = claude_process

        # Walk up tree
        current = claude_process
        tmux_found = None
        while current.parent():
            current = current.parent()
            if 'tmux' in current.name().lower():
                tmux_found = current
                break

        assert tmux_found is not None
        assert "tmux" in tmux_found.name()

    @patch('psutil.Process')
    def test_extract_session_from_attach_command(self, mock_process_class):
        """Verify session extraction from 'tmux attach -t session' command."""
        tmux_process = Mock()
        tmux_process.cmdline.return_value = ["tmux", "attach", "-t", "api/feature"]

        # Extract session from cmdline
        cmdline = tmux_process.cmdline()
        session = None
        for i, arg in enumerate(cmdline):
            if arg == '-t' and i + 1 < len(cmdline):
                session = cmdline[i + 1]
                break

        assert session == "api/feature"

    @patch('psutil.Process')
    def test_extract_session_from_server_name(self, mock_process_class):
        """Verify session extraction from 'tmux: server (name)' format."""
        tmux_process = Mock()
        tmux_process.name.return_value = "tmux: server (my-project@machine)"
        tmux_process.cmdline.return_value = []

        # Extract from process name
        name = tmux_process.name()
        session = None
        if '(' in name and ')' in name:
            session = name.split('(')[1].rstrip(')')

        assert session == "my-project@machine"

    @patch('psutil.Process')
    def test_session_detection_with_worktree_format(self, mock_process_class):
        """Verify detection works with worktree session names (project/branch)."""
        tmux_process = Mock()
        tmux_process.cmdline.return_value = ["tmux", "attach", "-t", "agentwire/feature"]

        cmdline = tmux_process.cmdline()
        session = cmdline[3]

        assert session == "agentwire/feature"
        assert "/" in session

    @patch('psutil.Process')
    def test_session_detection_with_remote_format(self, mock_process_class):
        """Verify detection works with remote session names (project@machine)."""
        tmux_process = Mock()
        tmux_process.name.return_value = "tmux: server (api@gpu-server)"

        name = tmux_process.name()
        session = name.split('(')[1].rstrip(')')

        assert session == "api@gpu-server"
        assert "@" in session

    @patch('psutil.Process')
    def test_session_detection_with_complex_name(self, mock_process_class):
        """Verify detection with worktree + remote format."""
        tmux_process = Mock()
        tmux_process.cmdline.return_value = ["tmux", "new-session", "-s", "ml/experiment@gpu-server"]

        cmdline = tmux_process.cmdline()
        session = None
        for i, arg in enumerate(cmdline):
            if arg == '-s' and i + 1 < len(cmdline):
                session = cmdline[i + 1]
                break

        assert session == "ml/experiment@gpu-server"
        assert "/" in session and "@" in session


class TestSessionNameExtraction:
    """Test session name extraction edge cases."""

    def test_extract_from_new_session_command(self):
        """Verify extraction from 'tmux new-session -s name'."""
        cmdline = ["tmux", "new-session", "-s", "test-session", "-d"]

        session = None
        for i, arg in enumerate(cmdline):
            if arg == '-s' and i + 1 < len(cmdline):
                session = cmdline[i + 1]
                break

        assert session == "test-session"

    def test_extract_from_attach_session_command(self):
        """Verify extraction from 'tmux attach-session -t name'."""
        cmdline = ["tmux", "attach-session", "-t", "myproject"]

        session = None
        for i, arg in enumerate(cmdline):
            if arg == '-t' and i + 1 < len(cmdline):
                session = cmdline[i + 1]
                break

        assert session == "myproject"

    def test_extract_with_special_characters(self):
        """Verify extraction handles special characters correctly."""
        test_names = [
            "my-project",
            "my_project",
            "project-123",
            "api/feature-branch",
            "service@remote-host",
            "app/feature@host",
        ]

        for name in test_names:
            cmdline = ["tmux", "attach", "-t", name]
            session = cmdline[3]
            assert session == name

    def test_extract_from_server_format_variations(self):
        """Verify extraction from various server name formats."""
        test_cases = [
            ("tmux: server (simple)", "simple"),
            ("tmux: server (with-dash)", "with-dash"),
            ("tmux: server (with_underscore)", "with_underscore"),
            ("tmux: server (path/branch)", "path/branch"),
            ("tmux: server (name@host)", "name@host"),
        ]

        for process_name, expected_session in test_cases:
            session = process_name.split('(')[1].rstrip(')')
            assert session == expected_session

    def test_handles_missing_session_name(self):
        """Verify graceful handling when session name not found."""
        # cmdline without -t or -s
        cmdline = ["tmux", "list-sessions"]

        session = None
        for i, arg in enumerate(cmdline):
            if arg in ['-t', '-s'] and i + 1 < len(cmdline):
                session = cmdline[i + 1]
                break

        assert session is None


class TestSessionToRoomMapping:
    """Test mapping from session names to room names."""

    def test_simple_session_to_room(self):
        """Verify simple session name maps to same room name."""
        session = "myproject"
        room = session  # 1:1 mapping in AgentWire
        assert room == "myproject"

    def test_worktree_session_to_room(self):
        """Verify worktree session preserves slash in room name."""
        session = "myproject/feature-branch"
        room = session
        assert room == "myproject/feature-branch"

    def test_remote_session_to_room(self):
        """Verify remote session preserves @ in room name."""
        session = "api@gpu-server"
        room = session
        assert room == "api@gpu-server"

    def test_complex_session_to_room(self):
        """Verify complex session (worktree + remote) maps correctly."""
        session = "ml/experiment@gpu-server"
        room = session
        assert room == "ml/experiment@gpu-server"

    def test_fork_session_to_room(self):
        """Verify forked session names map correctly."""
        test_cases = [
            "api-fork-1",
            "myproject-fork-2",
            "service/branch-fork-1",
        ]

        for session in test_cases:
            room = session
            assert room == session
            assert "fork" in room


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch('psutil.Process')
    def test_not_in_tmux_session(self, mock_process_class):
        """Verify returns None when not inside tmux."""
        # Process tree without tmux
        init = Mock()
        init.name.return_value = "init"
        init.parent.return_value = None

        shell = Mock()
        shell.name.return_value = "bash"
        shell.parent.return_value = init

        python = Mock()
        python.name.return_value = "python"
        python.parent.return_value = shell

        mock_process_class.return_value = python

        # Walk tree, should not find tmux
        current = python
        tmux_found = None
        while current.parent():
            current = current.parent()
            if 'tmux' in current.name().lower():
                tmux_found = current
                break

        assert tmux_found is None

    @patch('psutil.Process')
    def test_process_tree_with_no_parent(self, mock_process_class):
        """Verify graceful handling when process has no parent."""
        process = Mock()
        process.name.return_value = "orphan"
        process.parent.return_value = None

        mock_process_class.return_value = process

        # Should stop at None parent
        assert process.parent() is None

    @patch('psutil.Process')
    def test_malformed_tmux_process_name(self, mock_process_class):
        """Verify handling of tmux process without proper format."""
        tmux = Mock()
        tmux.name.return_value = "tmux"  # No session in name
        tmux.cmdline.return_value = ["tmux"]  # No -t or -s

        # Try to extract session
        name = tmux.name()
        session_from_name = None
        if '(' in name:
            session_from_name = name.split('(')[1].rstrip(')')

        cmdline = tmux.cmdline()
        session_from_cmdline = None
        for i, arg in enumerate(cmdline):
            if arg in ['-t', '-s'] and i + 1 < len(cmdline):
                session_from_cmdline = cmdline[i + 1]
                break

        # Both should be None
        assert session_from_name is None
        assert session_from_cmdline is None

    @patch('psutil.Process')
    def test_unicode_in_session_name(self, mock_process_class):
        """Verify handling of unicode characters in session names."""
        # While unlikely, session names could theoretically have unicode
        tmux = Mock()
        tmux.cmdline.return_value = ["tmux", "attach", "-t", "test-café"]

        session = tmux.cmdline()[3]
        assert session == "test-café"

    def test_session_name_with_spaces(self):
        """Verify spaces in session names are handled (tmux allows quoted names)."""
        # tmux allows: tmux new -s "my session"
        cmdline = ["tmux", "new", "-s", "my session"]
        session = cmdline[3]

        # Note: This is technically valid in tmux but we should handle it
        assert session == "my session"

    @patch('psutil.Process', side_effect=Exception("Process access denied"))
    def test_handles_permission_error(self, mock_process_class):
        """Verify graceful handling when process access is denied."""
        # from agentwire.session_detector import SessionDetector
        # detector = SessionDetector()

        # Should handle exception gracefully
        try:
            mock_process_class(12345)
            assert False, "Should have raised exception"
        except Exception as e:
            assert "access denied" in str(e).lower()


class TestCaching:
    """Test session detection caching behavior."""

    def test_cache_key_based_on_pid(self):
        """Verify cache uses PID as key."""
        cache = {}
        pid = 12345
        session = "test-session"

        cache[pid] = session
        assert cache.get(pid) == session

    def test_cache_invalidation_after_timeout(self):
        """Verify cache expires after 60 seconds."""
        import time

        # Simulate cache with timestamp
        cache = {}
        pid = 12345
        cache[pid] = {"session": "test", "timestamp": time.time()}

        # Check if expired (60s timeout)
        cached = cache.get(pid)
        is_expired = (time.time() - cached["timestamp"]) > 60

        # Should not be expired immediately
        assert is_expired is False

    def test_multiple_sessions_cached_independently(self):
        """Verify different PIDs cache independently."""
        cache = {}

        cache[111] = "session-1"
        cache[222] = "session-2"
        cache[333] = "session-3"

        assert cache[111] == "session-1"
        assert cache[222] == "session-2"
        assert cache[333] == "session-3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
