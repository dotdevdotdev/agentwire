"""Tmux-based agent backend."""

import logging
import shlex
import subprocess
from pathlib import Path

from .base import AgentBackend

logger = logging.getLogger(__name__)

DEFAULT_AGENT_COMMAND = "claude --dangerously-skip-permissions"


class TmuxAgent(AgentBackend):
    """Agent backend using tmux sessions."""

    def __init__(self, config: dict):
        """Initialize TmuxAgent.

        Args:
            config: Configuration dict with optional keys:
                - agent.command: Command to start agent (default: claude --dangerously-skip-permissions)
                - agent.model: Model to use (for {model} placeholder)
        """
        self.config = config
        agent_config = config.get("agent", {})
        self.agent_command = agent_config.get("command", DEFAULT_AGENT_COMMAND)
        self.default_model = agent_config.get("model", "")

    def _run_local(self, cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
        """Run a command locally.

        Args:
            cmd: Command as list of strings
            capture: Whether to capture output

        Returns:
            CompletedProcess result
        """
        logger.debug(f"Running local: {' '.join(cmd)}")
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
        )

    def _run_remote(self, machine: dict, cmd: str, capture: bool = True) -> subprocess.CompletedProcess:
        """Run a command on a remote machine via SSH.

        Args:
            machine: Machine config dict with 'host' and optional 'user'
            cmd: Command string to run remotely
            capture: Whether to capture output

        Returns:
            CompletedProcess result
        """
        host = machine.get("host", "")
        user = machine.get("user", "")

        ssh_target = f"{user}@{host}" if user else host
        ssh_cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            ssh_target,
            cmd,
        ]

        logger.debug(f"Running remote on {ssh_target}: {cmd}")
        return subprocess.run(
            ssh_cmd,
            capture_output=capture,
            text=True,
        )

    def _parse_session_name(self, name: str) -> tuple[str, dict | None]:
        """Parse session name to extract machine info.

        Args:
            name: Session name, optionally with @machine suffix

        Returns:
            Tuple of (session_name, machine_config or None for local)
        """
        if "@" in name:
            session, machine_id = name.rsplit("@", 1)
            machines = self.config.get("machines", [])
            for machine in machines:
                if machine.get("id") == machine_id:
                    return session, machine
            logger.warning(f"Unknown machine: {machine_id}, treating as local")
            return name, None
        return name, None

    def _format_agent_command(self, name: str, path: Path, options: dict | None = None) -> str:
        """Format the agent command with placeholders.

        Args:
            name: Session name
            path: Working directory
            options: Additional options

        Returns:
            Formatted command string
        """
        options = options or {}
        model = options.get("model", self.default_model)

        cmd = self.agent_command
        cmd = cmd.replace("{name}", name)
        cmd = cmd.replace("{path}", str(path))
        cmd = cmd.replace("{model}", model)

        return cmd

    def create_session(self, name: str, path: Path, options: dict | None = None) -> bool:
        """Create a new tmux session and start the agent."""
        session_name, machine = self._parse_session_name(name)
        agent_cmd = self._format_agent_command(session_name, path, options)

        if machine:
            projects_dir = machine.get("projects_dir", "/home/dotdev/projects")
            remote_path = f"{projects_dir}/{path.name}" if not str(path).startswith("/") else str(path)

            cmd = (
                f"tmux new-session -d -s {shlex.quote(session_name)} -c {shlex.quote(remote_path)} && "
                f"tmux send-keys -t {shlex.quote(session_name)} {shlex.quote(agent_cmd)} Enter"
            )
            result = self._run_remote(machine, cmd)
        else:
            # Create session
            result = self._run_local([
                "tmux", "new-session", "-d",
                "-s", session_name,
                "-c", str(path),
            ])

            if result.returncode != 0:
                logger.error(f"Failed to create session: {result.stderr}")
                return False

            # Start agent
            result = self._run_local([
                "tmux", "send-keys",
                "-t", session_name,
                agent_cmd, "Enter",
            ])

        if result.returncode != 0:
            logger.error(f"Failed to start agent: {result.stderr}")
            return False

        logger.info(f"Created session '{name}' at {path}")
        return True

    def session_exists(self, name: str) -> bool:
        """Check if a tmux session exists."""
        session_name, machine = self._parse_session_name(name)

        if machine:
            cmd = f"tmux has-session -t {shlex.quote(session_name)} 2>/dev/null"
            result = self._run_remote(machine, cmd)
        else:
            result = self._run_local([
                "tmux", "has-session", "-t", session_name,
            ])

        return result.returncode == 0

    def get_output(self, name: str, lines: int = 50) -> str:
        """Get recent output from a tmux session with ANSI colors."""
        session_name, machine = self._parse_session_name(name)

        if machine:
            cmd = f"tmux capture-pane -t {shlex.quote(session_name)} -p -e -S -{lines}"
            result = self._run_remote(machine, cmd)
        else:
            result = self._run_local([
                "tmux", "capture-pane",
                "-t", session_name,
                "-p",  # Print to stdout
                "-e",  # Include ANSI escape sequences
                "-S", f"-{lines}",  # Start from N lines back
            ])

        if result.returncode != 0:
            logger.error(f"Failed to get output: {result.stderr}")
            return ""

        return result.stdout

    def send_input(self, name: str, text: str) -> bool:
        """Send input to a tmux session."""
        session_name, machine = self._parse_session_name(name)

        if machine:
            # Use base64 encoding for safe transmission of complex text
            import base64
            encoded = base64.b64encode(text.encode()).decode()
            cmd = (
                f"echo {shlex.quote(encoded)} | base64 -d | "
                f"xargs -0 tmux send-keys -t {shlex.quote(session_name)} && "
                f"tmux send-keys -t {shlex.quote(session_name)} Enter"
            )
            result = self._run_remote(machine, cmd)
        else:
            result = self._run_local([
                "tmux", "send-keys",
                "-t", session_name,
                text, "Enter",
            ])

        if result.returncode != 0:
            logger.error(f"Failed to send input: {result.stderr}")
            return False

        return True

    def kill_session(self, name: str) -> bool:
        """Terminate a tmux session."""
        session_name, machine = self._parse_session_name(name)

        if machine:
            cmd = f"tmux kill-session -t {shlex.quote(session_name)}"
            result = self._run_remote(machine, cmd)
        else:
            result = self._run_local([
                "tmux", "kill-session", "-t", session_name,
            ])

        if result.returncode != 0:
            logger.error(f"Failed to kill session: {result.stderr}")
            return False

        logger.info(f"Killed session '{name}'")
        return True

    def list_sessions(self) -> list[str]:
        """List all tmux sessions (local only for now)."""
        result = self._run_local([
            "tmux", "list-sessions", "-F", "#{session_name}",
        ])

        if result.returncode != 0:
            # tmux returns error when no sessions exist
            return []

        sessions = result.stdout.strip().split("\n")
        return [s for s in sessions if s]  # Filter empty strings
