"""CLI entry point for AgentWire."""

import argparse
import base64
import datetime
import importlib.resources
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .worktree import parse_session_name, get_session_path, ensure_worktree, remove_worktree
from . import cli_safety
from .roles import RoleConfig, load_roles, merge_roles
from .project_config import ProjectConfig, SessionType, save_project_config, get_voice_from_config, load_project_config
from . import pane_manager

# Default config directory
CONFIG_DIR = Path.home() / ".agentwire"

def _build_claude_cmd(
    session_type: SessionType,
    roles: list[RoleConfig] | None = None,
) -> str:
    """Build the claude command with appropriate flags.

    Args:
        session_type: Session execution mode (bare, claude-bypass, etc.)
        roles: List of RoleConfig objects to apply (merged for tools/instructions)

    Returns:
        The claude command string to execute, or empty string for bare sessions
    """
    if session_type == SessionType.BARE:
        return ""  # No Claude for bare sessions

    parts = ["claude"]

    # Add session type flags
    parts.extend(session_type.to_cli_flags())

    if roles:
        # Merge all roles
        merged = merge_roles(roles)

        # Add tools whitelist if any role specifies tools
        if merged.tools:
            parts.append("--tools " + " ".join(sorted(merged.tools)))

        # Add disallowed tools (intersection - only block if ALL roles agree)
        if merged.disallowed_tools:
            parts.append("--disallowedTools " + " ".join(sorted(merged.disallowed_tools)))

        # Concatenate all instructions via --append-system-prompt
        if merged.instructions:
            # Write merged instructions to a temp approach - use heredoc
            # Escape any double quotes and dollar signs in instructions
            escaped = merged.instructions.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
            parts.append(f'--append-system-prompt "{escaped}"')

        # Model override (last non-None wins)
        if merged.model:
            parts.append(f"--model {merged.model}")

    return " ".join(parts)


def check_python_version() -> bool:
    """Check if Python version meets minimum requirements.

    Returns:
        True if version is acceptable, False otherwise (exits with message).
    """
    min_version = (3, 10)
    current_version = sys.version_info[:2]

    if current_version < min_version:
        print(f"⚠️  Python {current_version[0]}.{current_version[1]} detected")
        print(f"   AgentWire requires Python {min_version[0]}.{min_version[1]} or higher")
        print()

        if sys.platform == "darwin":
            print("Install Python 3.12 on macOS:")
            print("  brew install python@3.12")
            print("  # or")
            print("  pyenv install 3.12.0 && pyenv global 3.12.0")
        elif sys.platform.startswith("linux"):
            print("Install Python 3.12 on Ubuntu/Debian:")
            print("  sudo apt update && sudo apt install python3.12")
        else:
            print("Install Python 3.12 from:")
            print("  https://www.python.org/downloads/")

        print()
        return False

    return True


def check_pip_environment() -> bool:
    """Check if we're in an externally-managed environment (Ubuntu 24.04+).

    Returns:
        True if environment is OK to proceed, False if user should take action.
    """
    if not sys.platform.startswith('linux'):
        return True

    # Check for EXTERNALLY-MANAGED marker
    marker = Path(sys.prefix) / "EXTERNALLY-MANAGED"
    if marker.exists():
        print("⚠️  Externally-managed Python environment detected (Ubuntu 24.04+)")
        print()
        print("Ubuntu prevents pip from installing packages system-wide to avoid conflicts.")
        print()
        print("Recommended approach - Use venv:")
        print("  python3 -m venv ~/.agentwire-venv")
        print("  source ~/.agentwire-venv/bin/activate")
        print("  pip install agentwire-dev")
        print()
        print("  Add to ~/.bashrc for persistence:")
        print("  echo 'source ~/.agentwire-venv/bin/activate' >> ~/.bashrc")
        print()
        print("Alternative (not recommended):")
        print("  pip3 install --break-system-packages agentwire-dev")
        print()
        return False

    return True


def generate_certs() -> int:
    """Generate self-signed SSL certificates."""
    cert_dir = CONFIG_DIR
    cert_dir.mkdir(parents=True, exist_ok=True)

    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        print(f"Certificates already exist at {cert_dir}")
        response = input("Overwrite? [y/N] ").strip().lower()
        if response != "y":
            print("Aborted.")
            return 1

    print(f"Generating self-signed certificates in {cert_dir}...")

    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:4096",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate certificates: {e.stderr}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("openssl not found. Please install OpenSSL.", file=sys.stderr)
        return 1

    print(f"Created: {cert_path}")
    print(f"Created: {key_path}")
    return 0


