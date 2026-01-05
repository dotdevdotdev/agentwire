"""
Network context helper for AgentWire.

Understands network topology and routing between machines and services.
"""

import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import Config, get_config


@dataclass
class TunnelSpec:
    """Specification for an SSH tunnel."""

    local_port: int
    remote_machine: str
    remote_port: int

    @property
    def id(self) -> str:
        """Unique identifier for this tunnel spec."""
        return f"{self.local_port}-{self.remote_machine}-{self.remote_port}"


class NetworkContext:
    """Understands the network topology and how to reach services."""

    def __init__(self, config: Config, machines: list[dict]):
        """
        Initialize with config and machines list.

        Args:
            config: Loaded Config object (with services section)
            machines: List of machine dicts from machines.json
        """
        self.config = config
        self.machines = {m["id"]: m for m in machines if "id" in m}
        self.local_machine_id = self._detect_local_machine()

    def _detect_local_machine(self) -> Optional[str]:
        """
        Detect which machine we're running on.

        Matches current hostname against machine IDs and hosts.
        Returns None if not a registered machine (standalone mode).
        """
        hostname = socket.gethostname().lower()

        for machine_id, machine in self.machines.items():
            # Check if hostname matches machine ID
            if machine_id.lower() == hostname:
                return machine_id

            # Check if hostname matches host field
            host = machine.get("host", "").lower()
            if host == hostname or host.split(".")[0] == hostname:
                return machine_id

            # Check if hostname matches the short form of host
            if hostname.split(".")[0] == host.split(".")[0] and host:
                return machine_id

        return None

    def is_local(self, service: str) -> bool:
        """
        Is this service running on the current machine?

        Args:
            service: Service name ("portal" or "tts")

        Returns:
            True if service runs locally (machine is None or matches local machine)
        """
        service_config = getattr(self.config.services, service, None)
        if service_config is None:
            return True  # Unknown service defaults to local

        machine = service_config.machine
        if machine is None:
            return True  # Explicitly local

        return machine == self.local_machine_id

    def get_service_url(self, service: str, use_tunnel: bool = True) -> str:
        """
        Get URL to reach service.

        Args:
            service: Service name ("portal" or "tts")
            use_tunnel: If True and service is remote, assume tunnel exists on localhost

        Returns:
            URL like "http://localhost:8765" or "http://192.168.1.50:8765"
        """
        service_config = getattr(self.config.services, service, None)
        if service_config is None:
            # Fallback for unknown services
            return "http://localhost:8765"

        if self.is_local(service):
            return f"http://localhost:{service_config.port}"

        if use_tunnel:
            # Assume tunnel brings remote port to localhost
            return f"http://localhost:{service_config.port}"

        # Direct connection to remote
        machine = self.machines.get(service_config.machine)
        if machine:
            host = machine.get("host", service_config.machine)
            return f"http://{host}:{service_config.port}"

        return f"http://localhost:{service_config.port}"

    def get_required_tunnels(self) -> list[TunnelSpec]:
        """
        What tunnels does THIS machine need?

        Returns tunnels needed to reach services that run on other machines.
        """
        tunnels = []

        for service_name in ["portal", "tts"]:
            service_config = getattr(self.config.services, service_name, None)
            if service_config is None:
                continue

            if not self.is_local(service_name) and service_config.machine:
                tunnels.append(
                    TunnelSpec(
                        local_port=service_config.port,
                        remote_machine=service_config.machine,
                        remote_port=service_config.port,
                    )
                )

        return tunnels

    def get_ssh_target(self, service: str) -> Optional[str]:
        """
        If service is remote, return SSH target for commands.

        Returns:
            SSH target like "user@host" or None if service is local
        """
        service_config = getattr(self.config.services, service, None)
        if service_config is None or self.is_local(service):
            return None

        machine = self.machines.get(service_config.machine)
        if machine is None:
            return None

        host = machine.get("host", service_config.machine)
        user = machine.get("user")

        if user:
            return f"{user}@{host}"
        return host

    def get_machine_for_service(self, service: str) -> Optional[str]:
        """
        Get the machine ID where a service runs.

        Args:
            service: Service name ("portal" or "tts")

        Returns:
            Machine ID or None if service runs locally
        """
        service_config = getattr(self.config.services, service, None)
        if service_config is None:
            return None
        return service_config.machine

    @classmethod
    def from_config(cls) -> "NetworkContext":
        """
        Create NetworkContext from default config location.

        Loads config and machines.json automatically.
        """
        config = get_config()

        # Load machines
        machines_file = Path.home() / ".agentwire" / "machines.json"
        machines = []
        if machines_file.exists():
            try:
                with open(machines_file) as f:
                    data = json.load(f)
                    machines = data.get("machines", [])
            except (json.JSONDecodeError, IOError):
                pass

        return cls(config, machines)
