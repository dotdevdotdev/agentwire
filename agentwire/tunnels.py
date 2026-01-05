"""
SSH tunnel management for AgentWire.

Creates and monitors SSH tunnels to reach remote services.
"""

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .network import NetworkContext, TunnelSpec


@dataclass
class TunnelStatus:
    """Status of a tunnel."""

    spec: TunnelSpec
    status: str  # "up", "down", "error"
    pid: Optional[int] = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None


class TunnelManager:
    """Manages SSH tunnels for reaching remote services."""

    def __init__(self, state_dir: Optional[Path] = None):
        """
        Initialize tunnel manager.

        Args:
            state_dir: Directory to store tunnel state (PIDs, etc.)
                      Defaults to ~/.agentwire/tunnels/
        """
        self.state_dir = state_dir or (Path.home() / ".agentwire" / "tunnels")
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_state_file(self, spec: TunnelSpec) -> Path:
        """Get path to state file for a tunnel."""
        return self.state_dir / f"{spec.id}.json"

    def _get_ssh_target(self, machine_id: str, ctx: Optional[NetworkContext] = None) -> Optional[str]:
        """Get SSH target (user@host) for a machine."""
        if ctx is None:
            ctx = NetworkContext.from_config()

        machine = ctx.machines.get(machine_id)
        if machine is None:
            return None

        host = machine.get("host", machine_id)
        user = machine.get("user")

        if user:
            return f"{user}@{host}"
        return host

    def check_tunnel(self, spec: TunnelSpec) -> TunnelStatus:
        """
        Check if a tunnel is running.

        Checks:
        1. State file exists with PID
        2. Process is actually running
        3. Local port is listening (optional)

        Returns:
            TunnelStatus with current state
        """
        state_file = self._get_state_file(spec)

        if not state_file.exists():
            return TunnelStatus(spec=spec, status="down")

        try:
            state = json.loads(state_file.read_text())
            pid = state.get("pid")

            if pid is None:
                return TunnelStatus(spec=spec, status="down")

            # Check if process is running
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
            except (OSError, ProcessLookupError):
                # Process not running, clean up state file
                state_file.unlink(missing_ok=True)
                return TunnelStatus(spec=spec, status="down")

            # Process is running
            return TunnelStatus(spec=spec, status="up", pid=pid)

        except (json.JSONDecodeError, IOError) as e:
            return TunnelStatus(spec=spec, status="error", error=str(e))

    def create_tunnel(self, spec: TunnelSpec, ctx: Optional[NetworkContext] = None) -> TunnelStatus:
        """
        Create an SSH tunnel.

        Uses: ssh -L local_port:localhost:remote_port -N -f user@host

        Args:
            spec: Tunnel specification
            ctx: Optional NetworkContext (loaded if not provided)

        Returns:
            TunnelStatus with result
        """
        # Check if already running
        existing = self.check_tunnel(spec)
        if existing.status == "up":
            return existing

        # Get SSH target
        ssh_target = self._get_ssh_target(spec.remote_machine, ctx)
        if ssh_target is None:
            return TunnelStatus(
                spec=spec,
                status="error",
                error=f"Machine '{spec.remote_machine}' not found in machines.json",
            )

        # Build SSH command
        # -L local_port:localhost:remote_port - Port forwarding
        # -N - Don't execute remote command
        # -f - Go to background
        # -o ExitOnForwardFailure=yes - Exit if port forward fails
        # -o ServerAliveInterval=60 - Keep connection alive
        # -o ServerAliveCountMax=3 - Max missed keepalives
        cmd = [
            "ssh",
            "-L", f"{spec.local_port}:localhost:{spec.remote_port}",
            "-N",
            "-f",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=3",
            ssh_target,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return TunnelStatus(
                    spec=spec,
                    status="error",
                    error=result.stderr.strip() or f"SSH exited with code {result.returncode}",
                )

            # Find the PID of the SSH process
            # The -f flag backgrounds the process, so we need to find it
            pid = self._find_tunnel_pid(spec)

            if pid:
                # Save state
                state = {"pid": pid, "spec": {"local_port": spec.local_port, "remote_machine": spec.remote_machine, "remote_port": spec.remote_port}}
                self._get_state_file(spec).write_text(json.dumps(state))

                return TunnelStatus(spec=spec, status="up", pid=pid)
            else:
                return TunnelStatus(
                    spec=spec,
                    status="error",
                    error="SSH started but could not find process",
                )

        except subprocess.TimeoutExpired:
            return TunnelStatus(spec=spec, status="error", error="SSH connection timed out")
        except Exception as e:
            return TunnelStatus(spec=spec, status="error", error=str(e))

    def _find_tunnel_pid(self, spec: TunnelSpec) -> Optional[int]:
        """Find the PID of an SSH tunnel process."""
        # Use pgrep to find SSH processes with our port forward
        try:
            # Look for: ssh -L <local_port>:localhost:<remote_port>
            pattern = f"-L.*{spec.local_port}:localhost:{spec.remote_port}"
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Return first matching PID
                pids = result.stdout.strip().split("\n")
                return int(pids[0])

        except Exception:
            pass

        return None

    def destroy_tunnel(self, spec: TunnelSpec) -> TunnelStatus:
        """
        Destroy an SSH tunnel.

        Args:
            spec: Tunnel specification

        Returns:
            TunnelStatus (should be "down" if successful)
        """
        status = self.check_tunnel(spec)

        if status.status == "down":
            return status

        if status.pid:
            try:
                os.kill(status.pid, signal.SIGTERM)
                # Wait a bit for graceful shutdown
                time.sleep(0.5)

                # Check if still running
                try:
                    os.kill(status.pid, 0)
                    # Still running, force kill
                    os.kill(status.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass  # Process is gone

            except (OSError, ProcessLookupError):
                pass  # Process already gone

        # Clean up state file
        self._get_state_file(spec).unlink(missing_ok=True)

        return TunnelStatus(spec=spec, status="down")

    def ensure_tunnels(self, ctx: Optional[NetworkContext] = None) -> list[TunnelStatus]:
        """
        Ensure all required tunnels are running.

        Args:
            ctx: Optional NetworkContext (loaded if not provided)

        Returns:
            List of TunnelStatus for all required tunnels
        """
        if ctx is None:
            ctx = NetworkContext.from_config()

        results = []

        for spec in ctx.get_required_tunnels():
            status = self.check_tunnel(spec)

            if status.status != "up":
                status = self.create_tunnel(spec, ctx)

            results.append(status)

        return results

    def list_tunnels(self) -> list[TunnelStatus]:
        """
        List all known tunnels from state files.

        Returns:
            List of TunnelStatus for all tracked tunnels
        """
        results = []

        for state_file in self.state_dir.glob("*.json"):
            try:
                state = json.loads(state_file.read_text())
                spec_data = state.get("spec", {})

                spec = TunnelSpec(
                    local_port=spec_data.get("local_port", 0),
                    remote_machine=spec_data.get("remote_machine", "unknown"),
                    remote_port=spec_data.get("remote_port", 0),
                )

                status = self.check_tunnel(spec)
                results.append(status)

            except (json.JSONDecodeError, IOError):
                continue

        return results

    def destroy_all_tunnels(self) -> int:
        """
        Destroy all managed tunnels.

        Returns:
            Number of tunnels destroyed
        """
        count = 0
        for status in self.list_tunnels():
            if status.status == "up":
                self.destroy_tunnel(status.spec)
                count += 1
        return count


def test_ssh_connectivity(host: str, user: Optional[str] = None, timeout: int = 5) -> Optional[int]:
    """
    Test SSH connectivity to a host.

    Args:
        host: Hostname or IP
        user: Optional username
        timeout: Connection timeout in seconds

    Returns:
        Latency in milliseconds, or None if unreachable
    """
    target = f"{user}@{host}" if user else host

    start = time.time()
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", "ConnectTimeout=" + str(timeout),
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "BatchMode=yes",
                target,
                "echo ok",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )

        if result.returncode == 0:
            elapsed = time.time() - start
            return int(elapsed * 1000)

    except (subprocess.TimeoutExpired, Exception):
        pass

    return None


def test_service_health(url: str, timeout: int = 5) -> tuple[bool, Optional[str]]:
    """
    Test if a service is responding.

    Args:
        url: Full URL to health endpoint
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    import urllib.request
    import urllib.error
    import ssl

    try:
        # Create SSL context that accepts self-signed certs
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            if response.status == 200:
                return True, None
            return False, f"HTTP {response.status}"

    except urllib.error.URLError as e:
        return False, str(e.reason)
    except Exception as e:
        return False, str(e)