def tmux_session_exists(name: str) -> bool:
    """Check if a tmux session exists (exact match)."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={name}"],  # = prefix for exact match
        capture_output=True,
    )
    return result.returncode == 0


def load_config() -> dict:
    """Load configuration from ~/.agentwire/config.yaml."""
    config_path = CONFIG_DIR / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


# === Wave 2: Remote Infrastructure Helpers ===


def _get_machine_config(machine_id: str) -> dict | None:
    """Load machine config from machines.json.

    Returns:
        Machine dict with id, host, user, projects_dir, etc.
        None if machine not found.
    """
    machines_file = CONFIG_DIR / "machines.json"
    if not machines_file.exists():
        return None

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    machines = machines_data.get("machines", [])
    for m in machines:
        if m.get("id") == machine_id:
            return m

    return None


def _parse_session_target(name: str) -> tuple[str, str | None]:
    """Parse 'session@machine' into (session, machine_id).

    Examples:
        "myapp" -> ("myapp", None)
        "myapp@gpu-server" -> ("myapp", "gpu-server")
        "myapp/feature@gpu-server" -> ("myapp/feature", "gpu-server")
    """
    if "@" in name:
        session, machine = name.rsplit("@", 1)
        return session, machine
    return name, None


def _run_remote(machine_id: str, command: str) -> subprocess.CompletedProcess:
    """Run command on remote machine via SSH.

    Args:
        machine_id: Machine ID from machines.json
        command: Shell command to run

    Returns:
        subprocess.CompletedProcess with stdout, stderr, returncode
    """
    machine = _get_machine_config(machine_id)
    if machine is None:
        # Return a failed result
        result = subprocess.CompletedProcess(
            args=["ssh", machine_id, command],
            returncode=1,
            stdout="",
            stderr=f"Machine '{machine_id}' not found in machines.json",
        )
        return result

    host = machine.get("host", machine_id)
    user = machine.get("user")
    port = machine.get("port")

    # Build SSH target
    if user:
        ssh_target = f"{user}@{host}"
    else:
        ssh_target = host

    # Build SSH command with optional port and connection timeout
    ssh_cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes"]
    if port:
        ssh_cmd.extend(["-p", str(port)])
    ssh_cmd.extend([ssh_target, command])

    try:
        return subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=10,  # Hard timeout for command execution
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=ssh_cmd,
            returncode=1,
            stdout="",
            stderr=f"SSH connection to {machine_id} timed out",
        )


def _get_all_machines() -> list[dict]:
    """Get list of all registered machines from machines.json."""
    machines_file = CONFIG_DIR / "machines.json"
    if not machines_file.exists():
        return []

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
            return machines_data.get("machines", [])
    except (json.JSONDecodeError, IOError):
        return []


def _output_json(data: dict) -> None:
    """Output JSON to stdout."""
    print(json.dumps(data, indent=2))


def _output_result(success: bool, json_mode: bool, message: str = "", **kwargs) -> int:
    """Output result in text or JSON mode.

    Returns:
        0 if success, 1 otherwise
    """
    if json_mode:
        result = {"success": success, **kwargs}
        if not success and "error" not in result:
            result["error"] = message
        _output_json(result)
    else:
        if message:
            if success:
                print(message)
            else:
                print(message, file=sys.stderr)
    return 0 if success else 1


def _notify_portal_sessions_changed():
    """Notify portal that sessions have changed so it can broadcast to clients.

    This is fire-and-forget - failures are silently ignored since the portal
    may not be running.
    """
    import urllib.request
    import ssl

    try:
        # Create SSL context that doesn't verify (localhost self-signed cert)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            "https://localhost:8765/api/sessions/refresh",
            method="POST",
            data=b"",
        )
        urllib.request.urlopen(req, timeout=2, context=ctx)
    except Exception:
        # Portal may not be running - that's fine
        pass


# === Portal Commands ===


def _start_portal_local(args) -> int:
    """Start portal locally in tmux."""
    from .network import NetworkContext
    from .tunnels import TunnelManager

    session_name = "agentwire-portal"

    if tmux_session_exists(session_name):
        print(f"Portal already running in tmux session '{session_name}'")
        print(f"Attaching... (Ctrl+B D to detach)")
        subprocess.run(["tmux", "attach-session", "-t", session_name])
        return 0

    # Ensure required tunnels are up before starting portal
    ctx = NetworkContext.from_config()
    required_tunnels = ctx.get_required_tunnels()

    if required_tunnels:
        print("Ensuring tunnels to remote services...")
        tm = TunnelManager()

        for spec in required_tunnels:
            status = tm.check_tunnel(spec)

            if status.status == "up":
                print(f"  [ok] {spec.remote_machine}:{spec.remote_port} (already up)")
            else:
                print(f"  [..] Creating tunnel to {spec.remote_machine}:{spec.remote_port}...", end=" ", flush=True)
                result = tm.create_tunnel(spec, ctx)

                if result.status == "up":
                    print(f"[ok]")
                else:
                    print(f"[!!]")
                    print(f"      Warning: Could not create tunnel: {result.error}")
                    print(f"      The portal may not be able to reach {spec.remote_machine}.")

        print()

    # Build the server command
    # --dev runs from source with uv run (picks up code changes immediately)
    if getattr(args, 'dev', False):
        cmd_parts = ["uv", "run", "python", "-m", "agentwire", "portal", "serve"]
    else:
        cmd_parts = ["agentwire", "portal", "serve"]

    if args.port:
        cmd_parts.extend(["--port", str(args.port)])
    if args.host:
        cmd_parts.extend(["--host", args.host])
    if args.no_tts:
        cmd_parts.append("--no-tts")
    if args.no_stt:
        cmd_parts.append("--no-stt")
    if args.config:
        cmd_parts.extend(["--config", str(args.config)])

    server_cmd = " ".join(cmd_parts)

    # Create tmux session and start server
    mode = "dev mode (from source)" if getattr(args, 'dev', False) else "installed"
    print(f"Starting AgentWire portal ({mode}) in tmux session '{session_name}'...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
    ])
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, server_cmd, "Enter",
    ])

    print(f"Portal started. Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


def _start_portal_remote(ssh_target: str, machine_id: str, args) -> int:
    """Start portal on remote machine via SSH."""
    session_name = "agentwire-portal"

    # Check if portal already running remotely
    check_cmd = f"tmux has-session -t ={session_name} 2>/dev/null && echo running || echo stopped"
    result = subprocess.run(
        ["ssh", ssh_target, check_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Cannot reach portal machine. Check: ssh {ssh_target} echo ok", file=sys.stderr)
        return 1

    if "running" in result.stdout:
        print(f"Portal already running on {machine_id} in tmux session '{session_name}'")
        return 0

    # Build remote command
    if getattr(args, 'dev', False):
        cmd_parts = ["uv", "run", "python", "-m", "agentwire", "portal", "serve"]
    else:
        cmd_parts = ["agentwire", "portal", "serve"]

    if args.port:
        cmd_parts.extend(["--port", str(args.port)])
    if args.host:
        cmd_parts.extend(["--host", args.host])
    if args.no_tts:
        cmd_parts.append("--no-tts")
    if args.no_stt:
        cmd_parts.append("--no-stt")

    server_cmd = " ".join(cmd_parts)

    # Start remotely in tmux
    remote_cmd = f"tmux new-session -d -s {session_name} && tmux send-keys -t {session_name} {shlex.quote(server_cmd)} Enter"
    mode = "dev mode" if getattr(args, 'dev', False) else "installed"
    print(f"Starting AgentWire portal ({mode}) on {machine_id}...")

    result = subprocess.run(
        ["ssh", ssh_target, remote_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Failed to start portal on {machine_id}: {result.stderr}", file=sys.stderr)
        return 1

    print(f"Portal started on {machine_id}.")
    return 0


def _stop_portal_remote(ssh_target: str, machine_id: str) -> int:
    """Stop portal on remote machine via SSH."""
    session_name = "agentwire-portal"

    # Check if running
    check_cmd = f"tmux has-session -t ={session_name} 2>/dev/null && echo running || echo stopped"
    result = subprocess.run(
        ["ssh", ssh_target, check_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Cannot reach portal machine. Check: ssh {ssh_target} echo ok", file=sys.stderr)
        return 1

    if "stopped" in result.stdout:
        print(f"Portal is not running on {machine_id}.")
        return 1

    # Kill session
    kill_cmd = f"tmux kill-session -t {session_name}"
    result = subprocess.run(
        ["ssh", ssh_target, kill_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Failed to stop portal on {machine_id}: {result.stderr}", file=sys.stderr)
        return 1

    print(f"Portal stopped on {machine_id}.")
    return 0


def _check_portal_health(url: str, timeout: int = 2) -> bool:
    """Check if portal is responding at URL."""
    import urllib.request
    import ssl

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.urlopen(f"{url}/health", context=ctx, timeout=timeout)
        return req.status == 200
    except Exception:
        return False


def cmd_portal_start(args) -> int:
    """Start the AgentWire portal web server in tmux."""
    from .network import NetworkContext

    ctx = NetworkContext.from_config()

    if ctx.is_local("portal"):
        return _start_portal_local(args)

    # Portal runs on another machine
    ssh_target = ctx.get_ssh_target("portal")
    machine_id = ctx.get_machine_for_service("portal")

    if not ssh_target or not machine_id:
        print("Portal configured for remote machine but machine not found.", file=sys.stderr)
        return 1

    print(f"Portal runs on {machine_id}, starting remotely...")
    return _start_portal_remote(ssh_target, machine_id, args)


def cmd_portal_serve(args) -> int:
    """Run the web server directly (foreground)."""
    from .server import main as server_main

    server_main(
        config_path=str(args.config) if args.config else None,
        port=args.port,
        host=args.host,
        no_tts=args.no_tts,
        no_stt=args.no_stt,
    )
    return 0


def cmd_portal_stop(args) -> int:
    """Stop the AgentWire portal."""
    from .network import NetworkContext

    ctx = NetworkContext.from_config()
    session_name = "agentwire-portal"

    if ctx.is_local("portal"):
        if not tmux_session_exists(session_name):
            print("Portal is not running.")
            return 1

        subprocess.run(["tmux", "kill-session", "-t", session_name])
        print("Portal stopped.")
        return 0

    # Portal runs on another machine
    ssh_target = ctx.get_ssh_target("portal")
    machine_id = ctx.get_machine_for_service("portal")

    if not ssh_target or not machine_id:
        print("Portal configured for remote machine but machine not found.", file=sys.stderr)
        return 1

    print(f"Portal runs on {machine_id}, stopping remotely...")
    return _stop_portal_remote(ssh_target, machine_id)


def cmd_portal_status(args) -> int:
    """Check portal status."""
    from .network import NetworkContext

    ctx = NetworkContext.from_config()
    session_name = "agentwire-portal"

    if ctx.is_local("portal"):
        if tmux_session_exists(session_name):
            print(f"Portal is running in tmux session '{session_name}'")
            print(f"  Attach: tmux attach -t {session_name}")

            # Also check health endpoint
            url = ctx.get_service_url("portal", use_tunnel=False)
            if _check_portal_health(url):
                print(f"  Health: OK ({url})")
            else:
                print(f"  Health: starting or not responding yet")

            return 0
        else:
            print("Portal is not running.")
            print("  Start:  agentwire portal start")
            return 1

    # Portal runs on another machine - check via health endpoint
    machine_id = ctx.get_machine_for_service("portal")
    url = ctx.get_service_url("portal", use_tunnel=True)

    print(f"Portal runs on {machine_id}")

    if _check_portal_health(url):
        print(f"  Status: running")
        print(f"  Health: OK ({url})")
        return 0
    else:
        # Try direct connection if tunnel might not exist
        direct_url = ctx.get_service_url("portal", use_tunnel=False)
        if direct_url != url and _check_portal_health(direct_url):
            print(f"  Status: running (tunnel not working, direct OK)")
            print(f"  Health: OK ({direct_url})")
            print(f"  Hint: Run 'agentwire tunnels check' to verify tunnels")
            return 0

        print(f"  Status: not reachable")
        print(f"  Checked: {url}")
        if direct_url != url:
            print(f"  Also checked: {direct_url}")
        return 1


def cmd_portal_restart(args) -> int:
    """Restart the AgentWire portal (stop + start)."""
    import time

    print("Stopping portal...")
    stop_result = cmd_portal_stop(args)

    if stop_result != 0:
        # Portal wasn't running, just start it
        print("Portal was not running, starting fresh...")

    # Brief pause to ensure clean shutdown
    time.sleep(0.5)

    print("Starting portal...")
    return cmd_portal_start(args)


# === TTS Commands ===


def _start_tts_local(args) -> int:
    """Start TTS server locally in tmux."""
    session_name = "agentwire-tts"

    if tmux_session_exists(session_name):
        print(f"TTS server already running in tmux session '{session_name}'")
        print(f"Attaching... (Ctrl+B D to detach)")
        subprocess.run(["tmux", "attach-session", "-t", session_name])
        return 0

    # Get TTS config
    config = load_config()
    tts_config = config.get("tts", {})
    port = args.port or tts_config.get("port", 8100)
    host = args.host or tts_config.get("host", "0.0.0.0")

    # Check if uvicorn is available in current environment
    try:
        import uvicorn  # noqa: F401

        tts_cmd = f"agentwire tts serve --host {host} --port {port}"
    except ImportError:
        # TTS deps not in current env, try to find project venv
        # Look for agentwire project in common locations
        possible_paths = [
            Path.home() / "projects" / "agentwire",
            Path("/home/dotdev/projects/agentwire"),
            Path.cwd(),
        ]
        venv_path = None
        for p in possible_paths:
            venv = p / ".venv" / "bin" / "activate"
            if venv.exists():
                venv_path = p
                break

        if venv_path:
            tts_cmd = f"cd {venv_path} && source .venv/bin/activate && python -m agentwire tts serve --host {host} --port {port}"
        else:
            print("Error: TTS dependencies (uvicorn) not found.", file=sys.stderr)
            print("Install with: uv pip install -e '.[tts]'", file=sys.stderr)
            return 1

    print(f"Starting TTS server on {host}:{port}...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
    ])
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, tts_cmd, "Enter",
    ])

    print(f"TTS server started. Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


def _start_tts_remote(ssh_target: str, machine_id: str, args) -> int:
    """Start TTS server on remote machine via SSH."""
    session_name = "agentwire-tts"

    # Check if TTS already running remotely
    check_cmd = f"tmux has-session -t ={session_name} 2>/dev/null && echo running || echo stopped"
    result = subprocess.run(
        ["ssh", ssh_target, check_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Cannot reach TTS machine. Check: ssh {ssh_target} echo ok", file=sys.stderr)
        return 1

    if "running" in result.stdout:
        print(f"TTS server already running on {machine_id} in tmux session '{session_name}'")
        return 0

    # Get port config
    config = load_config()
    tts_config = config.get("tts", {})
    port = args.port or tts_config.get("port", 8100)
    host = args.host or tts_config.get("host", "0.0.0.0")

    # Build remote command - on remote machine, use agentwire tts serve
    server_cmd = f"agentwire tts serve --host {host} --port {port}"

    # Start remotely in tmux
    remote_cmd = f"tmux new-session -d -s {session_name} && tmux send-keys -t {session_name} {shlex.quote(server_cmd)} Enter"
    print(f"Starting TTS server on {machine_id}...")

    result = subprocess.run(
        ["ssh", ssh_target, remote_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Failed to start TTS on {machine_id}: {result.stderr}", file=sys.stderr)
        return 1

    print(f"TTS server started on {machine_id}.")
    return 0


def _stop_tts_remote(ssh_target: str, machine_id: str) -> int:
    """Stop TTS server on remote machine via SSH."""
    session_name = "agentwire-tts"

    # Check if running
    check_cmd = f"tmux has-session -t ={session_name} 2>/dev/null && echo running || echo stopped"
    result = subprocess.run(
        ["ssh", ssh_target, check_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Cannot reach TTS machine. Check: ssh {ssh_target} echo ok", file=sys.stderr)
        return 1

    if "stopped" in result.stdout:
        print(f"TTS server is not running on {machine_id}.")
        return 1

    # Kill session
    kill_cmd = f"tmux kill-session -t {session_name}"
    result = subprocess.run(
        ["ssh", ssh_target, kill_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Failed to stop TTS on {machine_id}: {result.stderr}", file=sys.stderr)
        return 1

    print(f"TTS server stopped on {machine_id}.")
    return 0


def _check_tts_health(url: str, timeout: int = 2) -> tuple[bool, list[str] | None]:
    """Check if TTS server is responding at URL.

    Returns:
        (is_healthy, voices_list or None)
    """
    import urllib.request

    try:
        req = urllib.request.urlopen(f"{url}/voices", timeout=timeout)
        voices = json.loads(req.read().decode())
        if isinstance(voices, list):
            return True, voices
        return True, None
    except Exception:
        return False, None


def cmd_tts_start(args) -> int:
    """Start the Chatterbox TTS server in tmux."""
    from .network import NetworkContext

    ctx = NetworkContext.from_config()

    if ctx.is_local("tts"):
        return _start_tts_local(args)

    # TTS runs on another machine
    ssh_target = ctx.get_ssh_target("tts")
    machine_id = ctx.get_machine_for_service("tts")

    if not ssh_target or not machine_id:
        print("TTS configured for remote machine but machine not found.", file=sys.stderr)
        return 1

    print(f"TTS runs on {machine_id}, starting remotely...")
    return _start_tts_remote(ssh_target, machine_id, args)


def cmd_tts_serve(args) -> int:
    """Run the TTS server directly (foreground)."""
    import uvicorn

    config = load_config()
    tts_config = config.get("tts", {})
    port = args.port or tts_config.get("port", 8100)
    host = args.host or tts_config.get("host", "0.0.0.0")

    print(f"Starting TTS server on {host}:{port}...")
    uvicorn.run(
        "agentwire.tts_server:app",
        host=host,
        port=port,
        log_level="info",
    )
    return 0


def cmd_tts_stop(args) -> int:
    """Stop the TTS server."""
    from .network import NetworkContext

    ctx = NetworkContext.from_config()
    session_name = "agentwire-tts"

    if ctx.is_local("tts"):
        if not tmux_session_exists(session_name):
            print("TTS server is not running.")
            return 1

        subprocess.run(["tmux", "kill-session", "-t", session_name])
        print("TTS server stopped.")
        return 0

    # TTS runs on another machine
    ssh_target = ctx.get_ssh_target("tts")
    machine_id = ctx.get_machine_for_service("tts")

    if not ssh_target or not machine_id:
        print("TTS configured for remote machine but machine not found.", file=sys.stderr)
        return 1

    print(f"TTS runs on {machine_id}, stopping remotely...")
    return _stop_tts_remote(ssh_target, machine_id)


def cmd_tts_status(args) -> int:
    """Check TTS server status."""
    from .network import NetworkContext

    ctx = NetworkContext.from_config()
    session_name = "agentwire-tts"

    if ctx.is_local("tts"):
        if tmux_session_exists(session_name):
            print(f"TTS server is running in tmux session '{session_name}'")
            print(f"  Attach: tmux attach -t {session_name}")

            # Check health endpoint
            url = ctx.get_service_url("tts", use_tunnel=False)
            healthy, voices = _check_tts_health(url)
            if healthy:
                if voices:
                    print(f"  Voices: {', '.join(voices)}")
                else:
                    print(f"  Health: OK ({url})")
            else:
                print("  Status: starting or not responding yet")

            return 0
        else:
            # No local tmux session, but check if TTS is reachable anyway
            # (might be running via manual tunnel or external process)
            url = ctx.get_service_url("tts", use_tunnel=False)
            healthy, voices = _check_tts_health(url)
            if healthy:
                print(f"TTS server is running (external/tunnel)")
                if voices:
                    print(f"  Voices: {', '.join(voices)}")
                print(f"  URL: {url}")
                return 0

            print("TTS server is not running.")
            print("  Start:  agentwire tts start")
            return 1

    # TTS runs on another machine - check via health endpoint
    machine_id = ctx.get_machine_for_service("tts")
    url = ctx.get_service_url("tts", use_tunnel=True)

    print(f"TTS server runs on {machine_id}")

    healthy, voices = _check_tts_health(url)
    if healthy:
        print(f"  Status: running")
        if voices:
            print(f"  Voices: {', '.join(voices)}")
        print(f"  URL: {url}")
        return 0
    else:
        # Try direct connection if tunnel might not exist
        direct_url = ctx.get_service_url("tts", use_tunnel=False)
        if direct_url != url:
            healthy, voices = _check_tts_health(direct_url)
            if healthy:
                print(f"  Status: running (tunnel not working, direct OK)")
                if voices:
                    print(f"  Voices: {', '.join(voices)}")
                print(f"  URL: {direct_url}")
                print(f"  Hint: Run 'agentwire tunnels check' to verify tunnels")
                return 0

        print(f"  Status: not reachable")
        print(f"  Checked: {url}")
        if direct_url != url:
            print(f"  Also checked: {direct_url}")
        return 1


# === STT Commands ===

def cmd_stt_start(args) -> int:
    """Start the STT server in tmux."""
    session_name = "agentwire-stt"

    if tmux_session_exists(session_name):
        print(f"STT server already running in tmux session '{session_name}'")
        print(f"  Attach: tmux attach -t {session_name}")
        return 0

    config = load_config()
    stt_config = config.get("stt", {})
    port = args.port or 8100
    host = args.host or "0.0.0.0"
    model = args.model or os.environ.get("WHISPER_MODEL", "base")

    # Find agentwire source directory (for running from source venv)
    # Check common locations
    source_dirs = [
        Path.home() / "projects" / "agentwire",
        Path("/Users/dotdev/projects/agentwire"),
    ]
    agentwire_dir = None
    for d in source_dirs:
        if (d / ".venv" / "bin" / "python").exists():
            agentwire_dir = d
            break

    if not agentwire_dir:
        print("Error: Cannot find agentwire source directory with .venv", file=sys.stderr)
        print("Run from ~/projects/agentwire or set up .venv there", file=sys.stderr)
        return 1

    # Build command using source venv
    python_path = agentwire_dir / ".venv" / "bin" / "python"
    cmd = f"cd {agentwire_dir} && WHISPER_MODEL={model} WHISPER_DEVICE=cpu STT_PORT={port} STT_HOST={host} {python_path} -m agentwire.stt.stt_server"

    # Create tmux session
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name, "-c", str(agentwire_dir)
    ], check=True)

    subprocess.run([
        "tmux", "send-keys", "-t", session_name, cmd, "Enter"
    ], check=True)

    print(f"STT server starting in tmux session '{session_name}'")
    print(f"  Model: {model}")
    print(f"  Port: {port}")
    print(f"  Attach: tmux attach -t {session_name}")
    return 0


def cmd_stt_serve(args) -> int:
    """Run the STT server directly (foreground)."""
    import uvicorn

    port = args.port or 8100
    host = args.host or "0.0.0.0"
    model = args.model or "base"

    os.environ["WHISPER_MODEL"] = model
    os.environ["WHISPER_DEVICE"] = "cpu"

    print(f"Starting STT server on {host}:{port} with model {model}...")
    uvicorn.run(
        "agentwire.stt.stt_server:app",
        host=host,
        port=port,
        log_level="info",
    )
    return 0


def cmd_stt_stop(args) -> int:
    """Stop the STT server."""
    session_name = "agentwire-stt"

    if not tmux_session_exists(session_name):
        print("STT server is not running.")
        return 1

    subprocess.run(["tmux", "kill-session", "-t", session_name])
    print("STT server stopped.")
    return 0


def cmd_stt_status(args) -> int:
    """Check STT server status."""
    session_name = "agentwire-stt"
    config = load_config()
    stt_url = config.get("stt", {}).get("url", "http://localhost:8100")

    # Check health endpoint
    try:
        import urllib.request
        req = urllib.request.Request(f"{stt_url}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"STT server is running")
            print(f"  Model: {data.get('model', 'unknown')}")
            print(f"  Device: {data.get('device', 'unknown')}")
            print(f"  URL: {stt_url}")
            if tmux_session_exists(session_name):
                print(f"  Attach: tmux attach -t {session_name}")
            return 0
    except Exception:
        pass

    if tmux_session_exists(session_name):
        print(f"STT server is starting in tmux session '{session_name}'")
        print(f"  Attach: tmux attach -t {session_name}")
        return 0

    print("STT server is not running.")
    print(f"  Start: agentwire stt start")
    return 1


# === Say Command ===

def _get_portal_url() -> str:
    """Get portal URL from config, with smart fallbacks.

    Uses NetworkContext to determine the best URL:
    - If portal is local: use localhost
    - If portal is remote with tunnel: use localhost (tunnel port)
    - If portal is remote without tunnel: use direct URL
    """
    from .network import NetworkContext

    ctx = NetworkContext.from_config()

    if ctx.is_local("portal"):
        # Portal runs locally
        return f"https://localhost:{ctx.config.services.portal.port}"

    # Portal is remote - check if tunnel exists by testing localhost first
    tunnel_url = ctx.get_service_url("portal", use_tunnel=True)
    direct_url = ctx.get_service_url("portal", use_tunnel=False)

    # Try tunnel first (more common setup)
    if _check_portal_health(tunnel_url.replace("http://", "https://")):
        return tunnel_url.replace("http://", "https://")

    # Fall back to direct connection
    return direct_url.replace("http://", "https://")


def _get_current_tmux_session() -> str | None:
    """Get the current tmux session name, if running inside tmux."""
    # Check if we're in tmux
    if not os.environ.get("TMUX"):
        return None

    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:
        pass

    return None


def _get_session_from_yml() -> str | None:
    """Legacy function - session no longer stored in .agentwire.yml.

    Session is now runtime context from environment, not project config.
    This function exists for fallback compatibility but always returns None.
    """
    return None


def _get_session_type_from_path(path: str) -> str | None:
    """Read session type from .agentwire.yml in the given path.

    Returns:
        Session type (e.g., 'bare', 'claude-bypass', 'claude-restricted') or None
    """
    import yaml

    if not path:
        return None

    yml_path = Path(path) / ".agentwire.yml"
    if yml_path.exists():
        try:
            with open(yml_path) as f:
                config = yaml.safe_load(f) or {}
                return config.get("type")
        except Exception:
            pass
    return None


def _infer_session_from_path() -> str | None:
    """Infer session name from current working directory.

    ~/projects/myapp -> myapp
    ~/projects/myapp-worktrees/feature -> myapp/feature
    """
    cwd = Path.cwd()
    projects_dir = Path.home() / "projects"

    try:
        rel = cwd.relative_to(projects_dir)
        parts = rel.parts

        if len(parts) == 1:
            return parts[0]
        elif len(parts) >= 2 and "-worktrees" in parts[0]:
            # myapp-worktrees/feature -> myapp/feature
            base = parts[0].replace("-worktrees", "")
            return f"{base}/{parts[1]}"
        elif len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    except ValueError:
        pass

    return None


def _check_portal_connections(session: str, portal_url: str) -> tuple[bool, str]:
    """Check if portal has active browser connections for a session.

    Tries session name variants: as-is, with hostname.

    Returns:
        Tuple of (has_connections, actual_session_name)
        - has_connections: True if there are connections (audio should go to portal)
        - actual_session_name: The session name that has connections (may include @machine)
    """
    import urllib.request
    import ssl
    import socket

    # Try session variants: as-is, with hostname, with @local
    session_variants = [session]
    if "@" not in session:
        hostname = socket.gethostname().split('.')[0]
        session_variants.append(f"{session}@{hostname}")
        session_variants.append(f"{session}@local")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for session_name in session_variants:
        try:
            req = urllib.request.Request(
                f"{portal_url}/api/sessions/{session_name}/connections",
                headers={"Accept": "application/json"},
            )

            with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
                result = json.loads(response.read().decode())
                if result.get("has_connections", False):
                    return True, session_name

        except Exception:
            continue

    # No connections found in any variant
    return False, session


def _local_say_runpod(
    text: str,
    voice: str,
    exaggeration: float,
    cfg_weight: float,
    tts_config: dict,
) -> int:
    """Generate TTS via RunPod API and play locally.

    Works with runpod backend - calls the API directly.
    Falls back to chatterbox HTTP if that's the backend.
    """
    import urllib.request
    import tempfile
    import base64

    backend = tts_config.get("backend", "none")

    if backend == "runpod":
        return _local_say_runpod_api(text, voice, exaggeration, cfg_weight, tts_config)
    elif backend == "chatterbox":
        # Use the old HTTP-based local TTS
        from .network import NetworkContext
        ctx = NetworkContext.from_config()
        tts_url = ctx.get_service_url("tts", use_tunnel=True)
        return _local_say(text, voice, exaggeration, cfg_weight, tts_url)
    else:
        print(f"TTS backend '{backend}' not supported for local playback", file=sys.stderr)
        return 1


def _local_say_runpod_api(
    text: str,
    voice: str,
    exaggeration: float,
    cfg_weight: float,
    tts_config: dict,
) -> int:
    """Generate TTS via RunPod serverless API and play locally."""
    import urllib.request
    import tempfile
    import base64

    endpoint_id = tts_config.get("runpod_endpoint_id", "")
    api_key = tts_config.get("runpod_api_key", "")
    timeout = tts_config.get("runpod_timeout", 120)

    if not endpoint_id or not api_key:
        print("RunPod backend requires runpod_endpoint_id and runpod_api_key in config", file=sys.stderr)
        return 1

    endpoint_url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"

    payload = {
        "input": {
            "action": "generate",
            "text": text,
            "voice": voice,
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
        }
    }

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            endpoint_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode())

            # Check RunPod status
            if result.get("status") == "error":
                print(f"RunPod error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return 1

            # Extract output
            output = result.get("output", {})
            if "error" in output:
                print(f"TTS error: {output['error']}", file=sys.stderr)
                return 1

            # Decode base64 audio
            audio_b64 = output.get("audio", "")
            if not audio_b64:
                print("No audio returned from TTS", file=sys.stderr)
                return 1

            audio_data = base64.b64decode(audio_b64)

        # Save to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        # Play audio (cross-platform)
        if sys.platform == "darwin":
            subprocess.run(["afplay", temp_path], check=True)
        elif sys.platform == "linux":
            # Try various players
            for player in ["aplay", "paplay", "play"]:
                try:
                    subprocess.run([player, temp_path], check=True)
                    break
                except FileNotFoundError:
                    continue
        else:
            print(f"Audio saved to: {temp_path}")
            return 0

        # Clean up
        Path(temp_path).unlink(missing_ok=True)
        return 0

    except urllib.error.URLError as e:
        print(f"RunPod API not reachable: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"TTS failed: {e}", file=sys.stderr)
        return 1


def cmd_say(args) -> int:
    """Generate TTS audio and play it.

    Smart routing:
    1. Determine session (--session flag, .agentwire.yml, path inference, or tmux)
    2. Check if portal has browser connections for that session
    3. If connections exist → send to portal (plays on browser/tablet)
    4. If no connections → generate locally and play via system audio
    """
    text = " ".join(args.text) if args.text else ""

    if not text:
        print("Usage: agentwire say <text>", file=sys.stderr)
        return 1

    config = load_config()
    tts_config = config.get("tts", {})
    # Voice priority: CLI flag > .agentwire.yml > global config default
    voice = args.voice or get_voice_from_config() or tts_config.get("default_voice", "dotdev")
    exaggeration = args.exaggeration if args.exaggeration is not None else tts_config.get("exaggeration", 0.5)
    cfg_weight = args.cfg if args.cfg is not None else tts_config.get("cfg_weight", 0.5)

    # Determine session name (priority: flag > tmux session > path inference)
    # Tmux session is more accurate than path for forked/named sessions like "anna-fork-1"
    session = args.session or _get_current_tmux_session() or _infer_session_from_path()

    # Try portal first if we have a session
    if session:
        portal_url = _get_portal_url()
        has_connections, actual_session = _check_portal_connections(session, portal_url)

        if has_connections:
            # Send to portal - browser will play the audio
            return _remote_say(text, actual_session, portal_url)

    # No portal connections (or no session) - generate locally
    return _local_say_runpod(text, voice, exaggeration, cfg_weight, tts_config)


def _local_say(text: str, voice: str, exaggeration: float, cfg_weight: float, tts_url: str) -> int:
    """Generate TTS locally and play via system audio."""
    import urllib.request
    import tempfile

    try:
        # Request audio from chatterbox
        data = json.dumps({
            "text": text,
            "voice": voice,
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
        }).encode()

        req = urllib.request.Request(
            f"{tts_url}/tts",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            audio_data = response.read()

        # Save to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        # Play audio (cross-platform)
        if sys.platform == "darwin":
            subprocess.run(["afplay", temp_path], check=True)
        elif sys.platform == "linux":
            # Try various players
            for player in ["aplay", "paplay", "play"]:
                try:
                    subprocess.run([player, temp_path], check=True)
                    break
                except FileNotFoundError:
                    continue
        else:
            print(f"Audio saved to: {temp_path}")

        # Clean up
        Path(temp_path).unlink(missing_ok=True)
        return 0

    except urllib.error.URLError as e:
        print(f"TTS server not reachable: {e}", file=sys.stderr)
        print("Start it with: agentwire tts start", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"TTS failed: {e}", file=sys.stderr)
        return 1


def _remote_say(text: str, session: str, portal_url: str) -> int:
    """Send TTS to a session via the portal (for remote sessions)."""
    import urllib.request
    import ssl

    try:
        # Create SSL context that doesn't verify (self-signed certs)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        data = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            f"{portal_url}/api/say/{session}",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        # 90 second timeout to handle RunPod cold starts
        with urllib.request.urlopen(req, context=ctx, timeout=90) as response:
            result = json.loads(response.read().decode())
            if result.get("error"):
                print(f"Error: {result['error']}", file=sys.stderr)
                return 1

        return 0

    except Exception as e:
        print(f"Failed to send to portal: {e}", file=sys.stderr)
        return 1


# === Session Commands ===

def cmd_send(args) -> int:
    """Send a prompt to a tmux session or pane (adds Enter automatically).

    Supports remote sessions with session@machine format.
    Use --pane N to send to a specific pane in the current session.
    """
    session_full = getattr(args, 'session', None)
    pane_index = getattr(args, 'pane', None)
    prompt = " ".join(args.prompt) if args.prompt else ""
    json_mode = getattr(args, 'json', False)

    # Handle pane mode (auto-detect session from environment)
    if pane_index is not None:
        if not prompt:
            return _output_result(False, json_mode, "Usage: agentwire send --pane N <prompt>")

        try:
            pane_manager.send_to_pane(session_full, pane_index, prompt)
            if json_mode:
                _output_json({
                    "success": True,
                    "pane": pane_index,
                    "session": session_full or pane_manager.get_current_session(),
                    "message": "Prompt sent"
                })
            else:
                print(f"Sent to pane {pane_index}")
            return 0
        except RuntimeError as e:
            return _output_result(False, json_mode, str(e))

    # Session mode (original behavior)
    if not session_full:
        if json_mode:
            print(json.dumps({"success": False, "error": "Session name required (-s) or pane number (--pane)"}))
        else:
            print("Usage: agentwire send -s <session> <prompt>", file=sys.stderr)
            print("   or: agentwire send --pane N <prompt>", file=sys.stderr)
        return 1

    if not prompt:
        if json_mode:
            print(json.dumps({"success": False, "error": "Prompt required"}))
        else:
            print("Usage: agentwire send -s <session> <prompt>", file=sys.stderr)
        return 1

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux commands
        machine = _get_machine_config(machine_id)
        if machine is None:
            if json_mode:
                print(json.dumps({"success": False, "error": f"Machine '{machine_id}' not found"}))
            else:
                print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
            return 1

        # Build remote command
        quoted_session = shlex.quote(session)
        quoted_prompt = shlex.quote(prompt)

        # Send text, sleep, send Enter
        cmd = f"tmux send-keys -t {quoted_session} {quoted_prompt} && sleep 0.5 && tmux send-keys -t {quoted_session} Enter"

        # For multi-line text, add another Enter
        if "\n" in prompt or len(prompt) > 200:
            cmd += f" && sleep 0.5 && tmux send-keys -t {quoted_session} Enter"

        result = _run_remote(machine_id, cmd)
        if result.returncode != 0:
            if json_mode:
                print(json.dumps({"success": False, "error": f"Failed to send to {session_full}"}))
            else:
                print(f"Failed to send to {session_full}: {result.stderr}", file=sys.stderr)
            return 1

        if json_mode:
            print(json.dumps({"success": True, "session": session_full, "machine": machine_id, "message": "Prompt sent"}))
        else:
            print(f"Sent to {session_full}")
        return 0

    # Local: existing logic
    # Check if session exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        if json_mode:
            print(json.dumps({"success": False, "error": f"Session '{session}' not found"}))
        else:
            print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    # Send the prompt via tmux send-keys (text first, then Enter after delay)
    subprocess.run(
        ["tmux", "send-keys", "-t", session, prompt],
        check=True
    )

    # Wait for text to be fully entered before pressing Enter
    time.sleep(0.5)

    subprocess.run(
        ["tmux", "send-keys", "-t", session, "Enter"],
        check=True
    )

    # For multi-line text, Claude Code shows "[Pasted text...]" and waits for Enter
    # Send another Enter after a short delay to confirm the paste
    if "\n" in prompt or len(prompt) > 200:
        time.sleep(0.5)
        subprocess.run(
            ["tmux", "send-keys", "-t", session, "Enter"],
            check=True
        )

    if json_mode:
        print(json.dumps({"success": True, "session": session_full, "machine": None, "message": "Prompt sent"}))
    else:
        print(f"Sent to {session}")
    return 0


def cmd_list(args) -> int:
    """List tmux sessions or panes.

    When inside a tmux session, shows panes by default.
    Use --sessions to show sessions instead.
    """
    json_mode = getattr(args, 'json', False)
    local_only = getattr(args, 'local', False)
    remote_only = getattr(args, 'remote', False)
    show_sessions = getattr(args, 'sessions', False)

    # Check if we're inside a tmux session
    current_session = pane_manager.get_current_session()

    # If inside tmux and not explicitly asking for sessions, show panes
    if current_session and not show_sessions:
        panes = pane_manager.list_panes(current_session)

        if json_mode:
            pane_data = [
                {
                    "index": p.index,
                    "pane_id": p.pane_id,
                    "pid": p.pid,
                    "command": p.command,
                    "active": p.active,
                }
                for p in panes
            ]
            _output_json({"success": True, "session": current_session, "panes": pane_data})
            return 0

        if not panes:
            print(f"No panes in session '{current_session}'")
            return 0

        print(f"Panes in {current_session}:")
        for p in panes:
            active_marker = " *" if p.active else ""
            role = "orchestrator" if p.index == 0 else "worker"
            print(f"  {p.index}: [{role}] {p.command}{active_marker}")
        return 0

    # Show sessions (original behavior)
    all_sessions = []

    # Get local sessions (skip if remote_only)
    local_sessions = []
    if not remote_only:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_windows}:#{pane_current_path}"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        path = parts[2] if len(parts) > 2 else ""
                        session_info = {
                            "name": parts[0],  # Local sessions don't have machine suffix
                            "windows": int(parts[1]) if parts[1].isdigit() else 1,
                            "path": path,
                            "machine": None,  # Local session
                            "type": _get_session_type_from_path(path),
                        }
                        local_sessions.append(session_info)
                        all_sessions.append(session_info)

    # Get remote sessions from all registered machines (skip if local_only)
    remote_by_machine = {}
    if not local_only:
        machines = _get_all_machines()
        for machine in machines:
            machine_id = machine.get("id")
            if not machine_id:
                continue

            # Skip "local" machine (legacy Docker config)
            if machine_id == "local":
                continue

            cmd = "tmux list-sessions -F '#{session_name}:#{session_windows}:#{pane_current_path}' 2>/dev/null || echo ''"
            result = _run_remote(machine_id, cmd)

            machine_sessions = []
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(":", 2)
                        if len(parts) >= 2:
                            session_info = {
                                "name": f"{parts[0]}@{machine_id}",
                                "windows": int(parts[1]) if parts[1].isdigit() else 1,
                                "path": parts[2] if len(parts) > 2 else "",
                                "machine": machine_id,
                            }
                            machine_sessions.append(session_info)
                            all_sessions.append(session_info)

            remote_by_machine[machine_id] = machine_sessions

    # Output
    if json_mode:
        _output_json({"success": True, "sessions": all_sessions})
        return 0

    # Text output - grouped by machine
    # Combine local and remote sessions into single machine-based view
    all_machines = {}

    # Add local sessions to machine view
    for s in local_sessions:
        machine = s['machine']
        if machine not in all_machines:
            all_machines[machine] = []
        all_machines[machine].append(s)

    # Add remote sessions to machine view
    for machine_id, sessions in remote_by_machine.items():
        if machine_id not in all_machines:
            all_machines[machine_id] = []
        all_machines[machine_id].extend(sessions)

    if not all_machines:
        print("No sessions running")
        return 0

    # Display all sessions grouped by machine
    for machine_id, sessions in sorted(all_machines.items(), key=lambda x: (x[0] is not None, x[0])):
        label = machine_id if machine_id else "local"
        print(f"{label}:")
        if sessions:
            for s in sessions:
                # Remove @machine suffix for display within machine group
                display_name = s['name'].rsplit('@', 1)[0] if '@' in s['name'] else s['name']
                print(f"  {display_name}: {s['windows']} window(s) ({s['path']})")
        else:
            print("  (no sessions)")
        print()

    return 0


def cmd_new(args) -> int:
    """Create a new Claude Code session in tmux.

    Supports:
    - "project" -> simple session in ~/projects/project/
    - "project/branch" -> worktree session in ~/projects/project-worktrees/branch/
    - "project@machine" -> remote session
    - "project/branch@machine" -> remote worktree session
    """
    from .config import load_template as load_template_fn

    name = args.session
    path = args.path
    template_name = getattr(args, 'template', None)
    json_mode = getattr(args, 'json', False)

    if not name:
        return _output_result(False, json_mode, "Usage: agentwire new -s <name> [-p path] [-f]")

    # Load template if specified
    template = None
    if template_name:
        template = load_template_fn(template_name)
        if template is None:
            return _output_result(False, json_mode, f"Template '{template_name}' not found")

    # Parse roles from CLI, template, or existing .agentwire.yml
    roles_arg = getattr(args, 'roles', None)
    role_names: list[str] = []
    if roles_arg:
        role_names = [r.strip() for r in roles_arg.split(",") if r.strip()]
    elif template and hasattr(template, 'roles') and template.roles:
        role_names = template.roles
    else:
        # Check existing .agentwire.yml in the project
        project_path_for_config = Path(path).expanduser().resolve() if path else None
        if project_path_for_config:
            existing = load_project_config(project_path_for_config)
            if existing and existing.roles:
                role_names = existing.roles
            else:
                # Default to agentwire role for new projects
                role_names = ["agentwire"]
        else:
            # Default to agentwire role when no path specified
            role_names = ["agentwire"]

    # Load and validate roles
    roles: list[RoleConfig] = []
    if role_names:
        # Determine project path for role discovery
        project_path_for_roles = Path(path).expanduser().resolve() if path else None
        roles, missing = load_roles(role_names, project_path_for_roles)
        if missing:
            return _output_result(False, json_mode, f"Roles not found: {', '.join(missing)}")

    # Parse session name: project, branch, machine
    project, branch, machine_id = parse_session_name(name)

    # Build the tmux session name (convert dots to underscores, preserve slashes)
    if branch:
        session_name = f"{project}/{branch}".replace(".", "_")
    else:
        session_name = project.replace(".", "_")

    # Load config
    config = load_config()
    projects_dir = Path(config.get("projects", {}).get("dir", "~/projects")).expanduser()
    worktrees_config = config.get("projects", {}).get("worktrees", {})
    worktrees_enabled = worktrees_config.get("enabled", True)
    worktree_suffix = worktrees_config.get("suffix", "-worktrees")
    auto_create_branch = worktrees_config.get("auto_create_branch", True)

    # Handle remote session
    if machine_id:
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        remote_projects_dir = machine.get("projects_dir", "~/projects")

        # Build remote path
        if path:
            remote_path = path
        elif branch:
            remote_path = f"{remote_projects_dir}/{project}{worktree_suffix}/{branch}"
        else:
            remote_path = f"{remote_projects_dir}/{project}"

        # If branch specified, create worktree on remote
        if branch:
            # Create worktree on remote
            project_path = f"{remote_projects_dir}/{project}"
            worktree_path = remote_path

            # Check if worktree already exists
            check_cmd = f"test -d {shlex.quote(worktree_path)}"
            result = _run_remote(machine_id, check_cmd)

            if result.returncode != 0:
                # Create worktree
                # First check if branch exists
                branch_check = f"cd {shlex.quote(project_path)} && git rev-parse --verify refs/heads/{shlex.quote(branch)} 2>/dev/null"
                result = _run_remote(machine_id, branch_check)

                if result.returncode == 0:
                    # Branch exists, create worktree
                    create_cmd = f"cd {shlex.quote(project_path)} && mkdir -p $(dirname {shlex.quote(worktree_path)}) && git worktree add {shlex.quote(worktree_path)} {shlex.quote(branch)}"
                elif auto_create_branch:
                    # Create branch with worktree
                    create_cmd = f"cd {shlex.quote(project_path)} && mkdir -p $(dirname {shlex.quote(worktree_path)}) && git worktree add -b {shlex.quote(branch)} {shlex.quote(worktree_path)}"
                else:
                    return _output_result(False, json_mode, f"Branch '{branch}' does not exist and auto_create_branch is disabled")

                result = _run_remote(machine_id, create_cmd)
                if result.returncode != 0:
                    return _output_result(False, json_mode, f"Failed to create remote worktree: {result.stderr}")

        # Check if remote session already exists
        check_cmd = f"tmux has-session -t ={shlex.quote(session_name)} 2>/dev/null"
        result = _run_remote(machine_id, check_cmd)
        if result.returncode == 0:
            if args.force:
                # Kill existing session
                kill_cmd = f"tmux send-keys -t {shlex.quote(session_name)} /exit Enter && sleep 2 && tmux kill-session -t {shlex.quote(session_name)} 2>/dev/null"
                _run_remote(machine_id, kill_cmd)
            else:
                return _output_result(False, json_mode, f"Session '{session_name}' already exists on {machine_id}. Use -f to replace.")

        # Create remote tmux session
        # Determine session type from CLI flags or template
        if getattr(args, 'bare', False):
            session_type = SessionType.BARE
        elif getattr(args, 'restricted', False):
            session_type = SessionType.CLAUDE_RESTRICTED
        elif getattr(args, 'prompted', False):
            session_type = SessionType.CLAUDE_PROMPTED
        elif template:
            if template.restricted:
                session_type = SessionType.CLAUDE_RESTRICTED
            elif not template.bypass_permissions:
                session_type = SessionType.CLAUDE_PROMPTED
            else:
                session_type = SessionType.CLAUDE_BYPASS
        else:
            session_type = SessionType.CLAUDE_BYPASS

        # Build claude command with roles
        claude_cmd = _build_claude_cmd(session_type, roles if roles else None)
        # Create session - Claude starts immediately if not bare
        if claude_cmd:
            create_cmd = (
                f"tmux new-session -d -s {shlex.quote(session_name)} -c {shlex.quote(remote_path)} && "
                f"tmux send-keys -t {shlex.quote(session_name)} 'cd {shlex.quote(remote_path)}' Enter && "
                f"sleep 0.1 && "
                f"tmux send-keys -t {shlex.quote(session_name)} {shlex.quote(claude_cmd)} Enter"
            )
        else:
            # Bare session - just create tmux
            create_cmd = (
                f"tmux new-session -d -s {shlex.quote(session_name)} -c {shlex.quote(remote_path)} && "
                f"tmux send-keys -t {shlex.quote(session_name)} 'cd {shlex.quote(remote_path)}' Enter"
            )

        result = _run_remote(machine_id, create_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create remote session: {result.stderr}")

        # Send initial prompt from template if specified
        if template and template.initial_prompt:
            # Wait for Claude to be ready
            time.sleep(2)
            # Expand template variables
            variables = {
                "project_name": project,
                "branch": branch or "",
                "machine": machine_id,
            }
            initial_prompt = template.expand_variables(variables)
            # Send initial prompt via tmux
            # Use printf + base64 to handle multi-line prompts safely
            encoded = base64.b64encode(initial_prompt.encode()).decode()
            send_cmd = f"echo {shlex.quote(encoded)} | base64 -d | tmux load-buffer - && tmux paste-buffer -t {shlex.quote(session_name)} && tmux send-keys -t {shlex.quote(session_name)} Enter"
            _run_remote(machine_id, send_cmd)

        if json_mode:
            _output_json({
                "success": True,
                "session": f"{session_name}@{machine_id}",
                "path": remote_path,
                "branch": branch,
                "machine": machine_id,
                "template": template_name,
            })
        else:
            print(f"Created session '{session_name}' on {machine_id} in {remote_path}")
            if template:
                print(f"Applied template: {template_name}")
            print(f"Attach via portal or: ssh {machine.get('host', machine_id)} -t tmux attach -t {session_name}")

        _notify_portal_sessions_changed()
        return 0

    # Local session
    # Resolve path
    if path and branch and worktrees_enabled:
        # Path + branch: use provided path as main repo, create worktree from it
        project_path = Path(path).expanduser().resolve()
        session_path = project_path.parent / f"{project_path.name}{worktree_suffix}" / branch

        # Ensure worktree exists
        if not session_path.exists():
            if not project_path.exists():
                return _output_result(False, json_mode, f"Project path does not exist: {project_path}")

            success = ensure_worktree(
                project_path,
                branch,
                session_path,
                auto_create_branch=auto_create_branch,
            )
            if not success:
                return _output_result(False, json_mode, f"Failed to create worktree for branch '{branch}' in {project_path}")
    elif path:
        session_path = Path(path).expanduser().resolve()
    elif branch and worktrees_enabled:
        # Worktree session: ~/projects/project-worktrees/branch/
        project_path = projects_dir / project
        session_path = projects_dir / f"{project}{worktree_suffix}" / branch

        # Ensure worktree exists
        if not session_path.exists():
            if not project_path.exists():
                return _output_result(False, json_mode, f"Project path does not exist: {project_path}")

            success = ensure_worktree(
                project_path,
                branch,
                session_path,
                auto_create_branch=auto_create_branch,
            )
            if not success:
                return _output_result(False, json_mode, f"Failed to create worktree for branch '{branch}' in {project_path}")
    else:
        # Simple session: ~/projects/project/
        session_path = projects_dir / project

    if not session_path.exists():
        if args.force:
            # Auto-create directory with -f flag
            session_path.mkdir(parents=True, exist_ok=True)
        else:
            return _output_result(False, json_mode, f"Path does not exist: {session_path}")

    # Check if session already exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={session_name}"],
        capture_output=True
    )
    if result.returncode == 0:
        if args.force:
            # Kill existing session
            subprocess.run(["tmux", "send-keys", "-t", session_name, "/exit", "Enter"])
            time.sleep(2)
            subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        else:
            return _output_result(False, json_mode, f"Session '{session_name}' already exists. Use -f to replace.")

    # Create new tmux session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, "-c", str(session_path)],
        check=True
    )

    # Ensure Claude starts in correct directory
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, f"cd {shlex.quote(str(session_path))}", "Enter"],
        check=True
    )
    time.sleep(0.1)

    # Determine session type from CLI flags, template, or existing config
    if getattr(args, 'bare', False):
        session_type = SessionType.BARE
    elif getattr(args, 'restricted', False):
        session_type = SessionType.CLAUDE_RESTRICTED
    elif getattr(args, 'prompted', False):
        session_type = SessionType.CLAUDE_PROMPTED
    elif template:
        # Use template settings
        if template.restricted:
            session_type = SessionType.CLAUDE_RESTRICTED
        elif not template.bypass_permissions:
            session_type = SessionType.CLAUDE_PROMPTED
        else:
            session_type = SessionType.CLAUDE_BYPASS
    else:
        # Check existing .agentwire.yml for type, otherwise default to bypass
        existing_config = load_project_config(session_path)
        if existing_config and existing_config.type:
            session_type = existing_config.type
        else:
            session_type = SessionType.CLAUDE_BYPASS  # Default

    # Build and start Claude command
    claude_cmd = _build_claude_cmd(session_type, roles if roles else None)
    if claude_cmd:
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, claude_cmd, "Enter"],
            check=True
        )

    # Update project config (.agentwire.yml) - preserve existing settings
    # Note: session name is NOT stored in config - it's runtime context
    existing_config = load_project_config(session_path)
    if existing_config:
        # Preserve existing voice and roles if not overridden by CLI/template
        project_config = ProjectConfig(
            type=session_type,
            roles=role_names if role_names else existing_config.roles,
            voice=template.voice if template and template.voice else existing_config.voice,
        )
    else:
        # Create new config
        project_config = ProjectConfig(
            type=session_type,
            roles=role_names if role_names else [],
            voice=template.voice if template and template.voice else None,
        )
    save_project_config(project_config, session_path)

    # Send initial prompt from template if specified
    if template and template.initial_prompt:
        # Wait for Claude to be ready
        time.sleep(2)
        # Expand template variables
        variables = {
            "project_name": project,
            "branch": branch or "",
            "machine": "",
        }
        initial_prompt = template.expand_variables(variables)
        # Send initial prompt via tmux
        # Use load-buffer to handle multi-line prompts safely
        encoded = base64.b64encode(initial_prompt.encode()).decode()
        subprocess.run(
            f"echo {shlex.quote(encoded)} | base64 -d | tmux load-buffer - && tmux paste-buffer -t {shlex.quote(session_name)} && tmux send-keys -t {shlex.quote(session_name)} Enter",
            shell=True,
            check=True
        )

    if json_mode:
        _output_json({
            "success": True,
            "session": session_name,
            "path": str(session_path),
            "branch": branch,
            "machine": None,
            "template": template_name,
        })
    else:
        print(f"Created session '{session_name}' in {session_path}")
        if template:
            print(f"Applied template: {template_name}")
        print(f"Attach with: tmux attach -t {session_name}")

    _notify_portal_sessions_changed()
    return 0


def cmd_output(args) -> int:
    """Read output from a tmux session or pane.

    Supports remote sessions with session@machine format.
    Use --pane N to read from a specific pane in the current session.
    """
    session_full = getattr(args, 'session', None)
    pane_index = getattr(args, 'pane', None)
    lines = args.lines or 50
    json_mode = getattr(args, 'json', False)

    # Handle pane mode (auto-detect session from environment)
    if pane_index is not None:
        try:
            output = pane_manager.capture_pane(session_full, pane_index, lines)
            if json_mode:
                _output_json({
                    "success": True,
                    "pane": pane_index,
                    "session": session_full or pane_manager.get_current_session(),
                    "lines": lines,
                    "output": output
                })
            else:
                print(output)
            return 0
        except RuntimeError as e:
            return _output_result(False, json_mode, str(e))

    # Session mode (original behavior)
    if not session_full:
        if json_mode:
            print(json.dumps({"success": False, "error": "Session name required (-s) or pane number (--pane)"}))
        else:
            print("Usage: agentwire output -s <session> [-n lines]", file=sys.stderr)
            print("   or: agentwire output --pane N [-n lines]", file=sys.stderr)
        return 1

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux capture-pane
        machine = _get_machine_config(machine_id)
        if machine is None:
            if json_mode:
                print(json.dumps({"success": False, "error": f"Machine '{machine_id}' not found"}))
            else:
                print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
            return 1

        cmd = f"tmux capture-pane -t {shlex.quote(session)} -p -S -{lines}"
        result = _run_remote(machine_id, cmd)

        if result.returncode != 0:
            if json_mode:
                print(json.dumps({"success": False, "error": f"Session '{session}' not found on {machine_id}"}))
            else:
                print(f"Session '{session}' not found on {machine_id}", file=sys.stderr)
            return 1

        if json_mode:
            print(json.dumps({
                "success": True,
                "session": session_full,
                "lines": lines,
                "machine": machine_id,
                "output": result.stdout
            }))
        else:
            print(result.stdout)
        return 0

    # Local: existing logic
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        if json_mode:
            print(json.dumps({"success": False, "error": f"Session '{session}' not found"}))
        else:
            print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
        capture_output=True,
        text=True
    )

    if json_mode:
        print(json.dumps({
            "success": True,
            "session": session_full,
            "lines": lines,
            "machine": None,
            "output": result.stdout
        }))
    else:
        print(result.stdout)
    return 0


def cmd_info(args) -> int:
    """Get session information as JSON.

    Returns working directory, pane count, and other metadata.
    """
    session_full = args.session
    json_mode = getattr(args, 'json', True)  # Default to JSON

    if not session_full:
        return _output_result(False, json_mode, "Session name required (-s)")

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote session
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found")

        # Get session info via SSH
        cmd = f"tmux display-message -t {shlex.quote(session)} -p '#{{pane_current_path}}:#{{window_panes}}' 2>/dev/null"
        result = _run_remote(machine_id, cmd)

        if result.returncode != 0:
            return _output_result(False, json_mode, f"Session '{session}' not found on {machine_id}")

        parts = result.stdout.strip().split(":")
        cwd = parts[0] if parts else ""
        pane_count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        info = {
            "success": True,
            "session": session_full,
            "name": session,
            "machine": machine_id,
            "cwd": cwd,
            "pane_count": pane_count,
            "is_remote": True,
        }
    else:
        # Local session
        if not tmux_session_exists(session):
            return _output_result(False, json_mode, f"Session '{session}' not found")

        # Get working directory
        result = subprocess.run(
            ["tmux", "display-message", "-t", session, "-p", "#{pane_current_path}:#{window_panes}"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return _output_result(False, json_mode, f"Could not get info for '{session}'")

        parts = result.stdout.strip().split(":")
        cwd = parts[0] if parts else ""
        pane_count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        info = {
            "success": True,
            "session": session,
            "name": session,
            "machine": None,
            "cwd": cwd,
            "pane_count": pane_count,
            "is_remote": False,
        }

    if json_mode:
        print(json.dumps(info))
    else:
        print(f"Session: {info['name']}")
        if info['machine']:
            print(f"Machine: {info['machine']}")
        print(f"CWD: {info['cwd']}")
        print(f"Panes: {info['pane_count']}")

    return 0


def cmd_kill(args) -> int:
    """Kill a tmux session or pane (with clean Claude exit).

    Supports remote sessions with session@machine format.
    Use --pane N to kill a specific pane in the current session.
    """
    session_full = getattr(args, 'session', None)
    pane_index = getattr(args, 'pane', None)
    json_mode = getattr(args, 'json', False)

    # Handle pane mode (auto-detect session from environment)
    if pane_index is not None:
        if pane_index == 0:
            return _output_result(False, json_mode, "Cannot kill pane 0 (orchestrator)")

        try:
            session = session_full or pane_manager.get_current_session()
            if not session:
                return _output_result(False, json_mode, "Not in tmux session and no session specified")

            # Send /exit for clean shutdown (use send_to_pane for proper timing)
            pane_manager.send_to_pane(session, pane_index, "/exit")
            if not json_mode:
                print(f"Sent /exit to pane {pane_index}, waiting 3s...")
            time.sleep(3)

            # Kill the pane
            pane_manager.kill_pane(session, pane_index)

            if json_mode:
                _output_json({
                    "success": True,
                    "pane": pane_index,
                    "session": session,
                })
            else:
                print(f"Killed pane {pane_index}")
            return 0
        except RuntimeError as e:
            return _output_result(False, json_mode, str(e))

    # Session mode (original behavior)
    if not session_full:
        return _output_result(False, json_mode, "Usage: agentwire kill -s <session> or --pane N")

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux commands
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        # Check if session exists
        check_cmd = f"tmux has-session -t {shlex.quote(session)} 2>/dev/null"
        result = _run_remote(machine_id, check_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Session '{session}' not found on {machine_id}")

        # Send /exit to Claude first for clean shutdown
        exit_cmd = f"tmux send-keys -t {shlex.quote(session)} /exit Enter"
        _run_remote(machine_id, exit_cmd)
        if not json_mode:
            print(f"Sent /exit to {session_full}, waiting 3s...")
        time.sleep(3)

        # Kill the session
        kill_cmd = f"tmux kill-session -t {shlex.quote(session)}"
        _run_remote(machine_id, kill_cmd)
        if not json_mode:
            print(f"Killed session '{session_full}'")

        _notify_portal_sessions_changed()

        if json_mode:
            _output_json({"success": True, "session": session_full})
        return 0

    # Local: existing logic
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        return _output_result(False, json_mode, f"Session '{session}' not found")

    # Send /exit to Claude first for clean shutdown
    subprocess.run(["tmux", "send-keys", "-t", session, "/exit", "Enter"])
    if not json_mode:
        print(f"Sent /exit to {session}, waiting 3s...")
    time.sleep(3)

    # Kill the session
    subprocess.run(["tmux", "kill-session", "-t", session])
    if not json_mode:
        print(f"Killed session '{session}'")

    _notify_portal_sessions_changed()

    if json_mode:
        _output_json({"success": True, "session": session_full})
    return 0


def cmd_spawn(args) -> int:
    """Spawn a worker pane in the current session.

    Creates a new tmux pane in the orchestrator's session and starts
    Claude Code with the specified roles (default: worker).

    With --branch, creates an isolated worktree for the worker to enable
    parallel commits without conflicts.
    """
    json_mode = getattr(args, 'json', False)
    cwd = getattr(args, 'cwd', None) or os.getcwd()
    roles_arg = getattr(args, 'roles', 'worker')
    session = getattr(args, 'session', None)
    branch = getattr(args, 'branch', None)

    worktree_path = None

    # Handle --branch: create worktree for isolated work
    if branch:
        try:
            worktree_path = pane_manager.create_worker_worktree(branch, cwd)
            cwd = worktree_path
            if not json_mode:
                print(f"Created worktree at {worktree_path}")
        except RuntimeError as e:
            return _output_result(False, json_mode, f"Failed to create worktree: {e}")

    # Parse roles
    role_names = [r.strip() for r in roles_arg.split(",") if r.strip()]

    # Load and validate roles
    roles, missing = load_roles(role_names, Path(cwd))
    if missing:
        return _output_result(False, json_mode, f"Roles not found: {', '.join(missing)}")

    # Build claude command with roles
    claude_cmd = _build_claude_cmd(SessionType.CLAUDE_BYPASS, roles if roles else None)

    try:
        # Spawn pane
        pane_index = pane_manager.spawn_worker_pane(
            session=session,
            cwd=cwd,
            cmd=claude_cmd
        )

        if json_mode:
            result = {
                "success": True,
                "pane": pane_index,
                "session": session or pane_manager.get_current_session(),
                "roles": role_names,
            }
            if branch:
                result["branch"] = branch
                result["worktree"] = worktree_path
            _output_json(result)
        else:
            print(f"Spawned pane {pane_index}")

        return 0

    except RuntimeError as e:
        return _output_result(False, json_mode, str(e))


def cmd_split(args) -> int:
    """Add terminal pane(s) to current session with even vertical layout."""
    count = getattr(args, 'count', 1)
    cwd = getattr(args, 'cwd', None) or os.getcwd()
    session = getattr(args, 'session', None)

    # Get current session if not specified
    if not session:
        session = os.environ.get("TMUX_PANE")
        if session:
            # We're in tmux, get session name
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{session_name}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                session = result.stdout.strip()
            else:
                session = None

    if not session:
        print("Error: Not in a tmux session and no --session specified")
        return 1

    # Add panes
    for _ in range(count):
        subprocess.run([
            "tmux", "split-window", "-h", "-t", session, "-c", cwd
        ], capture_output=True)

    # Even vertical layout and focus pane 0
    subprocess.run(["tmux", "select-layout", "-t", session, "even-horizontal"], capture_output=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{session}:0.0"], capture_output=True)

    pane_count = 1 + count  # original + new
    print(f"Added {count} pane(s) - now {pane_count} even vertical panes")
    return 0


def cmd_detach(args) -> int:
    """Move a pane to its own session and re-align remaining panes."""
    pane_index = getattr(args, 'pane', None)
    new_session = getattr(args, 'session', None)
    source_session = getattr(args, 'source', None)

    if pane_index is None or new_session is None:
        print("Error: --pane and -s/--session are required")
        return 1

    # Get source session if not specified
    if not source_session:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{session_name}"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            source_session = result.stdout.strip()
        else:
            print("Error: Could not detect current session")
            return 1

    # Check if target session already exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", new_session],
        capture_output=True
    )
    session_exists = result.returncode == 0

    # Move pane to new session
    if session_exists:
        # Move to existing session
        subprocess.run([
            "tmux", "move-pane", "-s", f"{source_session}:{pane_index}", "-t", f"{new_session}:"
        ], capture_output=True)
    else:
        # Break pane into new session
        subprocess.run([
            "tmux", "break-pane", "-d", "-s", f"{source_session}:{pane_index}", "-t", f"{new_session}:"
        ], capture_output=True)

    # Re-align remaining panes in source session
    subprocess.run(["tmux", "select-layout", "-t", source_session, "even-horizontal"], capture_output=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{source_session}:0.0"], capture_output=True)

    print(f"Moved pane {pane_index} to session '{new_session}'")
    return 0


def cmd_jump(args) -> int:
    """Jump to (focus) a specific pane."""
    json_mode = getattr(args, 'json', False)
    pane_index = getattr(args, 'pane', None)
    session = getattr(args, 'session', None)

    if pane_index is None:
        return _output_result(False, json_mode, "Usage: agentwire jump --pane N")

    try:
        pane_manager.focus_pane(session, pane_index)

        if json_mode:
            _output_json({
                "success": True,
                "pane": pane_index,
                "session": session or pane_manager.get_current_session(),
            })
        else:
            print(f"Jumped to pane {pane_index}")

        return 0

    except RuntimeError as e:
        return _output_result(False, json_mode, str(e))


def cmd_resize(args) -> int:
    """Resize tmux window to fit the largest attached client."""
    json_mode = getattr(args, 'json', False)
    session = getattr(args, 'session', None)

    # Get session name
    if not session:
        session = pane_manager.get_current_session()
        if not session:
            return _output_result(False, json_mode, "Not in a tmux session. Use -s to specify session.")

    try:
        result = subprocess.run(
            ["tmux", "resize-window", "-A", "-t", session],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to resize: {result.stderr.strip()}")

        if json_mode:
            _output_json({"success": True, "session": session})
        else:
            print(f"Resized {session} to fit largest client")

        return 0

    except Exception as e:
        return _output_result(False, json_mode, str(e))


def cmd_send_keys(args) -> int:
    """Send raw keys to a tmux session (no automatic Enter).

    Each argument is sent as a separate key group with a brief pause between.
    Useful for sending special keys like Enter, Escape, C-c, etc.

    Supports remote sessions with session@machine format.
    """
    session_full = args.session
    keys = args.keys if args.keys else []

    if not session_full:
        print("Usage: agentwire send-keys -s <session> <keys>...", file=sys.stderr)
        return 1

    if not keys:
        print("Usage: agentwire send-keys -s <session> <keys>...", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  agentwire send-keys -s mysession Enter", file=sys.stderr)
        print("  agentwire send-keys -s mysession C-c", file=sys.stderr)
        print("  agentwire send-keys -s mysession Escape", file=sys.stderr)
        print("  agentwire send-keys -s mysession 'hello world' Enter", file=sys.stderr)
        return 1

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux commands
        machine = _get_machine_config(machine_id)
        if machine is None:
            print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
            return 1

        # Build remote command with pauses between keys
        quoted_session = shlex.quote(session)
        cmd_parts = []
        for i, key in enumerate(keys):
            cmd_parts.append(f"tmux send-keys -t {quoted_session} {shlex.quote(key)}")
            if i < len(keys) - 1:
                cmd_parts.append("sleep 0.1")

        cmd = " && ".join(cmd_parts)

        result = _run_remote(machine_id, cmd)
        if result.returncode != 0:
            print(f"Failed to send keys to {session_full}: {result.stderr}", file=sys.stderr)
            return 1

        print(f"Sent keys to {session_full}")
        return 0

    # Local: existing logic
    # Check if session exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    # Send each key group with a pause between
    for i, key in enumerate(keys):
        subprocess.run(
            ["tmux", "send-keys", "-t", session, key],
            check=True
        )
        # Brief pause between key groups (not after last one)
        if i < len(keys) - 1:
            time.sleep(0.1)

    print(f"Sent keys to {session}")
    return 0


# === Wave 5: Recreate and Fork Commands ===


def cmd_recreate(args) -> int:
    """Destroy and recreate a session with fresh worktree.

    Steps:
    1. Kill existing session (local or remote)
    2. Remove worktree
    3. Pull latest on main repo
    4. Create new worktree with timestamp branch
    5. Create new session

    Supports remote sessions with session@machine format.
    """
    session_full = args.session
    json_mode = getattr(args, 'json', False)

    if not session_full:
        return _output_result(False, json_mode, "Usage: agentwire recreate -s <session>")

    # Parse session name
    project, branch, machine_id = parse_session_name(session_full)

    # Load config
    config = load_config()
    projects_dir = Path(config.get("projects", {}).get("dir", "~/projects")).expanduser()
    worktrees_config = config.get("projects", {}).get("worktrees", {})
    worktree_suffix = worktrees_config.get("suffix", "-worktrees")

    # Build session name for tmux (preserve slashes, convert dots to underscores)
    if branch:
        session_name = f"{project}/{branch}".replace(".", "_")
    else:
        session_name = project.replace(".", "_")

    if machine_id:
        # Remote recreate
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        remote_projects_dir = machine.get("projects_dir", "~/projects")

        # Step 1: Kill existing session
        kill_cmd = f"tmux send-keys -t {shlex.quote(session_name)} /exit Enter 2>/dev/null; sleep 2; tmux kill-session -t {shlex.quote(session_name)} 2>/dev/null"
        _run_remote(machine_id, kill_cmd)

        # Determine paths
        project_path = f"{remote_projects_dir}/{project}"
        if branch:
            worktree_path = f"{remote_projects_dir}/{project}{worktree_suffix}/{branch}"
        else:
            worktree_path = project_path

        # Step 2: Remove worktree (if branch session)
        if branch:
            remove_cmd = f"cd {shlex.quote(project_path)} && git worktree remove {shlex.quote(worktree_path)} --force 2>/dev/null; rm -rf {shlex.quote(worktree_path)}"
            _run_remote(machine_id, remove_cmd)

        # Step 3: Pull latest on main repo
        pull_cmd = f"cd {shlex.quote(project_path)} && git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true"
        _run_remote(machine_id, pull_cmd)

        # Step 4: Create new worktree with timestamp branch
        if branch:
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            new_branch = f"{branch}-{timestamp}"

            create_wt_cmd = f"cd {shlex.quote(project_path)} && mkdir -p $(dirname {shlex.quote(worktree_path)}) && git worktree add -b {shlex.quote(new_branch)} {shlex.quote(worktree_path)}"
            result = _run_remote(machine_id, create_wt_cmd)
            if result.returncode != 0:
                return _output_result(False, json_mode, f"Failed to create worktree: {result.stderr}")

        # Step 5: Create new session
        restricted = getattr(args, 'restricted', False)
        no_bypass = getattr(args, 'no_bypass', False)
        # Restricted mode implies no bypass (uses hook for permission handling)
        bypass_flag = "" if (restricted or no_bypass) else " --dangerously-skip-permissions"
        session_path = worktree_path if branch else project_path

        create_cmd = (
            f"tmux new-session -d -s {shlex.quote(session_name)} -c {shlex.quote(session_path)} && "
            f"tmux send-keys -t {shlex.quote(session_name)} 'cd {shlex.quote(session_path)}' Enter && "
            f"sleep 0.1 && "
            f"tmux send-keys -t {shlex.quote(session_name)} 'claude{bypass_flag}' Enter"
        )

        result = _run_remote(machine_id, create_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create session: {result.stderr}")

        if json_mode:
            _output_json({
                "success": True,
                "session": session_name,
                "path": session_path,
                "branch": new_branch if branch else None,
                "machine": machine_id,
            })
        else:
            print(f"Recreated session '{session_name}' on {machine_id} in {session_path}")

        return 0

    # Local recreate
    # Step 1: Kill existing session
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={session_name}"],
        capture_output=True
    )
    if result.returncode == 0:
        subprocess.run(["tmux", "send-keys", "-t", session_name, "/exit", "Enter"])
        time.sleep(2)
        subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)

    # Determine paths
    project_path = projects_dir / project
    if branch:
        worktree_path = projects_dir / f"{project}{worktree_suffix}" / branch
    else:
        worktree_path = project_path

    # Step 2: Remove worktree (if branch session)
    if branch and worktree_path.exists():
        remove_worktree(project_path, worktree_path)
        # Force remove if git worktree remove failed
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

    # Step 3: Pull latest on main repo
    if project_path.exists():
        subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=project_path,
            capture_output=True
        )

    # Step 4: Create new worktree with timestamp branch
    if branch:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        new_branch = f"{branch}-{timestamp}"

        success = ensure_worktree(
            project_path,
            new_branch,
            worktree_path,
            auto_create_branch=True,
        )
        if not success:
            return _output_result(False, json_mode, f"Failed to create worktree for branch '{new_branch}'")

    session_path = worktree_path if branch else project_path

    if not session_path.exists():
        return _output_result(False, json_mode, f"Path does not exist: {session_path}")

    # Step 5: Create new session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, "-c", str(session_path)],
        check=True
    )

    # Ensure Claude starts in correct directory
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, f"cd {shlex.quote(str(session_path))}", "Enter"],
        check=True
    )
    time.sleep(0.1)

    restricted = getattr(args, 'restricted', False)
    no_bypass = getattr(args, 'no_bypass', False)
    # Restricted mode implies no bypass (uses hook for permission handling)
    if restricted or no_bypass:
        claude_cmd = "claude"
    else:
        claude_cmd = "claude --dangerously-skip-permissions"

    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, claude_cmd, "Enter"],
        check=True
    )

    if json_mode:
        _output_json({
            "success": True,
            "session": session_name,
            "path": str(session_path),
            "branch": new_branch if branch else None,
            "machine": None,
        })
    else:
        print(f"Recreated session '{session_name}' in {session_path}")
        print(f"Attach with: tmux attach -t {session_name}")

    return 0


def cmd_fork(args) -> int:
    """Fork a session into a new worktree with copied Claude context.

    Creates a new worktree from current branch state and optionally
    copies Claude session file for conversation continuity.

    Supports remote sessions with session@machine format.
    """
    source_full = args.source
    target_full = args.target
    json_mode = getattr(args, 'json', False)

    if not source_full or not target_full:
        return _output_result(False, json_mode, "Usage: agentwire fork -s <source> -t <target>")

    # Parse session names
    source_project, source_branch, source_machine = parse_session_name(source_full)
    target_project, target_branch, target_machine = parse_session_name(target_full)

    # Non-worktree fork: both have no branch (same directory, fork Claude context)
    # Worktree fork: at least one has a branch (create new worktree)
    is_non_worktree_fork = not source_branch and not target_branch

    # For worktree forks, validate project names match and target has a branch
    if not is_non_worktree_fork:
        if source_project != target_project:
            return _output_result(False, json_mode, f"For worktree forks, source and target must be same project (got {source_project} vs {target_project})")
        if not target_branch:
            return _output_result(False, json_mode, "For worktree forks, target must include a branch name (e.g., project/new-branch)")

    # Machines must match
    if source_machine != target_machine:
        return _output_result(False, json_mode, f"Source and target must be on same machine (got {source_machine} vs {target_machine})")

    machine_id = source_machine

    # Load config
    config = load_config()
    projects_dir = Path(config.get("projects", {}).get("dir", "~/projects")).expanduser()
    worktrees_config = config.get("projects", {}).get("worktrees", {})
    worktree_suffix = worktrees_config.get("suffix", "-worktrees")

    # Build session names (preserve slashes, convert dots to underscores)
    if source_branch:
        source_session = f"{source_project}/{source_branch}".replace(".", "_")
    else:
        source_session = source_project.replace(".", "_")

    if target_branch:
        target_session = f"{target_project}/{target_branch}".replace(".", "_")
    else:
        # Non-worktree fork: use target project name directly
        target_session = target_project.replace(".", "_")

    if machine_id:
        # Remote fork
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        remote_projects_dir = machine.get("projects_dir", "~/projects")

        # Build paths
        project_path = f"{remote_projects_dir}/{source_project}"
        if source_branch:
            source_path = f"{remote_projects_dir}/{source_project}{worktree_suffix}/{source_branch}"
        else:
            source_path = project_path
        target_path = f"{remote_projects_dir}/{target_project}{worktree_suffix}/{target_branch}"

        # Check if target already exists
        check_cmd = f"test -d {shlex.quote(target_path)}"
        result = _run_remote(machine_id, check_cmd)
        if result.returncode == 0:
            return _output_result(False, json_mode, f"Target worktree already exists: {target_path}")

        # Create new worktree from source
        create_cmd = f"cd {shlex.quote(source_path)} && mkdir -p $(dirname {shlex.quote(target_path)}) && git worktree add -b {shlex.quote(target_branch)} {shlex.quote(target_path)}"
        result = _run_remote(machine_id, create_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create worktree: {result.stderr}")

        # Create new session
        restricted = getattr(args, 'restricted', False)
        no_bypass = getattr(args, 'no_bypass', False)
        # Restricted mode implies no bypass (uses hook for permission handling)
        bypass_flag = "" if (restricted or no_bypass) else " --dangerously-skip-permissions"
        create_session_cmd = (
            f"tmux new-session -d -s {shlex.quote(target_session)} -c {shlex.quote(target_path)} && "
            f"tmux send-keys -t {shlex.quote(target_session)} 'cd {shlex.quote(target_path)}' Enter && "
            f"sleep 0.1 && "
            f"tmux send-keys -t {shlex.quote(target_session)} 'claude{bypass_flag}' Enter"
        )

        result = _run_remote(machine_id, create_session_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create session: {result.stderr}")

        if json_mode:
            _output_json({
                "success": True,
                "session": f"{target_session}@{machine_id}",
                "path": target_path,
                "branch": target_branch,
                "machine": machine_id,
                "forked_from": source_full,
            })
        else:
            print(f"Forked '{source_full}' to '{target_session}' on {machine_id}")
            print(f"  Path: {target_path}")

        return 0

    # Local fork
    # Build paths
    project_path = projects_dir / source_project

    # Handle non-worktree fork (same directory, different Claude session)
    if is_non_worktree_fork:
        # For non-worktree forks, both use the project directory
        fork_path = project_path

        if not fork_path.exists():
            return _output_result(False, json_mode, f"Source path does not exist: {fork_path}")

        # Check if source session exists
        check_source = subprocess.run(
            ["tmux", "has-session", "-t", source_session],
            capture_output=True
        )
        if check_source.returncode != 0:
            return _output_result(False, json_mode, f"Source session '{source_session}' does not exist")

        # Check if target session already exists
        check_target = subprocess.run(
            ["tmux", "has-session", "-t", target_session],
            capture_output=True
        )
        if check_target.returncode == 0:
            return _output_result(False, json_mode, f"Target session '{target_session}' already exists")

        # Create new tmux session in same directory
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", target_session, "-c", str(fork_path)],
            check=True
        )

        # Ensure Claude starts in correct directory
        subprocess.run(
            ["tmux", "send-keys", "-t", target_session, f"cd {shlex.quote(str(fork_path))}", "Enter"],
            check=True
        )
        time.sleep(0.1)

        # Load source session config from .agentwire.yml to preserve settings
        source_project_config = load_project_config(fork_path)
        if source_project_config:
            session_type = source_project_config.type
        else:
            session_type = SessionType.CLAUDE_BYPASS  # Default

        # Build Claude command based on session type
        claude_cmd = _build_claude_cmd(session_type, None)
        if claude_cmd:
            subprocess.run(
                ["tmux", "send-keys", "-t", target_session, claude_cmd, "Enter"],
                check=True
            )

        if json_mode:
            _output_json({
                "success": True,
                "session": target_session,
                "path": str(fork_path),
                "branch": None,
                "machine": None,
                "forked_from": source_full,
            })
        else:
            print(f"Forked '{source_full}' to '{target_session}' (same directory)")
            print(f"  Path: {fork_path}")

        return 0

    # Worktree fork logic
    if source_branch:
        source_path = projects_dir / f"{source_project}{worktree_suffix}" / source_branch
    else:
        source_path = project_path
    target_path = projects_dir / f"{target_project}{worktree_suffix}" / target_branch

    # Check if target already exists
    if target_path.exists():
        return _output_result(False, json_mode, f"Target worktree already exists: {target_path}")

    # Check source exists
    if not source_path.exists():
        return _output_result(False, json_mode, f"Source path does not exist: {source_path}")

    # Create new worktree from source
    success = ensure_worktree(
        source_path,  # Use source as base for the worktree
        target_branch,
        target_path,
        auto_create_branch=True,
    )
    if not success:
        # Try from project path instead
        if project_path.exists():
            success = ensure_worktree(
                project_path,
                target_branch,
                target_path,
                auto_create_branch=True,
            )

    if not success:
        return _output_result(False, json_mode, f"Failed to create worktree for branch '{target_branch}'")

    # Create new session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", target_session, "-c", str(target_path)],
        check=True
    )

    # Ensure Claude starts in correct directory
    subprocess.run(
        ["tmux", "send-keys", "-t", target_session, f"cd {shlex.quote(str(target_path))}", "Enter"],
        check=True
    )
    time.sleep(0.1)

    restricted = getattr(args, 'restricted', False)
    no_bypass = getattr(args, 'no_bypass', False)
    # Restricted mode implies no bypass (uses hook for permission handling)
    if restricted or no_bypass:
        claude_cmd = "claude"
    else:
        claude_cmd = "claude --dangerously-skip-permissions"

    subprocess.run(
        ["tmux", "send-keys", "-t", target_session, claude_cmd, "Enter"],
        check=True
    )

    if json_mode:
        _output_json({
            "success": True,
            "session": target_session,
            "path": str(target_path),
            "branch": target_branch,
            "machine": None,
            "forked_from": source_full,
        })
    else:
        print(f"Forked '{source_full}' to '{target_session}'")
        print(f"  Path: {target_path}")
        print(f"Attach with: tmux attach -t {target_session}")

    return 0


# === History Commands ===

def format_relative_time(timestamp_ms: int) -> str:
    """Format timestamp as relative time (e.g., '2 hours ago')."""
    from datetime import datetime

    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    delta = datetime.now() - dt

    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"


def cmd_history_list(args) -> int:
    """List conversation history for a project."""
    from .history import get_history

    # Determine project path
    if args.project:
        project_path = Path(args.project).resolve()
        if not project_path.exists():
            print(f"Project path not found: {project_path}", file=sys.stderr)
            return 1
    else:
        # Check if cwd is a tracked project
        config = load_project_config()
        if config is None:
            print("Not in a tracked project directory.", file=sys.stderr)
            print("Use --project <path> or run from a directory with .agentwire.yml", file=sys.stderr)
            return 1
        project_path = Path.cwd().resolve()

    # Get history
    sessions = get_history(
        project_path=str(project_path),
        machine=args.machine,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(sessions, indent=2))
        return 0

    if not sessions:
        print(f"No history found for {project_path}")
        return 0

    print(f"Session history for {project_path.name} ({len(sessions)} sessions):")
    print()

    for session in sessions:
        session_id = session.get("sessionId", "")
        short_id = session_id[:8] if session_id else "?"
        timestamp = session.get("timestamp", 0)
        relative_time = format_relative_time(timestamp) if timestamp else "unknown"
        message_count = session.get("messageCount", 0)
        last_summary = session.get("lastSummary") or session.get("firstMessage", "")

        # Truncate summary for display
        if last_summary and len(last_summary) > 60:
            last_summary = last_summary[:57] + "..."

        print(f"  {short_id}  {relative_time:>15}  ({message_count} msgs)")
        if last_summary:
            print(f"           {last_summary}")
        print()

    return 0


def cmd_history_show(args) -> int:
    """Show details for a specific session."""
    from .history import get_session_detail

    session_id = args.session_id

    # Get session details
    detail = get_session_detail(
        session_id=session_id,
        machine=args.machine,
    )

    if detail is None:
        print(f"Session not found: {session_id}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(detail, indent=2))
        return 0

    # Display formatted output
    full_id = detail.get("sessionId", "?")
    message_count = detail.get("messageCount", 0)
    git_branch = detail.get("gitBranch")
    first_message = detail.get("firstMessage", "")
    summaries = detail.get("summaries", [])
    timestamps = detail.get("timestamps", {})

    start_ts = timestamps.get("start")
    end_ts = timestamps.get("end")

    print(f"Session: {full_id}")
    print()

    if start_ts:
        from datetime import datetime
        start_dt = datetime.fromtimestamp(start_ts / 1000)
        print(f"  Started:  {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    if end_ts:
        from datetime import datetime
        end_dt = datetime.fromtimestamp(end_ts / 1000)
        print(f"  Last msg: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"  Messages: {message_count}")

    if git_branch:
        print(f"  Branch:   {git_branch}")

    print()

    if first_message:
        # Truncate for display
        preview = first_message[:200] + "..." if len(first_message) > 200 else first_message
        print("First message:")
        print(f"  {preview}")
        print()

    if summaries:
        print(f"Summaries ({len(summaries)}):")
        for i, summary in enumerate(summaries, 1):
            # Truncate each summary
            if len(summary) > 100:
                summary = summary[:97] + "..."
            print(f"  {i}. {summary}")
        print()

    return 0


def cmd_history_resume(args) -> int:
    """Resume a Claude Code session (always forks).

    Creates a new tmux session and runs `claude --resume <session-id> --fork-session`
    with appropriate flags based on the project's .agentwire.yml config.
    """
    session_id = args.session_id
    name = getattr(args, 'name', None)
    machine_id = getattr(args, 'machine', 'local')
    project_path_str = args.project
    json_mode = getattr(args, 'json', False)

    # Resolve project path
    project_path = Path(project_path_str).expanduser().resolve()

    # Load project config for type and roles
    project_config = load_project_config(project_path)
    if project_config is None:
        # Default to bypass if no config found
        project_config = ProjectConfig(type=SessionType.CLAUDE_BYPASS, roles=["agentwire"])

    # Generate session name if not provided
    if not name:
        base_name = project_path.name.replace(".", "_")
        # Find unique name with -fork-N suffix
        name = f"{base_name}-fork-1"
        counter = 1
        while True:
            # Check if session exists locally
            check_result = subprocess.run(
                ["tmux", "has-session", "-t", f"={name}"],
                capture_output=True
            )
            if check_result.returncode != 0:
                break  # Session doesn't exist, use this name
            counter += 1
            name = f"{base_name}-fork-{counter}"

    # Build claude command with --resume --fork-session and session type flags
    claude_parts = ["claude", "--resume", session_id, "--fork-session"]
    claude_parts.extend(project_config.type.to_cli_flags())

    # Load and apply roles if specified in config
    if project_config.roles:
        roles, missing = load_roles(project_config.roles, project_path)
        if not missing and roles:
            merged = merge_roles(roles)
            if merged.tools:
                claude_parts.append("--tools")
                claude_parts.extend(sorted(merged.tools))
            if merged.disallowed_tools:
                claude_parts.append("--disallowedTools")
                claude_parts.extend(sorted(merged.disallowed_tools))
            if merged.instructions:
                escaped = merged.instructions.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
                claude_parts.append(f'--append-system-prompt "{escaped}"')
            if merged.model:
                claude_parts.append(f"--model {merged.model}")

    claude_cmd = " ".join(claude_parts)

    if machine_id and machine_id != "local":
        # Remote machine
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        remote_path = str(project_path)

        # Check if session already exists on remote
        check_cmd = f"tmux has-session -t ={shlex.quote(name)} 2>/dev/null"
        result = _run_remote(machine_id, check_cmd)
        if result.returncode == 0:
            return _output_result(False, json_mode, f"Session '{name}' already exists on {machine_id}")

        # Create remote tmux session and send claude command
        create_cmd = (
            f"tmux new-session -d -s {shlex.quote(name)} -c {shlex.quote(remote_path)} && "
            f"tmux send-keys -t {shlex.quote(name)} 'cd {shlex.quote(remote_path)}' Enter && "
            f"sleep 0.1 && "
            f"tmux send-keys -t {shlex.quote(name)} {shlex.quote(claude_cmd)} Enter"
        )

        result = _run_remote(machine_id, create_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create remote session: {result.stderr}")

        if json_mode:
            _output_json({
                "success": True,
                "session": f"{name}@{machine_id}",
                "resumed_from": session_id,
                "path": remote_path,
                "machine": machine_id,
                "type": project_config.type.value,
            })
        else:
            host = machine.get('host', machine_id)
            print(f"Resumed session '{name}' on {machine_id} (forked from {session_id})")
            print(f"Attach via portal or: ssh {host} -t tmux attach -t {name}")

        _notify_portal_sessions_changed()
        return 0

    # Local session
    if not project_path.exists():
        return _output_result(False, json_mode, f"Project path does not exist: {project_path}")

    # Check if session already exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={name}"],
        capture_output=True
    )
    if result.returncode == 0:
        return _output_result(False, json_mode, f"Session '{name}' already exists. Choose a different name with --name.")

    # Create new tmux session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", name, "-c", str(project_path)],
        check=True
    )

    # Ensure Claude starts in correct directory
    subprocess.run(
        ["tmux", "send-keys", "-t", name, f"cd {shlex.quote(str(project_path))}", "Enter"],
        check=True
    )
    time.sleep(0.1)

    # Send the claude resume command
    subprocess.run(
        ["tmux", "send-keys", "-t", name, claude_cmd, "Enter"],
        check=True
    )

    if json_mode:
        _output_json({
            "success": True,
            "session": name,
            "resumed_from": session_id,
            "path": str(project_path),
            "machine": None,
            "type": project_config.type.value,
        })
    else:
        print(f"Resumed session '{name}' (forked from {session_id})")
        print(f"Project: {project_path}")
        print(f"Attach with: tmux attach -t {name}")

    _notify_portal_sessions_changed()
    return 0


# === Machine Commands ===

def cmd_machine_add(args) -> int:
    """Add a machine to the AgentWire network."""
    machine_id = args.machine_id
    host = args.host or machine_id  # Default host to id if not specified
    user = args.user
    projects_dir = args.projects_dir

    machines_file = CONFIG_DIR / "machines.json"
    machines_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing machines
    machines = []
    if machines_file.exists():
        try:
            with open(machines_file) as f:
                machines = json.load(f).get("machines", [])
        except (json.JSONDecodeError, IOError):
            pass

    # Check for duplicate ID
    if any(m.get("id") == machine_id for m in machines):
        print(f"Machine '{machine_id}' already exists", file=sys.stderr)
        return 1

    # Build machine entry
    new_machine = {"id": machine_id, "host": host}
    if user:
        new_machine["user"] = user
    if projects_dir:
        new_machine["projects_dir"] = projects_dir

    machines.append(new_machine)

    # Save
    with open(machines_file, "w") as f:
        json.dump({"machines": machines}, f, indent=2)
        f.write("\n")

    print(f"Added machine '{machine_id}'")
    print(f"  Host: {host}")
    if user:
        print(f"  User: {user}")
    if projects_dir:
        print(f"  Projects: {projects_dir}")
    print()
    print("Next steps:")
    print("  1. Ensure SSH access: ssh", f"{user}@{host}" if user else host)
    print("  2. Start tunnel: autossh -M 0 -f -N -R 8765:localhost:8765", machine_id)
    print("  3. Restart portal: agentwire portal stop && agentwire portal start")
    print()
    print("For full setup guide, run: /machine-setup in a Claude session")

    return 0


def cmd_machine_remove(args) -> int:
    """Remove a machine from the AgentWire network."""
    machine_id = args.machine_id

    machines_file = CONFIG_DIR / "machines.json"

    # Step 1: Load and check machines.json
    if not machines_file.exists():
        print(f"No machines.json found at {machines_file}", file=sys.stderr)
        return 1

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Invalid machines.json: {e}", file=sys.stderr)
        return 1

    machines = machines_data.get("machines", [])
    machine = next((m for m in machines if m.get("id") == machine_id), None)

    if not machine:
        print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
        print(f"Available machines: {', '.join(m.get('id', '?') for m in machines)}")
        return 1

    host = machine.get("host", machine_id)

    print(f"Removing machine '{machine_id}' (host: {host})...")
    print()

    # Step 2: Kill autossh tunnel
    print("Stopping tunnel...")
    result = subprocess.run(
        ["pkill", "-f", f"autossh.*{machine_id}"],
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"  ✓ Killed autossh tunnel for {machine_id}")
    else:
        # Also try by host if different from id
        if host != machine_id:
            result = subprocess.run(
                ["pkill", "-f", f"autossh.*{host}"],
                capture_output=True,
            )
            if result.returncode == 0:
                print(f"  ✓ Killed autossh tunnel for {host}")
            else:
                print(f"  - No tunnel running (or already stopped)")
        else:
            print(f"  - No tunnel running (or already stopped)")

    # Step 3: Remove from machines.json
    print("Updating machines.json...")
    machines_data["machines"] = [m for m in machines if m.get("id") != machine_id]
    with open(machines_file, "w") as f:
        json.dump(machines_data, f, indent=2)
        f.write("\n")
    print(f"  ✓ Removed '{machine_id}' from machines.json")

    # Step 4: Print manual steps
    print()
    print("=" * 50)
    print("MANUAL STEPS REQUIRED:")
    print("=" * 50)
    print()
    print("1. Remove SSH config entry:")
    print(f"   Edit ~/.ssh/config and remove the 'Host {machine_id}' block")
    print()
    print("2. Remove from tunnel startup script (if using):")
    print(f"   Edit ~/.local/bin/agentwire-tunnels")
    print(f"   Remove '{machine_id}' from the MACHINES list")
    print()
    print("3. Delete GitHub deploy keys:")
    print(f"   gh repo deploy-key list --repo <user>/<repo>")
    print(f"   # Find keys titled '{machine_id}' and delete them:")
    print(f"   gh repo deploy-key delete <key-id> --repo <user>/<repo>")
    print()
    print("4. Destroy remote machine:")
    print(f"   Option A: Delete user only")
    print(f"     ssh root@<ip> 'pkill -u agentwire; userdel -r agentwire'")
    print(f"   Option B: Destroy the VM entirely via provider console")
    print()
    print("5. Restart portal to pick up changes:")
    print("   agentwire portal stop && agentwire portal start")
    print()

    return 0


def cmd_machine_list(args) -> int:
    """List registered machines."""
    machines_file = CONFIG_DIR / "machines.json"

    if not machines_file.exists():
        print("No machines registered.")
        print(f"  Config: {machines_file}")
        return 0

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Invalid machines.json: {e}", file=sys.stderr)
        return 1

    machines = machines_data.get("machines", [])

    if not machines:
        print("No machines registered.")
        return 0

    print(f"Registered machines ({len(machines)}):")
    print()
    for m in machines:
        machine_id = m.get("id", "?")
        host = m.get("host", machine_id)
        projects_dir = m.get("projects_dir", "~")

        # Check if tunnel is running
        result = subprocess.run(
            ["pgrep", "-f", f"autossh.*{machine_id}"],
            capture_output=True,
        )
        tunnel_status = "✓ tunnel" if result.returncode == 0 else "✗ no tunnel"

        print(f"  {machine_id}")
        print(f"    Host: {host}")
        print(f"    Projects: {projects_dir}")
        print(f"    Status: {tunnel_status}")
        print()

    return 0


# === Dev Command ===

def cmd_dev(args) -> int:
    """Start or attach to the AgentWire dev/agentwire session."""
    session_name = "agentwire"
    project_dir = Path.home() / "projects" / "agentwire"

    if tmux_session_exists(session_name):
        print(f"Dev session exists. Attaching to '{session_name}'...")
        subprocess.run(["tmux", "attach-session", "-t", session_name])
        return 0

    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 1

    # Load agentwire role for dev session
    dev_roles, _ = load_roles(["agentwire"], project_dir)
    claude_cmd = _build_claude_cmd(SessionType.CLAUDE_BYPASS, roles=dev_roles if dev_roles else None)

    # Create session
    print(f"Creating dev session '{session_name}' in {project_dir}...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name, "-c", str(project_dir),
    ])

    # Start Claude with agentwire config
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, claude_cmd, "Enter",
    ])

    print(f"Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


# === Init Command ===

def cmd_init(args) -> int:
    """Initialize AgentWire configuration with interactive wizard.

    Default behavior: Run full wizard with optional agentwire setup at the end.
    Quick mode (--quick): Run wizard only, skip agentwire setup prompt.
    """
    # Check Python version first
    if not check_python_version():
        return 1

    # Check for externally-managed environment (Ubuntu)
    if not check_pip_environment():
        print("Please set up a virtual environment before running init.")
        return 1

    from .onboarding import run_onboarding

    if args.quick:
        # Quick mode: run wizard but skip agentwire step
        # We do this by running onboarding and returning before agentwire prompt
        # The onboarding module handles this internally
        return run_onboarding(skip_agentwire=True)

    # Default: run full wizard (ends with optional agentwire setup)
    return run_onboarding()


def cmd_generate_certs(args) -> int:
    """Generate SSL certificates."""
    return generate_certs()


# === Listen Commands ===

def cmd_listen_start(args) -> int:
    """Start voice recording."""
    from .listen import start_recording
    return start_recording()


def cmd_listen_stop(args) -> int:
    """Stop recording, transcribe, send to session or type at cursor."""
    from .listen import stop_recording
    session = args.session or "agentwire"
    type_at_cursor = getattr(args, 'type', False)
    return stop_recording(session, voice_prompt=not args.no_prompt, type_at_cursor=type_at_cursor)


def cmd_listen_cancel(args) -> int:
    """Cancel current recording."""
    from .listen import cancel_recording
    return cancel_recording()


def cmd_listen_toggle(args) -> int:
    """Toggle recording (start if not recording, stop if recording)."""
    from .listen import is_recording, start_recording, stop_recording
    session = args.session or "agentwire"
    if is_recording():
        return stop_recording(session, voice_prompt=not args.no_prompt)
    else:
        return start_recording()


# === Network Commands ===


def cmd_network_status(args) -> int:
    """Show complete network health at a glance."""
    import socket
    from .network import NetworkContext
    from .tunnels import TunnelManager, test_ssh_connectivity, test_service_health

    ctx = NetworkContext.from_config()
    tm = TunnelManager()
    issues = []

    # Print header
    print("AgentWire Network Status")
    print("=" * 60)
    hostname = ctx.local_machine_id or socket.gethostname()
    print(f"\nYou are on: {hostname}")

    # Check machines (SSH connectivity)
    print("\nMachines")
    print("-" * 60)

    for machine_id, machine in ctx.machines.items():
        is_local = machine_id == ctx.local_machine_id
        host = machine.get("host", machine_id)
        user = machine.get("user")

        if is_local:
            print(f"  {machine_id:<16}(this machine)    [ok] reachable")
        else:
            latency = test_ssh_connectivity(host, user, timeout=5)
            if latency is not None:
                print(f"  {machine_id:<16}{host:<18}[ok] reachable (ssh: {latency}ms)")
            else:
                print(f"  {machine_id:<16}{host:<18}[!!] unreachable")
                issues.append({
                    "type": "machine_unreachable",
                    "machine": machine_id,
                    "host": host,
                })

    # Check services
    print("\nServices")
    print("-" * 60)

    for service_name in ["portal", "tts"]:
        service_config = getattr(ctx.config.services, service_name, None)
        if service_config is None:
            continue

        if ctx.is_local(service_name):
            location = f"localhost:{service_config.port}"
            via = "(local)"
        else:
            machine = service_config.machine
            location = f"{machine}:{service_config.port}"
            via = "(via tunnel)"

        # Test the service health
        url = ctx.get_service_url(service_name)
        health_url = f"{url}{service_config.health_endpoint}"
        is_healthy, error = test_service_health(health_url, timeout=3)

        if is_healthy:
            print(f"  {service_name.capitalize():<16}{location:<18}[ok] running {via}")
        else:
            print(f"  {service_name.capitalize():<16}{location:<18}[!!] not responding")
            issues.append({
                "type": "service_down",
                "service": service_name,
                "location": location,
                "error": error,
            })

    # Check tunnels
    required_tunnels = ctx.get_required_tunnels()
    if required_tunnels:
        print("\nTunnels (this machine)")
        print("-" * 60)

        for spec in required_tunnels:
            status = tm.check_tunnel(spec)
            target = f"localhost:{spec.local_port}"

            if status.status == "up":
                print(f"  -> {spec.remote_machine:<12}{target:<18}[ok] up (PID {status.pid})")
            else:
                print(f"  -> {spec.remote_machine:<12}{target:<18}[!!] down")
                issues.append({
                    "type": "tunnel_down",
                    "spec": spec,
                    "error": status.error,
                })

    # Check for worker sessions
    print("\nWorker Sessions")
    print("-" * 60)

    # Local sessions
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sessions = [s for s in result.stdout.strip().split("\n") if s and not s.startswith("agentwire")]
        if sessions:
            print(f"  {hostname:<16}{len(sessions)} sessions    {', '.join(sessions[:5])}")
            if len(sessions) > 5:
                print(f"  {'':<16}... and {len(sessions) - 5} more")
        else:
            print(f"  {hostname:<16}0 sessions")
    else:
        print(f"  {hostname:<16}(no tmux server)")

    # Remote sessions
    for machine_id, machine in ctx.machines.items():
        if machine_id == ctx.local_machine_id:
            continue

        result = _run_remote(machine_id, "tmux list-sessions -F '#{session_name}' 2>/dev/null")
        if result.returncode == 0 and result.stdout.strip():
            sessions = [s for s in result.stdout.strip().split("\n") if s]
            if sessions:
                print(f"  {machine_id:<16}{len(sessions)} sessions    {', '.join(sessions[:5])}")
                if len(sessions) > 5:
                    print(f"  {'':<16}... and {len(sessions) - 5} more")
        else:
            print(f"  {machine_id:<16}0 sessions")

    # Summary
    print()
    if not issues:
        print("Everything looks good!")
    else:
        print(f"Issues detected: {len(issues)}")
        print()
        for i, issue in enumerate(issues, 1):
            if issue["type"] == "machine_unreachable":
                print(f"  {i}. Machine '{issue['machine']}' unreachable")
                print(f"     Host: {issue['host']}")
                print()
                print("     To fix:")
                print(f"       Check SSH connectivity: ssh {issue['host']}")
                print(f"       Verify machine is running")
                print()

            elif issue["type"] == "service_down":
                print(f"  {i}. {issue['service'].capitalize()} not responding")
                print(f"     Location: {issue['location']}")
                if issue.get("error"):
                    print(f"     Error: {issue['error']}")
                print()
                print("     To fix:")
                if issue["service"] == "portal":
                    print("       agentwire portal start")
                elif issue["service"] == "tts":
                    print("       agentwire tts start")
                print("       agentwire tunnels check  # Verify tunnel health")
                print()

            elif issue["type"] == "tunnel_down":
                spec = issue["spec"]
                print(f"  {i}. Missing tunnel")
                print(f"     Required: localhost:{spec.local_port} -> {spec.remote_machine}:{spec.remote_port}")
                if issue.get("error"):
                    print(f"     Error: {issue['error']}")
                print()
                print("     To fix:")
                print("       agentwire tunnels up")
                print()

        print("-" * 60)
        print()
        print("Run: agentwire doctor    # Auto-fix common issues")

    return 0 if not issues else 1


def cmd_safety_check(args) -> int:
    """CLI command: agentwire safety check"""
    command = args.command
    verbose = getattr(args, 'verbose', False)
    return cli_safety.safety_check_cmd(command, verbose)


def cmd_safety_status(args) -> int:
    """CLI command: agentwire safety status"""
    return cli_safety.safety_status_cmd()


def cmd_safety_logs(args) -> int:
    """CLI command: agentwire safety logs"""
    tail = getattr(args, 'tail', None)
    session = getattr(args, 'session', None)
    today = getattr(args, 'today', False)
    pattern = getattr(args, 'pattern', None)
    return cli_safety.safety_logs_cmd(tail, session, today, pattern)


def cmd_safety_install(args) -> int:
    """CLI command: agentwire safety install"""
    return cli_safety.safety_install_cmd()


def cmd_doctor(args) -> int:
    """Auto-diagnose and fix common issues."""
    from .network import NetworkContext
    from .tunnels import TunnelManager, test_ssh_connectivity, test_service_health
    from .validation import validate_config

    dry_run = getattr(args, 'dry_run', False)
    auto_confirm = getattr(args, 'yes', False)

    print("AgentWire Doctor")
    print("=" * 60)

    issues_found = 0
    issues_fixed = 0

    # 1. Check Python version
    print("\nChecking Python version...")
    py_version = sys.version_info
    version_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
    if py_version >= (3, 10):
        print(f"  [ok] Python {version_str} (>=3.10 required)")
    else:
        print(f"  [!!] Python {version_str} (>=3.10 required)")
        print("     macOS: pyenv install 3.12.0 && pyenv global 3.12.0")
        print("     Ubuntu: sudo apt update && sudo apt install python3.12")
        issues_found += 1

    # 2. Check system dependencies
    print("\nChecking system dependencies...")

    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"  [ok] ffmpeg: {ffmpeg_path}")
    else:
        print("  [!!] ffmpeg: not found")
        print("     macOS: brew install ffmpeg")
        print("     Ubuntu: sudo apt install ffmpeg")
        issues_found += 1

    # 3. Check AgentWire scripts
    print("\nChecking AgentWire scripts...")

    say_path = shutil.which("say")

    scripts_missing = False
    if say_path:
        print(f"  [ok] say: {say_path}")
    else:
        print("  [!!] say: not found")
        scripts_missing = True
        issues_found += 1

    # Offer to fix missing scripts
    if scripts_missing and not dry_run:
        if auto_confirm or _confirm("     Install say script?"):
            print("     -> Installing scripts...", end=" ", flush=True)

            # Create a minimal args object for cmd_skills_install
            class SkillsArgs:
                force = False
                copy = False

            skills_args = SkillsArgs()
            result = cmd_skills_install(skills_args)

            if result == 0:
                print("[ok] installed")
                issues_fixed += 1
            else:
                print("[!!] failed")

    # 4. Check Claude Code hooks
    print("\nChecking Claude Code hooks...")

    permission_hook = CLAUDE_HOOKS_DIR / "agentwire-permission.sh"
    if permission_hook.exists():
        print(f"  [ok] Permission hook: {permission_hook}")
    else:
        print(f"  [!!] Permission hook: not found")
        print("     Run: agentwire skills install")
        issues_found += 1

    skills_dir = CLAUDE_SKILLS_DIR / "agentwire"
    if skills_dir.exists():
        print(f"  [ok] Skills linked: {skills_dir}")
    else:
        print(f"  [!!] Skills not linked")
        print("     Run: agentwire skills install")
        issues_found += 1

    # 5. Validate config
    print("\nChecking configuration...")
    try:
        from .config import load_config as load_config_typed
        config = load_config_typed()
        print("  [ok] Config file valid")
    except Exception as e:
        print(f"  [!!] Config file error: {e}")
        print("     Run: agentwire init")
        issues_found += 1
        return 1  # Can't proceed without valid config

    machines_file = config.machines.file
    warnings, errors = validate_config(config, machines_file)

    if not errors:
        print("  [ok] Machines.json valid")
    else:
        for err in errors:
            print(f"  [!!] {err.message}")
            issues_found += 1

    if not warnings:
        print("  [ok] All config checks passed")
    else:
        for warn in warnings:
            print(f"  [..] {warn.message}")

    # 6. Check SSH connectivity
    print("\nChecking SSH connectivity...")
    ctx = NetworkContext.from_config()

    for machine_id, machine in ctx.machines.items():
        if machine_id == ctx.local_machine_id:
            continue

        host = machine.get("host", machine_id)
        user = machine.get("user")

        latency = test_ssh_connectivity(host, user, timeout=5)
        if latency is not None:
            print(f"  [ok] {machine_id}: reachable ({latency}ms)")
        else:
            print(f"  [!!] {machine_id}: unreachable")
            issues_found += 1

    # 7. Check/create tunnels
    print("\nChecking tunnels...")
    tm = TunnelManager()
    required_tunnels = ctx.get_required_tunnels()

    if not required_tunnels:
        print("  [ok] No tunnels required (services are local)")
    else:
        for spec in required_tunnels:
            status = tm.check_tunnel(spec)

            if status.status == "up":
                print(f"  [ok] localhost:{spec.local_port} -> {spec.remote_machine}:{spec.remote_port} (PID {status.pid})")
            else:
                print(f"  [!!] Missing: localhost:{spec.local_port} -> {spec.remote_machine}:{spec.remote_port}")
                issues_found += 1

                if not dry_run:
                    if auto_confirm or _confirm("     Create tunnel?"):
                        print("     -> Creating tunnel...", end=" ", flush=True)
                        result = tm.create_tunnel(spec, ctx)
                        if result.status == "up":
                            print(f"[ok] created (PID {result.pid})")
                            issues_fixed += 1
                        else:
                            print(f"[!!] failed: {result.error}")
                else:
                    print("     -> Would create tunnel (dry-run)")

    # 8. Check services
    print("\nChecking services...")

    for service_name in ["portal", "tts"]:
        service_config = getattr(ctx.config.services, service_name, None)
        if service_config is None:
            continue

        url = ctx.get_service_url(service_name)
        health_url = f"{url}{service_config.health_endpoint}"
        is_healthy, error = test_service_health(health_url, timeout=3)

        if is_healthy:
            print(f"  [ok] {service_name.capitalize()}: responding on {url}")
        else:
            print(f"  [!!] {service_name.capitalize()}: not responding on {url}")
            if error:
                print(f"       Error: {error}")
            issues_found += 1

            # Only try to fix if service is local
            if ctx.is_local(service_name):
                if not dry_run:
                    if auto_confirm or _confirm(f"     Start {service_name}?"):
                        print(f"     -> Starting {service_name}...", end=" ", flush=True)

                        if service_name == "portal":
                            session_name = "agentwire-portal"
                            if tmux_session_exists(session_name):
                                print("[ok] already running in tmux")
                            else:
                                subprocess.run(
                                    ["tmux", "new-session", "-d", "-s", session_name],
                                    capture_output=True,
                                )
                                subprocess.run(
                                    ["tmux", "send-keys", "-t", session_name, "agentwire portal serve", "Enter"],
                                    capture_output=True,
                                )
                                print("[ok] started")
                                issues_fixed += 1

                        elif service_name == "tts":
                            session_name = "agentwire-tts"
                            if tmux_session_exists(session_name):
                                print("[ok] already running in tmux")
                            else:
                                subprocess.run(
                                    ["tmux", "new-session", "-d", "-s", session_name],
                                    capture_output=True,
                                )
                                subprocess.run(
                                    ["tmux", "send-keys", "-t", session_name, "agentwire tts serve", "Enter"],
                                    capture_output=True,
                                )
                                print("[ok] started")
                                issues_fixed += 1
                else:
                    print(f"     -> Would start {service_name} (dry-run)")
            else:
                print(f"     -> Service is remote, start it on {service_config.machine}")

    # 9. Validate remote machines
    print("\nChecking remote machines...")
    remote_machines = {mid: m for mid, m in ctx.machines.items() if mid != ctx.local_machine_id}

    if not remote_machines:
        print("  [ok] No remote machines configured")
    else:
        for machine_id, machine in remote_machines.items():
            host = machine.get("host", machine_id)
            user = machine.get("user")
            target = f"{user}@{host}" if user else host

            print(f"\n  {machine_id}:")

            # Check SSH connectivity (already done above, but include latency here)
            latency = test_ssh_connectivity(host, user, timeout=5)
            if latency is not None:
                print(f"    [ok] SSH connectivity ({latency}ms)")
            else:
                print(f"    [!!] SSH connectivity failed")
                print(f"         Fix: ssh {target}")
                issues_found += 1
                continue  # Can't check further if SSH fails

            # Check if agentwire is installed
            try:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", target, "agentwire --version"],
                    capture_output=True,
                    text=True,
                    timeout=7,
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print(f"    [ok] agentwire installed ({version})")
                else:
                    print(f"    [!!] agentwire not installed")
                    print(f"         Fix: ssh {target} 'pip install git+https://github.com/dotdevdotdev/agentwire.git'")
                    issues_found += 1
                    continue
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                print(f"    [!!] agentwire not installed")
                print(f"         Fix: ssh {target} 'pip install git+https://github.com/dotdevdotdev/agentwire.git'")
                issues_found += 1
                continue

            # Check portal_url file
            try:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", target, "cat ~/.agentwire/portal_url"],
                    capture_output=True,
                    text=True,
                    timeout=7,
                )
                if result.returncode == 0:
                    portal_url = result.stdout.strip()
                    print(f"    [ok] portal_url set ({portal_url})")
                else:
                    print(f"    [!!] portal_url not set")
                    print(f"         Fix: ssh {target} 'echo \"https://localhost:8765\" > ~/.agentwire/portal_url'")
                    issues_found += 1
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                print(f"    [!!] portal_url not set")
                print(f"         Fix: ssh {target} 'echo \"https://localhost:8765\" > ~/.agentwire/portal_url'")
                issues_found += 1

            # Check if skills are installed
            try:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", target, "test -d ~/.claude/skills/agentwire && echo ok"],
                    capture_output=True,
                    text=True,
                    timeout=7,
                )
                if result.returncode == 0 and result.stdout.strip() == "ok":
                    print(f"    [ok] Skills installed")
                else:
                    print(f"    [!!] Skills not installed")
                    print(f"         Fix: ssh {target} 'agentwire skills install'")
                    issues_found += 1
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                print(f"    [!!] Skills not installed")
                print(f"         Fix: ssh {target} 'agentwire skills install'")
                issues_found += 1

            # Test say command
            try:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", target, "which say"],
                    capture_output=True,
                    text=True,
                    timeout=7,
                )
                if result.returncode == 0:
                    print(f"    [ok] say command available")
                else:
                    print(f"    [!!] say command not found")
                    print(f"         Fix: ssh {target} 'agentwire skills install'")
                    issues_found += 1
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                print(f"    [!!] say command not found")
                print(f"         Fix: ssh {target} 'agentwire skills install'")
                issues_found += 1

    # Summary
    print()
    print("-" * 60)
    if issues_found == 0:
        print("All checks passed!")
    elif issues_fixed == issues_found:
        print(f"All issues resolved! ({issues_fixed} fixed)")
    elif issues_fixed > 0:
        print(f"Fixed {issues_fixed} of {issues_found} issues")
    else:
        print(f"Found {issues_found} issues")

    return 0 if issues_found == issues_fixed else 1


def _confirm(prompt: str) -> bool:
    """Ask for user confirmation."""
    try:
        response = input(f"{prompt} [y/N] ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


# === Voice Clone Commands ===

def cmd_voiceclone_start(args) -> int:
    """Start voice recording for cloning."""
    from .voiceclone import start_recording
    return start_recording()


def cmd_voiceclone_stop(args) -> int:
    """Stop recording and upload voice clone."""
    from .voiceclone import stop_recording
    return stop_recording(args.name)


def cmd_voiceclone_cancel(args) -> int:
    """Cancel current recording."""
    from .voiceclone import cancel_recording
    return cancel_recording()


def cmd_voiceclone_list(args) -> int:
    """List available voices."""
    from .voiceclone import list_voices
    return list_voices()


def cmd_voiceclone_delete(args) -> int:
    """Delete a voice."""
    from .voiceclone import delete_voice
    return delete_voice(args.name)


# === Rebuild/Uninstall Commands ===

UV_CACHE_DIR = Path.home() / ".cache" / "uv"


def cmd_rebuild(args) -> int:
    """Rebuild: clear uv cache, uninstall, reinstall from source.

    This is the correct way to pick up source changes when developing.
    `uv tool install . --force` does NOT work - it uses cached wheels.
    """
    print("Rebuilding agentwire-dev...")
    print()

    # Step 1: Clear uv cache
    if UV_CACHE_DIR.exists():
        print(f"Clearing uv cache ({UV_CACHE_DIR})...")
        shutil.rmtree(UV_CACHE_DIR)
        print("  ✓ Cache cleared")
    else:
        print("  - No cache to clear")

    # Step 2: Uninstall
    print("Uninstalling agentwire-dev...")
    result = subprocess.run(
        ["uv", "tool", "uninstall", "agentwire-dev"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✓ Uninstalled")
    else:
        # Might not be installed, that's fine
        print("  - Not installed (continuing)")

    # Step 3: Reinstall from current directory
    # Find the project root (where pyproject.toml is)
    project_root = Path(__file__).parent.parent
    if not (project_root / "pyproject.toml").exists():
        # Fallback: assume we're in ~/projects/agentwire
        project_root = Path.home() / "projects" / "agentwire"

    print(f"Installing from {project_root}...")
    result = subprocess.run(
        ["uv", "tool", "install", "."],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ✗ Install failed: {result.stderr}", file=sys.stderr)
        return 1

    print("  ✓ Installed")
    print()
    print("Rebuild complete. New version is active.")
    return 0


def cmd_uninstall(args) -> int:
    """Uninstall: clear uv cache and remove agentwire-dev tool."""
    print("Uninstalling agentwire-dev...")
    print()

    # Step 1: Clear uv cache
    if UV_CACHE_DIR.exists():
        print(f"Clearing uv cache ({UV_CACHE_DIR})...")
        shutil.rmtree(UV_CACHE_DIR)
        print("  ✓ Cache cleared")
    else:
        print("  - No cache to clear")

    # Step 2: Uninstall
    print("Uninstalling tool...")
    result = subprocess.run(
        ["uv", "tool", "uninstall", "agentwire-dev"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✓ Uninstalled")
    else:
        print(f"  - {result.stderr.strip() or 'Not installed'}")

    print()
    print("Uninstall complete.")
    print("To reinstall: cd ~/projects/agentwire && uv tool install .")
    return 0


# === Skills Commands ===

CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"
CLAUDE_HOOKS_DIR = Path.home() / ".claude" / "hooks"


def get_skills_source() -> Path:
    """Get the path to the skills directory in the installed package."""
    # First try: skills directory inside the agentwire package
    package_dir = Path(__file__).parent
    skills_dir = package_dir / "skills"
    if skills_dir.exists():
        return skills_dir

    # Fallback: try importlib.resources (for installed packages)
    try:
        with importlib.resources.files("agentwire").joinpath("skills") as p:
            if p.exists():
                return Path(p)
    except (TypeError, FileNotFoundError):
        pass

    raise FileNotFoundError("Could not find skills directory in package")


# =============================================================================
# Template Commands
# =============================================================================


def cmd_template_list(args) -> int:
    """List available session templates."""
    from .config import load_templates

    json_mode = getattr(args, 'json', False)
    templates = load_templates()

    if json_mode:
        _output_json([t.to_dict() for t in templates])
        return 0

    if not templates:
        print("No templates found.")
        print(f"Create one with: agentwire template create <name>")
        print(f"Templates directory: ~/.agentwire/templates/")
        return 0

    print(f"Available templates ({len(templates)}):\n")
    for t in templates:
        mode = "restricted" if t.restricted else ("bypass" if t.bypass_permissions else "prompted")
        print(f"  {t.name}")
        if t.description:
            print(f"    {t.description}")
        if t.voice:
            print(f"    Voice: {t.voice}")
        if t.project:
            print(f"    Project: {t.project}")
        print(f"    Mode: {mode}")
        if t.initial_prompt:
            # Show first line of initial prompt
            first_line = t.initial_prompt.strip().split('\n')[0][:60]
            print(f"    Prompt: {first_line}...")
        print()

    return 0


def cmd_template_show(args) -> int:
    """Show details of a specific template."""
    from .config import load_template

    name = args.name
    json_mode = getattr(args, 'json', False)

    template = load_template(name)
    if template is None:
        if json_mode:
            _output_json({"error": f"Template '{name}' not found"})
        else:
            print(f"Template '{name}' not found.", file=sys.stderr)
        return 1

    if json_mode:
        _output_json(template.to_dict())
        return 0

    print(f"Template: {template.name}")
    print(f"Description: {template.description or '(none)'}")
    print(f"Voice: {template.voice or '(default)'}")
    print(f"Roles: {', '.join(template.roles) if template.roles else '(none)'}")
    print(f"Project: {template.project or '(none)'}")
    mode = "restricted" if template.restricted else ("bypass" if template.bypass_permissions else "prompted")
    print(f"Permission Mode: {mode}")
    print()
    if template.initial_prompt:
        print("Initial Prompt:")
        print("-" * 40)
        print(template.initial_prompt)
        print("-" * 40)
    else:
        print("Initial Prompt: (none)")

    return 0


def cmd_template_create(args) -> int:
    """Create a new session template interactively."""
    from .config import Template, save_template, load_template

    name = args.name
    json_mode = getattr(args, 'json', False)

    # Check if template already exists
    existing = load_template(name)
    if existing:
        if not args.force:
            if json_mode:
                _output_json({"error": f"Template '{name}' already exists. Use --force to overwrite."})
            else:
                print(f"Template '{name}' already exists. Use --force to overwrite.", file=sys.stderr)
            return 1

    if json_mode:
        # In JSON mode, require --description and --prompt
        roles_arg = getattr(args, 'roles', None)
        roles_list = [r.strip() for r in roles_arg.split(",")] if roles_arg else []
        template = Template(
            name=name,
            description=args.description or "",
            voice=args.voice,
            roles=roles_list,
            project=args.project,
            initial_prompt=args.prompt or "",
            bypass_permissions=not args.no_bypass,
            restricted=args.restricted or False,
        )
    else:
        # Interactive mode
        print(f"Creating template: {name}\n")

        description = input("Description (optional): ").strip()

        print("\nEnter initial prompt (end with a line containing just '.'):")
        lines = []
        while True:
            line = input()
            if line == '.':
                break
            lines.append(line)
        initial_prompt = '\n'.join(lines)

        voice = input("\nVoice (optional, press Enter for default): ").strip() or None
        roles_input = input("Roles (comma-separated, e.g., worker,code-review): ").strip()
        roles_list = [r.strip() for r in roles_input.split(",")] if roles_input else []
        project = input("Default project path (optional): ").strip() or None

        print("\nPermission mode:")
        print("  1. Bypass (default - no prompts)")
        print("  2. Normal (permission prompts)")
        print("  3. Restricted (voice-only, all else denied)")
        mode_choice = input("Select [1/2/3]: ").strip()

        bypass_permissions = mode_choice != "2"
        restricted = mode_choice == "3"

        template = Template(
            name=name,
            description=description,
            voice=voice,
            roles=roles_list,
            project=project,
            initial_prompt=initial_prompt,
            bypass_permissions=bypass_permissions,
            restricted=restricted,
        )

    if save_template(template):
        if json_mode:
            _output_json({"success": True, "template": template.to_dict()})
        else:
            print(f"\nTemplate '{name}' saved to ~/.agentwire/templates/{name}.yaml")
        return 0
    else:
        if json_mode:
            _output_json({"error": "Failed to save template"})
        else:
            print("Failed to save template.", file=sys.stderr)
        return 1


def cmd_template_delete(args) -> int:
    """Delete a session template."""
    from .config import delete_template, load_template

    name = args.name
    json_mode = getattr(args, 'json', False)

    # Check if template exists
    template = load_template(name)
    if template is None:
        if json_mode:
            _output_json({"error": f"Template '{name}' not found"})
        else:
            print(f"Template '{name}' not found.", file=sys.stderr)
        return 1

    if not args.force:
        confirm = input(f"Delete template '{name}'? [y/N] ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return 1

    if delete_template(name):
        if json_mode:
            _output_json({"success": True, "deleted": name})
        else:
            print(f"Template '{name}' deleted.")
        return 0
    else:
        if json_mode:
            _output_json({"error": "Failed to delete template"})
        else:
            print("Failed to delete template.", file=sys.stderr)
        return 1


def get_sample_templates_source() -> Path:
    """Get the path to the sample_templates directory in the installed package."""
    # First try: sample_templates directory inside the agentwire package
    package_dir = Path(__file__).parent
    templates_dir = package_dir / "sample_templates"
    if templates_dir.exists():
        return templates_dir

    # Fallback: try importlib.resources (for installed packages)
    try:
        with importlib.resources.files("agentwire").joinpath("sample_templates") as p:
            if p.exists():
                return Path(p)
    except (TypeError, FileNotFoundError):
        pass

    raise FileNotFoundError("Could not find sample_templates directory in package")


def cmd_template_install_samples(args) -> int:
    """Install sample templates to ~/.agentwire/templates/."""
    from .config import get_config

    json_mode = getattr(args, 'json', False)
    force = getattr(args, 'force', False)

    try:
        source_dir = get_sample_templates_source()
    except FileNotFoundError as e:
        if json_mode:
            _output_json({"error": str(e)})
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    config = get_config()
    target_dir = config.templates.dir
    target_dir.mkdir(parents=True, exist_ok=True)

    installed = []
    skipped = []

    for template_file in source_dir.glob("*.yaml"):
        target_file = target_dir / template_file.name

        if target_file.exists() and not force:
            skipped.append(template_file.stem)
            continue

        shutil.copy2(template_file, target_file)
        installed.append(template_file.stem)

    if json_mode:
        _output_json({
            "success": True,
            "installed": installed,
            "skipped": skipped,
            "target_dir": str(target_dir),
        })
    else:
        if installed:
            print(f"Installed templates: {', '.join(installed)}")
        if skipped:
            print(f"Skipped (already exist): {', '.join(skipped)}")
        if not installed and not skipped:
            print("No sample templates found.")
        print(f"Templates directory: {target_dir}")

    return 0


# =============================================================================
# Roles Commands
# =============================================================================


def cmd_roles_list(args) -> int:
    """List available roles from all sources."""
    from .roles import parse_role_file

    json_mode = getattr(args, 'json', False)

    # Collect roles from all sources
    roles_data = []

    # User roles (~/.agentwire/roles/)
    user_roles_dir = Path.home() / ".agentwire" / "roles"
    if user_roles_dir.exists():
        for role_file in user_roles_dir.glob("*.md"):
            role = parse_role_file(role_file)
            if role:
                roles_data.append({
                    "name": role.name,
                    "description": role.description,
                    "source": "user",
                    "path": str(role_file),
                    "disallowed_tools": role.disallowed_tools,
                    "model": role.model,
                })

    # Bundled roles (agentwire/roles/)
    try:
        bundled_dir = Path(__file__).parent / "roles"
        if bundled_dir.exists():
            for role_file in bundled_dir.glob("*.md"):
                # Skip if user already has this role
                if any(r["name"] == role_file.stem for r in roles_data):
                    continue
                role = parse_role_file(role_file)
                if role:
                    roles_data.append({
                        "name": role.name,
                        "description": role.description,
                        "source": "bundled",
                        "path": str(role_file),
                        "disallowed_tools": role.disallowed_tools,
                        "model": role.model,
                    })
    except Exception:
        pass

    if json_mode:
        _output_json({"roles": roles_data})
        return 0

    if not roles_data:
        print("No roles found.")
        print(f"Create roles in: ~/.agentwire/roles/")
        return 0

    # Print table
    print("Available Roles:")
    print()
    print(f"{'Name':<20} {'Source':<10} {'Description':<40}")
    print("-" * 70)
    for r in sorted(roles_data, key=lambda x: x["name"]):
        desc = r["description"][:37] + "..." if len(r["description"]) > 40 else r["description"]
        print(f"{r['name']:<20} {r['source']:<10} {desc:<40}")

    print()
    print(f"User roles: ~/.agentwire/roles/")
    print(f"Use 'agentwire roles show <name>' for details")
    return 0


def cmd_projects_list(args) -> int:
    """List discovered projects."""
    from .projects import get_projects

    json_mode = getattr(args, 'json', False)
    machine_filter = getattr(args, 'machine', None)

    projects = get_projects(machine=machine_filter)

    if json_mode:
        _output_json({"projects": projects})
        return 0

    if not projects:
        print("No projects found.")
        print("Projects need a .agentwire.yml file in their directory.")
        return 0

    # Print table
    print(f"Discovered Projects ({len(projects)}):\n")
    print(f"{'Name':<25} {'Type':<15} {'Path':<40}")
    print("-" * 80)
    for p in projects:
        # Truncate long paths
        path = p["path"]
        if len(path) > 40:
            path = "..." + path[-37:]
        machine_suffix = f" @{p['machine']}" if p['machine'] != 'local' else ""
        print(f"{p['name']:<25} {p['type']:<15} {path:<40}{machine_suffix}")

    print()
    return 0


def cmd_roles_show(args) -> int:
    """Show details for a specific role."""
    from .roles import discover_role, parse_role_file

    name = args.name
    json_mode = getattr(args, 'json', False)

    # Discover role
    role_path = discover_role(name)
    if not role_path:
        if json_mode:
            _output_json({"error": f"Role '{name}' not found"})
        else:
            print(f"Role '{name}' not found.", file=sys.stderr)
            print(f"Available locations:")
            print(f"  User: ~/.agentwire/roles/{name}.md")
            print(f"  Bundled: agentwire/roles/{name}.md")
        return 1

    role = parse_role_file(role_path)
    if not role:
        if json_mode:
            _output_json({"error": f"Failed to parse role file"})
        else:
            print(f"Failed to parse role file: {role_path}", file=sys.stderr)
        return 1

    if json_mode:
        _output_json({
            "name": role.name,
            "description": role.description,
            "path": str(role_path),
            "tools": role.tools,
            "disallowed_tools": role.disallowed_tools,
            "model": role.model,
            "color": role.color,
            "instructions": role.instructions,
        })
        return 0

    print(f"Role: {role.name}")
    print(f"Description: {role.description or '(none)'}")
    print(f"Path: {role_path}")
    print(f"Model: {role.model or 'inherit'}")
    if role.tools:
        print(f"Tools (whitelist): {', '.join(role.tools)}")
    if role.disallowed_tools:
        print(f"Disallowed Tools: {', '.join(role.disallowed_tools)}")
    print()
    if role.instructions:
        print("Instructions:")
        print("-" * 40)
        print(role.instructions)
        print("-" * 40)
    else:
        print("Instructions: (none)")

    return 0


def get_hooks_source() -> Path:
    """Get the path to the hooks directory in the installed package."""
    # First try: hooks directory inside the agentwire package
    package_dir = Path(__file__).parent
    hooks_dir = package_dir / "hooks"
    if hooks_dir.exists():
        return hooks_dir

    # Fallback: try importlib.resources (for installed packages)
    try:
        with importlib.resources.files("agentwire").joinpath("hooks") as p:
            if p.exists():
                return Path(p)
    except (TypeError, FileNotFoundError):
        pass

    raise FileNotFoundError("Could not find hooks directory in package")


def register_hook_in_settings() -> bool:
    """Register the permission hook in Claude's settings.json.

    Returns True if settings were updated, False if already configured.

    Claude Code hook format:
    {
      "hooks": {
        "PermissionRequest": [
          {
            "matcher": ".*",
            "hooks": [
              {"type": "command", "command": "~/.claude/hooks/agentwire-permission.sh"}
            ]
          }
        ]
      }
    }
    """
    settings_file = Path.home() / ".claude" / "settings.json"
    # Use ~ for portability
    hook_command = "~/.claude/hooks/agentwire-permission.sh"

    # Load existing settings or create new
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    # Ensure hooks structure exists
    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PermissionRequest" not in settings["hooks"]:
        settings["hooks"]["PermissionRequest"] = []

    # Check if already registered (check nested hooks array)
    for entry in settings["hooks"]["PermissionRequest"]:
        if "hooks" in entry:
            for h in entry["hooks"]:
                if h.get("command") == hook_command:
                    return False  # Already registered

    # Add hook with correct Claude Code format
    hook_entry = {
        "matcher": ".*",
        "hooks": [
            {"type": "command", "command": hook_command}
        ]
    }
    settings["hooks"]["PermissionRequest"].append(hook_entry)

    # Write back
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(settings, indent=2))

    return True


def install_permission_hook(force: bool = False, copy: bool = False) -> bool:
    """Install the permission hook for Claude Code integration.

    Returns True if hook was installed/updated, False if skipped.
    """
    hook_name = "agentwire-permission.sh"

    try:
        hooks_source = get_hooks_source()
    except FileNotFoundError:
        print("  Warning: hooks directory not found, skipping hook installation")
        return False

    source_hook = hooks_source / hook_name
    if not source_hook.exists():
        print(f"  Warning: {hook_name} not found in package, skipping hook installation")
        return False

    # Create ~/.claude/hooks if it doesn't exist
    CLAUDE_HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    target_hook = CLAUDE_HOOKS_DIR / hook_name

    # Check if already installed
    file_updated = False
    if target_hook.exists():
        if target_hook.is_symlink():
            current_target = target_hook.resolve()
            if current_target == source_hook.resolve() and not force:
                file_updated = False  # File already correctly installed
            else:
                target_hook.unlink()
                file_updated = True
        elif not force:
            print(f"  Hook already exists at {target_hook}")
            file_updated = False
        else:
            target_hook.unlink()
            file_updated = True
    else:
        file_updated = True

    # Create symlink (preferred) or copy if needed
    if file_updated or not target_hook.exists():
        if copy:
            shutil.copy2(source_hook, target_hook)
        else:
            target_hook.symlink_to(source_hook)
        # Make executable
        target_hook.chmod(0o755)

    # Register in settings.json
    settings_updated = register_hook_in_settings()

    return file_updated or settings_updated


def cmd_skills_install(args) -> int:
    """Install Claude Code skills for AgentWire integration."""
    target_dir = CLAUDE_SKILLS_DIR / "agentwire"

    try:
        source_dir = get_skills_source()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Create ~/.claude/skills if it doesn't exist
    CLAUDE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # Check if already installed
    skills_already_installed = False
    if target_dir.exists():
        if target_dir.is_symlink():
            current_target = target_dir.resolve()
            if current_target == source_dir.resolve():
                print(f"Skills already installed (symlink to {source_dir})")
                skills_already_installed = True
            else:
                print(f"Existing symlink points to {current_target}")
        else:
            print(f"Skills directory already exists at {target_dir}")

        if not skills_already_installed:
            if not args.force:
                print("Use --force to overwrite")
                return 1

            # Remove existing
            if target_dir.is_symlink():
                target_dir.unlink()
            else:
                shutil.rmtree(target_dir)

    # Create symlink (preferred) or copy - unless already installed
    if not skills_already_installed:
        if args.copy:
            shutil.copytree(source_dir, target_dir)
            print(f"Copied skills to {target_dir}")
        else:
            target_dir.symlink_to(source_dir)
            print(f"Linked skills: {target_dir} -> {source_dir}")

    # Install permission hook
    hook_installed = install_permission_hook(force=args.force, copy=args.copy)
    if hook_installed:
        print(f"Installed permission hook to {CLAUDE_HOOKS_DIR / 'agentwire-permission.sh'}")

    print("\nClaude Code skills installed. Available commands:")
    print("  /sessions, /send, /output, /spawn, /new, /kill, /status, /jump")
    if hook_installed:
        print("\nPermission hook installed for normal session support.")
    return 0


def unregister_hook_from_settings() -> bool:
    """Remove the permission hook from Claude's settings.json.

    Returns True if settings were updated, False if not found.
    """
    settings_file = Path.home() / ".claude" / "settings.json"
    hook_command = "~/.claude/hooks/agentwire-permission.sh"

    if not settings_file.exists():
        return False

    try:
        settings = json.loads(settings_file.read_text())
    except json.JSONDecodeError:
        return False

    if "hooks" not in settings or "PermissionRequest" not in settings["hooks"]:
        return False

    # Filter out entries containing our hook
    original_len = len(settings["hooks"]["PermissionRequest"])
    new_entries = []
    for entry in settings["hooks"]["PermissionRequest"]:
        if "hooks" in entry:
            # Check if any hook in this entry matches ours
            has_our_hook = any(h.get("command") == hook_command for h in entry["hooks"])
            if not has_our_hook:
                new_entries.append(entry)
        else:
            new_entries.append(entry)

    settings["hooks"]["PermissionRequest"] = new_entries

    if len(settings["hooks"]["PermissionRequest"]) == original_len:
        return False  # Hook wasn't registered

    # Clean up empty structures
    if not settings["hooks"]["PermissionRequest"]:
        del settings["hooks"]["PermissionRequest"]
    if not settings["hooks"]:
        del settings["hooks"]

    # Write back
    settings_file.write_text(json.dumps(settings, indent=2))
    return True


def is_hook_registered() -> bool:
    """Check if the permission hook is registered in Claude's settings.json."""
    settings_file = Path.home() / ".claude" / "settings.json"
    hook_command = "~/.claude/hooks/agentwire-permission.sh"

    if not settings_file.exists():
        return False

    try:
        settings = json.loads(settings_file.read_text())
    except json.JSONDecodeError:
        return False

    if "hooks" not in settings or "PermissionRequest" not in settings["hooks"]:
        return False

    # Check nested hooks array for our command
    for entry in settings["hooks"]["PermissionRequest"]:
        if "hooks" in entry:
            for h in entry["hooks"]:
                if h.get("command") == hook_command:
                    return True
    return False


