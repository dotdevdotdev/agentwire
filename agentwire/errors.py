"""
AgentWire error classes with actionable messages.

Follows the WHAT/WHY/HOW pattern:
- WHAT: Clear description of what went wrong
- WHY: Context to understand the cause
- HOW: Actionable steps to fix the issue
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NetworkError(Exception):
    """
    Network-related error with actionable context.

    Example usage:
        raise NetworkError(
            what="Cannot reach TTS service on gpu-server",
            why={
                "service": "tts",
                "machine": "gpu-server",
                "url": "http://localhost:8100",
                "status": "connection refused",
            },
            how=[
                "Check if tunnel is running: agentwire tunnels status",
                "Create missing tunnels: agentwire tunnels up",
                "Verify TTS is running on remote: ssh gpu-server 'curl localhost:8100/health'",
            ],
        )
    """

    what: str
    why: dict = field(default_factory=dict)
    how: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.format_message()

    def format_message(self) -> str:
        """Format error with WHAT/WHY/HOW structure."""
        lines = [f"ERROR: {self.what}"]

        if self.why:
            lines.append("")
            lines.append("Context:")
            for k, v in self.why.items():
                lines.append(f"  {k}: {v}")

        if self.how:
            lines.append("")
            lines.append("To fix:")
            for i, step in enumerate(self.how, 1):
                lines.append(f"  {i}. {step}")

        return "\n".join(lines)


@dataclass
class TunnelError(NetworkError):
    """Error related to SSH tunnel operations."""

    pass


@dataclass
class ServiceError(NetworkError):
    """Error related to service health/connectivity."""

    pass


@dataclass
class MachineError(NetworkError):
    """Error related to remote machine operations."""

    pass


# Common error factories for consistent messaging


def tunnel_not_running(
    service: str,
    machine: str,
    local_port: int,
    remote_port: int,
) -> TunnelError:
    """Create error for missing tunnel."""
    return TunnelError(
        what=f"Tunnel to {machine} is not running",
        why={
            "service": service,
            "machine": machine,
            "local_port": local_port,
            "remote_port": remote_port,
        },
        how=[
            "Create the tunnel: agentwire tunnels up",
            "Or manually: ssh -L {local_port}:localhost:{remote_port} -N -f {machine}".format(
                local_port=local_port, remote_port=remote_port, machine=machine
            ),
        ],
    )


def tunnel_creation_failed(
    machine: str,
    local_port: int,
    remote_port: int,
    ssh_error: str,
) -> TunnelError:
    """Create error for failed tunnel creation."""
    how = [
        f"Verify SSH connectivity: ssh {machine} echo ok",
        "Check SSH key is configured correctly",
        f"Ensure port {remote_port} is not blocked by firewall",
    ]

    # Add specific hints based on error
    if "permission denied" in ssh_error.lower():
        how.insert(0, "Check SSH key permissions: chmod 600 ~/.ssh/id_*")
    elif "connection refused" in ssh_error.lower():
        how.insert(0, f"Ensure {machine} is reachable and SSH is running")
    elif "host key" in ssh_error.lower():
        how.insert(0, f"Accept host key: ssh-keyscan {machine} >> ~/.ssh/known_hosts")
    elif "address already in use" in ssh_error.lower():
        how.insert(0, f"Find process using port: lsof -i :{local_port}")
        how.insert(1, "Kill stale tunnels: agentwire tunnels down")

    return TunnelError(
        what=f"Failed to create tunnel to {machine}",
        why={
            "machine": machine,
            "local_port": local_port,
            "remote_port": remote_port,
            "ssh_error": ssh_error,
        },
        how=how,
    )


def service_unreachable(
    service: str,
    url: str,
    error: Optional[str] = None,
    is_remote: bool = False,
    machine: Optional[str] = None,
) -> ServiceError:
    """Create error for unreachable service."""
    how = []

    if is_remote and machine:
        how.extend(
            [
                "Check if tunnel is running: agentwire tunnels status",
                "Create missing tunnels: agentwire tunnels up",
                f"Verify service on remote: ssh {machine} 'curl {url}/health'",
            ]
        )
    else:
        how.extend(
            [
                f"Start the service: agentwire {service} start",
                f"Check service logs: tmux attach -t agentwire-{service}",
            ]
        )

    return ServiceError(
        what=f"{service.capitalize()} service is not responding",
        why={
            "service": service,
            "url": url,
            "error": error or "connection refused",
            "location": f"remote ({machine})" if is_remote else "local",
        },
        how=how,
    )


def machine_not_found(machine_id: str, available: List[str]) -> MachineError:
    """Create error for unknown machine reference."""
    available_str = ", ".join(available) if available else "(none registered)"

    return MachineError(
        what=f"Machine '{machine_id}' not found in configuration",
        why={
            "machine": machine_id,
            "available_machines": available_str,
            "config_file": "~/.agentwire/machines.json",
        },
        how=[
            f"Add the machine: agentwire machine add {machine_id} --host <ip-or-hostname>",
            "Or fix the machine ID in config.yaml services section",
        ],
    )


def ssh_unreachable(
    machine_id: str,
    host: str,
    user: Optional[str] = None,
    error: Optional[str] = None,
) -> MachineError:
    """Create error for SSH connectivity failure."""
    target = f"{user}@{host}" if user else host

    return MachineError(
        what=f"Cannot reach {machine_id} via SSH",
        why={
            "machine": machine_id,
            "ssh_target": target,
            "error": error or "connection timed out",
        },
        how=[
            f"Test connectivity: ssh -o ConnectTimeout=5 {target} echo ok",
            "Check if machine is powered on and network is reachable",
            "Verify SSH key is configured: ssh-add -l",
            f"Check ~/.ssh/config has correct settings for {host}",
        ],
    )