def cmd_skills_uninstall(args) -> int:
    """Uninstall Claude Code skills."""
    target_dir = CLAUDE_SKILLS_DIR / "agentwire"
    hook_file = CLAUDE_HOOKS_DIR / "agentwire-permission.sh"

    skills_removed = False
    hook_removed = False

    if target_dir.exists():
        if target_dir.is_symlink():
            target_dir.unlink()
            print(f"Removed symlink: {target_dir}")
        else:
            shutil.rmtree(target_dir)
            print(f"Removed directory: {target_dir}")
        skills_removed = True

    if hook_file.exists():
        hook_file.unlink()
        print(f"Removed hook: {hook_file}")
        hook_removed = True

    # Also unregister from settings.json
    if unregister_hook_from_settings():
        print("Unregistered hook from Claude settings.json")

    if not skills_removed and not hook_removed:
        print("Skills and hooks not installed")

    return 0


def cmd_skills_status(args) -> int:
    """Check Claude Code skills installation status."""
    target_dir = CLAUDE_SKILLS_DIR / "agentwire"
    hook_file = CLAUDE_HOOKS_DIR / "agentwire-permission.sh"

    skills_installed = target_dir.exists()
    hook_installed = hook_file.exists()

    if not skills_installed:
        print("Skills: not installed")
        print(f"  Run 'agentwire skills install' to set up Claude Code integration")
    else:
        if target_dir.is_symlink():
            source = target_dir.resolve()
            print(f"Skills: installed (symlink)")
            print(f"  Location: {target_dir} -> {source}")
        else:
            print(f"Skills: installed (copy)")
            print(f"  Location: {target_dir}")

        # List available skills
        skill_files = list(target_dir.glob("*.md"))
        skill_files = [f for f in skill_files if f.name != "SKILL.md"]
        if skill_files:
            print(f"  Commands: {', '.join('/' + f.stem for f in sorted(skill_files))}")

    print()
    hook_registered = is_hook_registered()
    if hook_installed:
        if hook_file.is_symlink():
            source = hook_file.resolve()
            print(f"Permission hook: installed (symlink)")
            print(f"  Location: {hook_file} -> {source}")
        else:
            print(f"Permission hook: installed (copy)")
            print(f"  Location: {hook_file}")
        if hook_registered:
            print(f"  Registered: yes (in ~/.claude/settings.json)")
        else:
            print(f"  Registered: NO - run 'agentwire skills install --force' to fix")
    else:
        print("Permission hook: not installed")
        print("  (Required for normal session permission prompts)")

    return 0 if skills_installed else 1


# === Tunnel Commands ===


def cmd_tunnels_up(args) -> int:
    """Create all required tunnels."""
    from .network import NetworkContext
    from .tunnels import TunnelManager

    ctx = NetworkContext.from_config()
    manager = TunnelManager()
    required = ctx.get_required_tunnels()

    if not required:
        print("No tunnels required for this machine's configuration.")
        print("(All services run locally or no remote services configured)")
        return 0

    print("Creating tunnels for this machine...\n")

    all_success = True
    for i, spec in enumerate(required, 1):
        # Get service name for display
        service_name = _get_service_for_tunnel(ctx, spec)

        print(f"[{i}/{len(required)}] {service_name} (localhost:{spec.local_port} -> {spec.remote_machine}:{spec.remote_port})")

        status = manager.create_tunnel(spec, ctx)

        if status.status == "up":
            if status.error:
                # Tunnel up but service not responding
                print(f"      ! Tunnel created (PID {status.pid})")
                print(f"      ! Warning: {status.error}")
            else:
                print(f"      + Tunnel created (PID {status.pid})")
        else:
            all_success = False
            print(f"      x Failed: {status.error}")
            _print_tunnel_help(spec, status.error)

        print()

    if all_success:
        print("All tunnels up. Services should be reachable.")
    else:
        print("Some tunnels failed. Check errors above.")
        return 1

    return 0


def cmd_tunnels_down(args) -> int:
    """Tear down all tunnels."""
    from .tunnels import TunnelManager

    manager = TunnelManager()
    count = manager.destroy_all_tunnels()

    if count == 0:
        print("No active tunnels to tear down.")
    else:
        print(f"Killed {count} tunnel(s).")

    return 0


def cmd_tunnels_status(args) -> int:
    """Show tunnel health."""
    from .network import NetworkContext
    from .tunnels import TunnelManager

    ctx = NetworkContext.from_config()
    manager = TunnelManager()

    # Get both required and active tunnels
    required = ctx.get_required_tunnels()
    active = manager.list_tunnels()

    print("AgentWire Tunnels")
    print("-" * 55)

    if not required and not active:
        print("\nNo tunnels configured or active.")
        print("(All services run locally or no remote services configured)")
        return 0

    # Show required tunnels
    for spec in required:
        service_name = _get_service_for_tunnel(ctx, spec)

        print(f"\n{service_name} (localhost:{spec.local_port} -> {spec.remote_machine}:{spec.remote_port})")

        status = manager.check_tunnel(spec)

        if status.status == "up":
            print(f"  Status: + UP (PID {status.pid})")
        elif status.status == "down":
            print(f"  Status: - DOWN")
        else:
            print(f"  Status: x ERROR")
            if status.error:
                print(f"  Error: {status.error}")

    # Show any orphaned tunnels (active but not required)
    required_ids = {s.id for s in required}
    orphaned = [t for t in active if t.spec.id not in required_ids]
    if orphaned:
        print("\n" + "-" * 55)
        print("\nOrphaned tunnels (active but no longer required):")
        for t in orphaned:
            print(f"  localhost:{t.spec.local_port} -> {t.spec.remote_machine}:{t.spec.remote_port}")
            print(f"    PID: {t.pid}, Status: {t.status}")

    print("\n" + "-" * 55)

    # Show next steps
    down_tunnels = [s for s in required if manager.check_tunnel(s).status != "up"]
    if down_tunnels:
        print("To create missing tunnels: agentwire tunnels up")

    return 0


def cmd_tunnels_check(args) -> int:
    """Verify tunnels are working with health checks."""
    from .network import NetworkContext
    from .tunnels import TunnelManager, test_service_health

    ctx = NetworkContext.from_config()
    manager = TunnelManager()
    required = ctx.get_required_tunnels()

    if not required:
        print("No tunnels required for this machine.")
        return 0

    print("Checking tunnel health...\n")

    all_healthy = True
    for spec in required:
        service_name = _get_service_for_tunnel(ctx, spec)
        status = manager.check_tunnel(spec)

        if status.status == "up":
            # Also test the actual service through the tunnel
            url = f"http://localhost:{spec.local_port}/health"
            healthy, err = test_service_health(url, timeout=3)

            if healthy:
                print(f"+ {service_name}: healthy")
            else:
                print(f"! {service_name}: tunnel up but service not responding")
                if err:
                    print(f"  {err}")
                all_healthy = False
        elif status.status == "down":
            print(f"x {service_name}: down")
            all_healthy = False
        else:
            print(f"x {service_name}: error - {status.error}")
            all_healthy = False

    if all_healthy:
        print("\nAll tunnels healthy.")
        return 0
    else:
        print("\nSome tunnels need attention. Run: agentwire tunnels up")
        return 1


def _get_service_for_tunnel(ctx, spec) -> str:
    """Get human-readable service name for a tunnel spec."""
    # Check which service this tunnel is for
    for service_name in ["portal", "tts"]:
        service_config = getattr(ctx.config.services, service_name, None)
        if service_config and service_config.machine == spec.remote_machine and service_config.port == spec.remote_port:
            return f"Portal -> {service_name.upper()}" if service_name != "portal" else "Portal"

    return f"Tunnel to {spec.remote_machine}"


def _print_tunnel_help(spec, error: str) -> None:
    """Print helpful diagnostics for tunnel errors."""
    if not error:
        return

    error_lower = error.lower()

    print("\n      Possible causes:")

    if "port" in error_lower and "in use" in error_lower:
        print("        1. Another process is using this port")
        print("        2. A previous tunnel wasn't cleaned up")
        print(f"\n      To diagnose:")
        print(f"        lsof -i :{spec.local_port}    # Find process using port")
        print(f"        agentwire tunnels down        # Clean up stale tunnels")

    elif "permission denied" in error_lower:
        print("        1. SSH key not authorized on remote machine")
        print("        2. Wrong user configured")
        print(f"\n      To fix:")
        print(f"        ssh-copy-id {spec.remote_machine}")

    elif "host key" in error_lower:
        print("        1. Remote machine was reinstalled/changed")
        print("        2. Possible security issue (man-in-the-middle)")
        print(f"\n      If expected, fix with:")
        print(f"        ssh-keygen -R {spec.remote_machine}")

    elif "connection refused" in error_lower:
        print("        1. SSH server not running on remote")
        print("        2. Firewall blocking port 22")
        print(f"\n      To diagnose:")
        print(f"        ssh {spec.remote_machine} echo ok")

    elif "timed out" in error_lower or "no route" in error_lower:
        print("        1. Machine is powered off or unreachable")
        print("        2. Network connectivity issue")
        print(f"\n      To diagnose:")
        print(f"        ping {spec.remote_machine}")

    elif "not responding" in error_lower:
        print("        1. Remote service not started")
        print("        2. Remote service on wrong port")
        print(f"\n      To diagnose:")
        print(f"        ssh {spec.remote_machine} 'lsof -i :{spec.remote_port}'")


class VersionAction(argparse.Action):
    """Custom version action that checks Python version and pip environment."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        # Print version
        print(f"agentwire {__version__}")
        print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

        # Check version compatibility
        version_ok = check_python_version()
        env_ok = check_pip_environment()

        if version_ok and env_ok:
            print("\n✓ System is ready for AgentWire")
        else:
            print("\n⚠️  Please resolve the issues above before installing/running AgentWire")

        parser.exit()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="agentwire",
        description="Multi-session voice web interface for AI coding agents.",
    )
    parser.add_argument(
        "--version",
        action=VersionAction,
        help="Show version and check system compatibility",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # === init command ===
    init_parser = subparsers.add_parser("init", help="Interactive setup wizard")
    init_parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: skip agentwire setup at end"
    )
    init_parser.set_defaults(func=cmd_init)

    # === portal command group ===
    portal_parser = subparsers.add_parser("portal", help="Manage the web portal")
    portal_subparsers = portal_parser.add_subparsers(dest="portal_command")

    # portal start
    portal_start = portal_subparsers.add_parser(
        "start", help="Start portal in tmux session"
    )
    portal_start.add_argument("--config", type=Path, help="Config file path")
    portal_start.add_argument("--port", type=int, help="Override port")
    portal_start.add_argument("--host", type=str, help="Override host")
    portal_start.add_argument("--no-tts", action="store_true", help="Disable TTS")
    portal_start.add_argument("--no-stt", action="store_true", help="Disable STT")
    portal_start.add_argument("--dev", action="store_true",
                              help="Run from source (uv run) - picks up code changes")
    portal_start.set_defaults(func=cmd_portal_start)

    # portal serve (run in foreground)
    portal_serve = portal_subparsers.add_parser(
        "serve", help="Run portal in foreground"
    )
    portal_serve.add_argument("--config", type=Path, help="Config file path")
    portal_serve.add_argument("--port", type=int, help="Override port")
    portal_serve.add_argument("--host", type=str, help="Override host")
    portal_serve.add_argument("--no-tts", action="store_true", help="Disable TTS")
    portal_serve.add_argument("--no-stt", action="store_true", help="Disable STT")
    portal_serve.set_defaults(func=cmd_portal_serve)

    # portal stop
    portal_stop = portal_subparsers.add_parser("stop", help="Stop the portal")
    portal_stop.set_defaults(func=cmd_portal_stop)

    # portal status
    portal_status = portal_subparsers.add_parser("status", help="Check portal status")
    portal_status.set_defaults(func=cmd_portal_status)

    # portal restart
    portal_restart = portal_subparsers.add_parser("restart", help="Restart the portal (stop + start)")
    portal_restart.add_argument("--config", type=Path, help="Config file path")
    portal_restart.add_argument("--port", type=int, help="Override port")
    portal_restart.add_argument("--host", type=str, help="Override host")
    portal_restart.add_argument("--no-tts", action="store_true", help="Disable TTS")
    portal_restart.add_argument("--no-stt", action="store_true", help="Disable STT")
    portal_restart.add_argument("--dev", action="store_true",
                                help="Run from source (uv run) - picks up code changes")
    portal_restart.set_defaults(func=cmd_portal_restart)

    # portal generate-certs
    portal_certs = portal_subparsers.add_parser(
        "generate-certs", help="Generate SSL certificates"
    )
    portal_certs.set_defaults(func=cmd_generate_certs)

    # === tts command group ===
    tts_parser = subparsers.add_parser("tts", help="Manage TTS server")
    tts_subparsers = tts_parser.add_subparsers(dest="tts_command")

    # tts start
    tts_start = tts_subparsers.add_parser("start", help="Start TTS server in tmux")
    tts_start.add_argument("--port", type=int, help="Server port (default: 8100)")
    tts_start.add_argument("--host", type=str, help="Server host (default: 0.0.0.0)")
    tts_start.set_defaults(func=cmd_tts_start)

    # tts serve (run in foreground)
    tts_serve = tts_subparsers.add_parser("serve", help="Run TTS server in foreground")
    tts_serve.add_argument("--port", type=int, help="Server port (default: 8100)")
    tts_serve.add_argument("--host", type=str, help="Server host (default: 0.0.0.0)")
    tts_serve.set_defaults(func=cmd_tts_serve)

    # tts stop
    tts_stop = tts_subparsers.add_parser("stop", help="Stop TTS server")
    tts_stop.set_defaults(func=cmd_tts_stop)

    # tts status
    tts_status = tts_subparsers.add_parser("status", help="Check TTS status")
    tts_status.set_defaults(func=cmd_tts_status)

    # === stt command group ===
    stt_parser = subparsers.add_parser("stt", help="Manage STT server (native Whisper)")
    stt_subparsers = stt_parser.add_subparsers(dest="stt_command")

    # stt start
    stt_start = stt_subparsers.add_parser("start", help="Start STT server in tmux")
    stt_start.add_argument("--port", type=int, help="Server port (default: 8100)")
    stt_start.add_argument("--host", type=str, help="Server host (default: 0.0.0.0)")
    stt_start.add_argument("--model", type=str, help="Whisper model (tiny/base/small/medium/large-v3)")
    stt_start.set_defaults(func=cmd_stt_start)

    # stt serve
    stt_serve = stt_subparsers.add_parser("serve", help="Run STT server in foreground")
    stt_serve.add_argument("--port", type=int, help="Server port (default: 8100)")
    stt_serve.add_argument("--host", type=str, help="Server host (default: 0.0.0.0)")
    stt_serve.add_argument("--model", type=str, help="Whisper model (tiny/base/small/medium/large-v3)")
    stt_serve.set_defaults(func=cmd_stt_serve)

    # stt stop
    stt_stop = stt_subparsers.add_parser("stop", help="Stop STT server")
    stt_stop.set_defaults(func=cmd_stt_stop)

    # stt status
    stt_status = stt_subparsers.add_parser("status", help="Check STT status")
    stt_status.set_defaults(func=cmd_stt_status)

    # === tunnels command group ===
    tunnels_parser = subparsers.add_parser("tunnels", help="Manage SSH tunnels for service routing")
    tunnels_subparsers = tunnels_parser.add_subparsers(dest="tunnels_command")

    # tunnels up
    tunnels_up = tunnels_subparsers.add_parser("up", help="Create all required tunnels")
    tunnels_up.set_defaults(func=cmd_tunnels_up)

    # tunnels down
    tunnels_down = tunnels_subparsers.add_parser("down", help="Tear down all tunnels")
    tunnels_down.set_defaults(func=cmd_tunnels_down)

    # tunnels status
    tunnels_status = tunnels_subparsers.add_parser("status", help="Show tunnel health")
    tunnels_status.set_defaults(func=cmd_tunnels_status)

    # tunnels check
    tunnels_check = tunnels_subparsers.add_parser("check", help="Verify tunnels are working")
    tunnels_check.set_defaults(func=cmd_tunnels_check)

    # === say command ===
    say_parser = subparsers.add_parser("say", help="Speak text via TTS")
    say_parser.add_argument("text", nargs="*", help="Text to speak")
    say_parser.add_argument("-v", "--voice", type=str, help="Voice name")
    say_parser.add_argument("-s", "--session", type=str, help="Session name (auto-detected from .agentwire.yml or tmux)")
    say_parser.add_argument("--exaggeration", type=float, help="Voice exaggeration (0-1)")
    say_parser.add_argument("--cfg", type=float, help="CFG weight (0-1)")
    say_parser.set_defaults(func=cmd_say)

    # === send command ===
    send_parser = subparsers.add_parser("send", help="Send prompt to a session or pane (adds Enter)")
    send_parser.add_argument("-s", "--session", help="Target session (supports session@machine)")
    send_parser.add_argument("--pane", type=int, help="Target pane index (auto-detects session)")
    send_parser.add_argument("prompt", nargs="*", help="Prompt to send")
    send_parser.add_argument("--json", action="store_true", help="Output as JSON")
    send_parser.set_defaults(func=cmd_send)

    # === send-keys command ===
    send_keys_parser = subparsers.add_parser(
        "send-keys", help="Send raw keys to a session (with pause between groups)"
    )
    send_keys_parser.add_argument("-s", "--session", required=True, help="Target session (supports session@machine)")
    send_keys_parser.add_argument("keys", nargs="*", help="Key groups to send (e.g., 'hello world' Enter)")
    send_keys_parser.set_defaults(func=cmd_send_keys)

    # === list command (top-level) ===
    list_parser = subparsers.add_parser("list", help="List panes (in tmux) or sessions")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.add_argument("--local", action="store_true", help="Only show local sessions")
    list_parser.add_argument("--remote", action="store_true", help="Only show remote sessions")
    list_parser.add_argument("--sessions", action="store_true", help="Show sessions instead of panes")
    list_parser.set_defaults(func=cmd_list)

    # === new command (top-level) ===
    new_parser = subparsers.add_parser("new", help="Create new Claude Code session")
    new_parser.add_argument("-s", "--session", required=True, help="Session name (project, project/branch, or project/branch@machine)")
    new_parser.add_argument("-p", "--path", help="Working directory (default: ~/projects/<name>)")
    new_parser.add_argument("-t", "--template", help="Apply session template (from ~/.agentwire/templates/)")
    new_parser.add_argument("-f", "--force", action="store_true", help="Replace existing session")
    # Session type flags (mutually exclusive)
    type_group = new_parser.add_mutually_exclusive_group()
    type_group.add_argument("--bare", action="store_true", help="No Claude, just tmux session")
    type_group.add_argument("--prompted", action="store_true", help="Claude with permission hooks (no bypass)")
    type_group.add_argument("--restricted", action="store_true", help="Claude restricted to say command only")
    # Roles
    new_parser.add_argument("--roles", help="Comma-separated list of roles (preserves existing config, defaults to agentwire for new projects)")
    new_parser.add_argument("--json", action="store_true", help="Output as JSON")
    new_parser.set_defaults(func=cmd_new)

    # === output command (top-level) ===
    output_parser = subparsers.add_parser("output", help="Read session or pane output")
    output_parser.add_argument("-s", "--session", help="Session name (supports session@machine)")
    output_parser.add_argument("--pane", type=int, help="Target pane index (auto-detects session)")
    output_parser.add_argument("-n", "--lines", type=int, default=50, help="Lines to show (default: 50)")
    output_parser.add_argument("--json", action="store_true", help="Output as JSON")
    output_parser.set_defaults(func=cmd_output)

    # === info command (top-level) ===
    info_parser = subparsers.add_parser("info", help="Get session information (cwd, panes, etc.)")
    info_parser.add_argument("-s", "--session", required=True, help="Session name (supports session@machine)")
    info_parser.add_argument("--json", action="store_true", default=True, help="Output as JSON (default)")
    info_parser.add_argument("--no-json", dest="json", action="store_false", help="Human-readable output")
    info_parser.set_defaults(func=cmd_info)

    # === kill command (top-level) ===
    kill_parser = subparsers.add_parser("kill", help="Kill a session or pane (clean shutdown)")
    kill_parser.add_argument("-s", "--session", help="Session name (supports session@machine)")
    kill_parser.add_argument("--pane", type=int, help="Target pane index (auto-detects session)")
    kill_parser.add_argument("--json", action="store_true", help="Output as JSON")
    kill_parser.set_defaults(func=cmd_kill)

    # === spawn command (top-level) ===
    spawn_parser = subparsers.add_parser("spawn", help="Spawn a worker pane in current session")
    spawn_parser.add_argument("-s", "--session", help="Target session (default: auto-detect)")
    spawn_parser.add_argument("--cwd", help="Working directory (default: current)")
    spawn_parser.add_argument("--branch", "-b", help="Create worktree on this branch for isolated commits")
    spawn_parser.add_argument("--roles", default="worker", help="Comma-separated roles (default: worker)")
    spawn_parser.add_argument("--json", action="store_true", help="Output as JSON")
    spawn_parser.set_defaults(func=cmd_spawn)

    # === split command (top-level) ===
    split_parser = subparsers.add_parser("split", help="Add terminal pane(s) with even vertical layout")
    split_parser.add_argument("-n", "--count", type=int, default=1, help="Number of panes to add (default: 1)")
    split_parser.add_argument("-s", "--session", help="Target session (default: auto-detect)")
    split_parser.add_argument("--cwd", help="Working directory (default: current)")
    split_parser.set_defaults(func=cmd_split)

    # === detach command (top-level) ===
    detach_parser = subparsers.add_parser("detach", help="Move a pane to its own session")
    detach_parser.add_argument("--pane", type=int, required=True, help="Pane index to detach")
    detach_parser.add_argument("-s", "--session", required=True, help="Target session name (created if doesn't exist)")
    detach_parser.add_argument("--source", help="Source session (default: auto-detect)")
    detach_parser.set_defaults(func=cmd_detach)

    # === jump command (top-level) ===
    jump_parser = subparsers.add_parser("jump", help="Jump to (focus) a specific pane")
    jump_parser.add_argument("-s", "--session", help="Target session (default: auto-detect)")
    jump_parser.add_argument("--pane", type=int, required=True, help="Pane index to focus")
    jump_parser.add_argument("--json", action="store_true", help="Output as JSON")
    jump_parser.set_defaults(func=cmd_jump)

    # === resize command (top-level) ===
    resize_parser = subparsers.add_parser("resize", help="Resize window to fit largest client")
    resize_parser.add_argument("-s", "--session", help="Target session (default: auto-detect)")
    resize_parser.add_argument("--json", action="store_true", help="Output as JSON")
    resize_parser.set_defaults(func=cmd_resize)

    # === recreate command (top-level) ===
    recreate_parser = subparsers.add_parser("recreate", help="Destroy and recreate session with fresh worktree")
    recreate_parser.add_argument("-s", "--session", required=True, help="Session name (project/branch or project/branch@machine)")
    # Session type flags (mutually exclusive)
    recreate_type_group = recreate_parser.add_mutually_exclusive_group()
    recreate_type_group.add_argument("--bare", action="store_true", help="No Claude, just tmux session")
    recreate_type_group.add_argument("--prompted", action="store_true", help="Claude with permission hooks (no bypass)")
    recreate_type_group.add_argument("--restricted", action="store_true", help="Claude restricted to say command only")
    recreate_parser.add_argument("--json", action="store_true", help="Output as JSON")
    recreate_parser.set_defaults(func=cmd_recreate)

    # === fork command (top-level) ===
    fork_parser = subparsers.add_parser("fork", help="Fork a session into a new worktree")
    fork_parser.add_argument("-s", "--source", required=True, help="Source session (project or project/branch)")
    fork_parser.add_argument("-t", "--target", required=True, help="Target session (must include branch: project/new-branch)")
    # Session type flags (mutually exclusive)
    fork_type_group = fork_parser.add_mutually_exclusive_group()
    fork_type_group.add_argument("--bare", action="store_true", help="No Claude, just tmux session")
    fork_type_group.add_argument("--prompted", action="store_true", help="Claude with permission hooks (no bypass)")
    fork_type_group.add_argument("--restricted", action="store_true", help="Claude restricted to say command only")
    fork_parser.add_argument("--json", action="store_true", help="Output as JSON")
    fork_parser.set_defaults(func=cmd_fork)

    # === dev command ===
    dev_parser = subparsers.add_parser(
        "dev", help="Start/attach to dev agentwire session"
    )
    dev_parser.set_defaults(func=cmd_dev)

    # === listen command group ===
    listen_parser = subparsers.add_parser("listen", help="Voice input recording")
    listen_parser.add_argument(
        "--session", "-s", type=str, default="agentwire",
        help="Target session (default: agentwire)"
    )
    listen_parser.add_argument(
        "--no-prompt", action="store_true",
        help="Don't prepend voice prompt hint"
    )
    listen_subparsers = listen_parser.add_subparsers(dest="listen_command")

    # listen start
    listen_start = listen_subparsers.add_parser("start", help="Start recording")
    listen_start.set_defaults(func=cmd_listen_start)

    # listen stop
    listen_stop = listen_subparsers.add_parser("stop", help="Stop and send")
    listen_stop.add_argument("--session", "-s", type=str, help="Target session")
    listen_stop.add_argument("--no-prompt", action="store_true")
    listen_stop.add_argument("--type", action="store_true", help="Type at cursor instead of sending to session")
    listen_stop.set_defaults(func=cmd_listen_stop)

    # listen cancel
    listen_cancel = listen_subparsers.add_parser("cancel", help="Cancel recording")
    listen_cancel.set_defaults(func=cmd_listen_cancel)

    # Default listen (no subcommand) = toggle
    listen_parser.set_defaults(func=cmd_listen_toggle)

    # === voiceclone command group ===
    voiceclone_parser = subparsers.add_parser(
        "voiceclone", help="Record and upload voice clones"
    )
    voiceclone_subparsers = voiceclone_parser.add_subparsers(dest="voiceclone_command")

    # voiceclone start
    voiceclone_start = voiceclone_subparsers.add_parser(
        "start", help="Start recording for voice clone"
    )
    voiceclone_start.set_defaults(func=cmd_voiceclone_start)

    # voiceclone stop <name>
    voiceclone_stop = voiceclone_subparsers.add_parser(
        "stop", help="Stop recording and upload as voice clone"
    )
    voiceclone_stop.add_argument("name", help="Name for the voice clone")
    voiceclone_stop.set_defaults(func=cmd_voiceclone_stop)

    # voiceclone cancel
    voiceclone_cancel = voiceclone_subparsers.add_parser(
        "cancel", help="Cancel current recording"
    )
    voiceclone_cancel.set_defaults(func=cmd_voiceclone_cancel)

    # voiceclone list
    voiceclone_list = voiceclone_subparsers.add_parser(
        "list", help="List available voices"
    )
    voiceclone_list.set_defaults(func=cmd_voiceclone_list)

    # voiceclone delete <name>
    voiceclone_delete = voiceclone_subparsers.add_parser(
        "delete", help="Delete a voice clone"
    )
    voiceclone_delete.add_argument("name", help="Name of voice to delete")
    voiceclone_delete.set_defaults(func=cmd_voiceclone_delete)

    # === machine command group ===
    machine_parser = subparsers.add_parser("machine", help="Manage remote machines")
    machine_subparsers = machine_parser.add_subparsers(dest="machine_command")

    # machine list
    machine_list = machine_subparsers.add_parser("list", help="List registered machines")
    machine_list.set_defaults(func=cmd_machine_list)

    # machine add <id>
    machine_add = machine_subparsers.add_parser(
        "add", help="Add a machine to the network"
    )
    machine_add.add_argument("machine_id", help="Machine ID (used in session names)")
    machine_add.add_argument("--host", help="SSH host (defaults to machine_id)")
    machine_add.add_argument("--user", help="SSH user")
    machine_add.add_argument("--projects-dir", dest="projects_dir", help="Projects directory on remote")
    machine_add.set_defaults(func=cmd_machine_add)

    # machine remove <id>
    machine_remove = machine_subparsers.add_parser(
        "remove", help="Remove a machine from the network"
    )
    machine_remove.add_argument("machine_id", help="Machine ID to remove")
    machine_remove.set_defaults(func=cmd_machine_remove)

    # === history command group ===
    history_parser = subparsers.add_parser("history", help="Claude Code session history")
    history_subparsers = history_parser.add_subparsers(dest="history_command")

    # history list
    history_list = history_subparsers.add_parser("list", help="List conversation history")
    history_list.add_argument("--project", "-p", help="Project path (defaults to cwd)")
    history_list.add_argument("--machine", "-m", default="local", help="Machine ID")
    history_list.add_argument("--limit", "-n", type=int, default=20, help="Max results")
    history_list.add_argument("--json", action="store_true", help="JSON output")
    history_list.set_defaults(func=cmd_history_list)

    # history show <session_id>
    history_show = history_subparsers.add_parser("show", help="Show session details")
    history_show.add_argument("session_id", help="Session ID to show")
    history_show.add_argument("--machine", "-m", default="local", help="Machine ID")
    history_show.add_argument("--json", action="store_true", help="JSON output")
    history_show.set_defaults(func=cmd_history_show)

    # history resume <session_id>
    history_resume = history_subparsers.add_parser("resume", help="Resume a session (always forks)")
    history_resume.add_argument("session_id", help="Session ID to resume")
    history_resume.add_argument("--name", "-n", help="New tmux session name")
    history_resume.add_argument("--machine", "-m", default="local", help="Machine ID")
    history_resume.add_argument("--project", "-p", required=True, help="Project path")
    history_resume.add_argument("--json", action="store_true", help="JSON output")
    history_resume.set_defaults(func=cmd_history_resume)

    # === template command group ===
    template_parser = subparsers.add_parser(
        "template", help="Manage session templates"
    )
    template_subparsers = template_parser.add_subparsers(dest="template_command")

    # template list
    template_list = template_subparsers.add_parser("list", help="List available templates")
    template_list.add_argument("--json", action="store_true", help="Output as JSON")
    template_list.set_defaults(func=cmd_template_list)

    # template show <name>
    template_show = template_subparsers.add_parser("show", help="Show template details")
    template_show.add_argument("name", help="Template name")
    template_show.add_argument("--json", action="store_true", help="Output as JSON")
    template_show.set_defaults(func=cmd_template_show)

    # template create <name>
    template_create = template_subparsers.add_parser("create", help="Create a new template")
    template_create.add_argument("name", help="Template name")
    template_create.add_argument("--description", help="Template description")
    template_create.add_argument("--voice", help="TTS voice")
    template_create.add_argument("--roles", help="Comma-separated list of roles to apply")
    template_create.add_argument("--project", help="Default project path")
    template_create.add_argument("--prompt", help="Initial prompt text")
    template_create.add_argument("--no-bypass", action="store_true", help="Use normal permission mode")
    template_create.add_argument("--restricted", action="store_true", help="Use restricted mode")
    template_create.add_argument("-f", "--force", action="store_true", help="Overwrite existing template")
    template_create.add_argument("--json", action="store_true", help="Non-interactive JSON mode")
    template_create.set_defaults(func=cmd_template_create)

    # template delete <name>
    template_delete = template_subparsers.add_parser("delete", help="Delete a template")
    template_delete.add_argument("name", help="Template name")
    template_delete.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    template_delete.add_argument("--json", action="store_true", help="Output as JSON")
    template_delete.set_defaults(func=cmd_template_delete)

    # template install-samples
    template_install_samples = template_subparsers.add_parser(
        "install-samples", help="Install sample templates"
    )
    template_install_samples.add_argument("-f", "--force", action="store_true", help="Overwrite existing templates")
    template_install_samples.add_argument("--json", action="store_true", help="Output as JSON")
    template_install_samples.set_defaults(func=cmd_template_install_samples)

    # === roles command group ===
    roles_parser = subparsers.add_parser(
        "roles", help="Manage composable roles"
    )
    roles_subparsers = roles_parser.add_subparsers(dest="roles_command")

    # roles list
    roles_list = roles_subparsers.add_parser("list", help="List available roles")
    roles_list.add_argument("--json", action="store_true", help="Output as JSON")
    roles_list.set_defaults(func=cmd_roles_list)

    # roles show <name>
    roles_show = roles_subparsers.add_parser("show", help="Show role details")
    roles_show.add_argument("name", help="Role name")
    roles_show.add_argument("--json", action="store_true", help="Output as JSON")
    roles_show.set_defaults(func=cmd_roles_show)

    # === projects command group ===
    projects_parser = subparsers.add_parser(
        "projects", help="Discover and list projects"
    )
    projects_subparsers = projects_parser.add_subparsers(dest="projects_command")

    # projects list
    projects_list = projects_subparsers.add_parser("list", help="List discovered projects")
    projects_list.add_argument("--machine", help="Filter by machine ID (e.g., 'local', 'mac-studio')")
    projects_list.add_argument("--json", action="store_true", help="Output as JSON")
    projects_list.set_defaults(func=cmd_projects_list)

    # === skills command group ===
    skills_parser = subparsers.add_parser(
        "skills", help="Manage Claude Code skills integration"
    )
    skills_subparsers = skills_parser.add_subparsers(dest="skills_command")

    # skills install
    skills_install = skills_subparsers.add_parser(
        "install", help="Install Claude Code skills for AgentWire"
    )
    skills_install.add_argument(
        "--force", "-f", action="store_true", help="Overwrite existing installation"
    )
    skills_install.add_argument(
        "--copy", action="store_true", help="Copy files instead of symlinking"
    )
    skills_install.set_defaults(func=cmd_skills_install)

    # skills uninstall
    skills_uninstall = skills_subparsers.add_parser(
        "uninstall", help="Remove Claude Code skills"
    )
    skills_uninstall.set_defaults(func=cmd_skills_uninstall)

    # skills status
    skills_status = skills_subparsers.add_parser(
        "status", help="Check skills installation status"
    )
    skills_status.set_defaults(func=cmd_skills_status)

    # === network command group ===
    network_parser = subparsers.add_parser(
        "network", help="Network diagnostics and status"
    )
    network_subparsers = network_parser.add_subparsers(dest="network_command")

    # network status
    network_status = network_subparsers.add_parser(
        "status", help="Show complete network health at a glance"
    )
    network_status.set_defaults(func=cmd_network_status)

    # === safety command group ===
    safety_parser = subparsers.add_parser(
        "safety", help="Damage control security commands"
    )
    safety_subparsers = safety_parser.add_subparsers(dest="safety_command")

    # safety check <command>
    safety_check = safety_subparsers.add_parser(
        "check", help="Test if a command would be blocked/allowed"
    )
    safety_check.add_argument("command", help="Command to test")
    safety_check.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    safety_check.set_defaults(func=cmd_safety_check)

    # safety status
    safety_status = safety_subparsers.add_parser(
        "status", help="Show safety status and pattern counts"
    )
    safety_status.set_defaults(func=cmd_safety_status)

    # safety logs
    safety_logs = safety_subparsers.add_parser(
        "logs", help="Query audit logs"
    )
    safety_logs.add_argument(
        "--tail", "-n", type=int, help="Show last N entries"
    )
    safety_logs.add_argument(
        "--session", "-s", help="Filter by session ID"
    )
    safety_logs.add_argument(
        "--today", action="store_true", help="Show only today's logs"
    )
    safety_logs.add_argument(
        "--pattern", "-p", help="Filter by pattern (regex or substring)"
    )
    safety_logs.set_defaults(func=cmd_safety_logs)

    # safety install
    safety_install = safety_subparsers.add_parser(
        "install", help="Install damage control hooks (interactive)"
    )
    safety_install.set_defaults(func=cmd_safety_install)

    # === doctor command (top-level) ===
    doctor_parser = subparsers.add_parser(
        "doctor", help="Auto-diagnose and fix common issues"
    )
    doctor_parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without making changes"
    )
    doctor_parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Auto-confirm all fixes without prompting"
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    # === generate-certs (top-level shortcut) ===
    certs_parser = subparsers.add_parser(
        "generate-certs", help="Generate SSL certificates"
    )
    certs_parser.set_defaults(func=cmd_generate_certs)

    # === rebuild command ===
    rebuild_parser = subparsers.add_parser(
        "rebuild", help="Clear uv cache and reinstall from source (for development)"
    )
    rebuild_parser.set_defaults(func=cmd_rebuild)

    # === uninstall command ===
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Clear uv cache and uninstall the tool"
    )
    uninstall_parser.set_defaults(func=cmd_uninstall)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "portal" and getattr(args, "portal_command", None) is None:
        portal_parser.print_help()
        return 0

    if args.command == "tts" and getattr(args, "tts_command", None) is None:
        tts_parser.print_help()
        return 0

    if args.command == "stt" and getattr(args, "stt_command", None) is None:
        stt_parser.print_help()
        return 0

    if args.command == "tunnels" and getattr(args, "tunnels_command", None) is None:
        tunnels_parser.print_help()
        return 0

    if args.command == "machine" and getattr(args, "machine_command", None) is None:
        machine_parser.print_help()
        return 0

    if args.command == "history" and getattr(args, "history_command", None) is None:
        history_parser.print_help()
        return 0

    if args.command == "skills" and getattr(args, "skills_command", None) is None:
        skills_parser.print_help()
        return 0

    if args.command == "projects" and getattr(args, "projects_command", None) is None:
        projects_parser.print_help()
        return 0

    if args.command == "safety" and getattr(args, "safety_command", None) is None:
        safety_parser.print_help()
        return 0

    if args.command == "network" and getattr(args, "network_command", None) is None:
        network_parser.print_help()
        return 0

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
