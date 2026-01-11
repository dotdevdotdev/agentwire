"""Interactive onboarding wizard for AgentWire setup."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".agentwire"

# ANSI colors
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"
DIM = "\033[2m"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}{text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{YELLOW}!{RESET} {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{DIM}{text}{RESET}")


def prompt(question: str, default: Optional[str] = None) -> str:
    """Prompt user for input with optional default."""
    if default:
        result = input(f"{question} [{default}]: ").strip()
        return result if result else default
    return input(f"{question}: ").strip()


def prompt_choice(question: str, options: list[tuple[str, str]], default: int = 1) -> str:
    """Prompt user to choose from options. Returns the option key."""
    print(question)
    print()
    for i, (key, description) in enumerate(options, 1):
        marker = f"{GREEN}→{RESET}" if i == default else " "
        print(f"  {marker} {i}. {description}")
    print()

    while True:
        choice = input(f"Choose [1-{len(options)}] (default: {default}): ").strip()
        if not choice:
            return options[default - 1][0]
        try:
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        except ValueError:
            pass
        print_error(f"Please enter a number between 1 and {len(options)}")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {hint}: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print_error("Please answer 'y' or 'n'")


def detect_platform() -> str:
    """Detect the current platform."""
    if sys.platform == "darwin":
        return "macos"
    elif sys.platform.startswith("linux"):
        # Check for WSL
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return "wsl"
        except FileNotFoundError:
            pass
        return "linux"
    return "unknown"


def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(cmd) is not None


def test_ssh_connection(host: str, user: str, timeout: int = 5) -> bool:
    """Test SSH connection to a host."""
    try:
        result = subprocess.run(
            ["ssh", "-o", f"ConnectTimeout={timeout}", "-o", "BatchMode=yes",
             f"{user}@{host}", "echo ok"],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def get_local_machine_info() -> tuple[str, str]:
    """Get this machine's ID and IP for remote config.

    Returns:
        Tuple of (hostname, local_ip)
    """
    import socket

    hostname = socket.gethostname().lower()
    # Try to get local IP (not localhost)
    try:
        # Connect to external host to find our LAN IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    return hostname, local_ip


def detect_remote_python_version(host: str, user: str) -> Optional[tuple[int, int, int]]:
    """Detect Python version on remote machine via SSH.

    Returns:
        Tuple of (major, minor, patch) or None if failed
    """
    try:
        ssh_target = f"{user}@{host}"
        result = subprocess.run(
            ["ssh", ssh_target, "python3 --version"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            # Parse "Python 3.10.12"
            version_str = result.stdout.strip().split()[1]
            parts = version_str.split(".")
            return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, IndexError):
        pass

    return None


def check_remote_externally_managed(host: str, user: str) -> bool:
    """Check if remote Python is externally managed (Ubuntu 24.04+).

    Returns:
        True if EXTERNALLY-MANAGED marker file exists
    """
    try:
        ssh_target = f"{user}@{host}"
        result = subprocess.run(
            ["ssh", ssh_target, "python3 -c 'import sys; print(sys.prefix)'"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            prefix = result.stdout.strip()
            check_result = subprocess.run(
                ["ssh", ssh_target, f"test -f {prefix}/EXTERNALLY-MANAGED && echo yes || echo no"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return check_result.stdout.strip() == "yes"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    return False


def setup_remote_machine(
    host: str,
    user: str,
    projects_dir: str,
    portal_machine_id: str,
    portal_host: str,
    portal_user: str,
) -> bool:
    """Set up AgentWire on a remote machine: install package, configure, verify.

    Steps:
    1. Check Python version (must be >= 3.10)
    2. Handle externally-managed environments (recommend venv for Ubuntu)
    3. Install agentwire package
    4. Create config files
    5. Install skills/scripts
    6. Verify say command works

    Returns:
        True if successful
    """
    ssh_target = f"{user}@{host}"

    # Step 1: Check Python version
    print(f"\nChecking Python version on {ssh_target}...")
    python_version = detect_remote_python_version(host, user)

    if python_version is None:
        print_error("Could not detect Python version")
        return False

    major, minor, patch = python_version
    print_success(f"Python {major}.{minor}.{patch}")

    if major < 3 or (major == 3 and minor < 10):
        print_error(f"Python {major}.{minor} is too old. AgentWire requires Python >=3.10")
        print()
        print("Upgrade instructions:")
        print("  Ubuntu: sudo apt update && sudo apt install python3.12")
        print("  macOS:  pyenv install 3.12.0 && pyenv global 3.12.0")
        return False

    # Step 2: Check for externally-managed environment
    print("Checking for externally-managed Python...")
    is_externally_managed = check_remote_externally_managed(host, user)

    install_command = "pip3 install git+https://github.com/dotdevdotdev/agentwire.git"

    if is_externally_managed:
        print_warning("Externally-managed Python environment detected (Ubuntu 24.04+)")
        print()
        print(f"{BOLD}Recommended approach: Use venv{RESET}")
        print()

        if prompt_yes_no("Create venv at ~/.agentwire-venv?", default=True):
            print("Creating virtual environment...")
            try:
                # Create venv
                subprocess.run(
                    ["ssh", ssh_target, "python3 -m venv ~/.agentwire-venv"],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                print_success("Created ~/.agentwire-venv")

                # Add to bashrc
                bashrc_line = "source ~/.agentwire-venv/bin/activate"
                subprocess.run(
                    ["ssh", ssh_target, f"grep -qxF '{bashrc_line}' ~/.bashrc || echo '{bashrc_line}' >> ~/.bashrc"],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
                print_success("Added activation to ~/.bashrc")

                # Update install command to use venv
                install_command = f"~/.agentwire-venv/bin/pip install git+https://github.com/dotdevdotdev/agentwire.git"

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print_error(f"Failed to create venv: {e}")
                print()
                print("Alternative: use --break-system-packages (not recommended)")
                if prompt_yes_no("Try with --break-system-packages?", default=False):
                    install_command = "pip3 install --break-system-packages git+https://github.com/dotdevdotdev/agentwire.git"
                else:
                    return False
        else:
            print()
            if prompt_yes_no("Use --break-system-packages instead?", default=False):
                install_command = "pip3 install --break-system-packages git+https://github.com/dotdevdotdev/agentwire.git"
            else:
                print_info("Setup cancelled. You can install manually later.")
                return False

    # Step 3: Install agentwire package
    print(f"\nInstalling AgentWire on {ssh_target}...")
    print_info(f"Command: {install_command}")
    print()

    try:
        result = subprocess.run(
            ["ssh", ssh_target, install_command],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for git clone + install
        )

        if result.returncode != 0:
            print_error(f"Installation failed:")
            print(result.stderr)
            return False

        print_success("AgentWire installed successfully")

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print_error(f"Installation failed: {e}")
        return False

    # Step 4: Create config files
    print("\nCreating configuration files...")
    if not setup_remote_machine_config(host, user, projects_dir, portal_machine_id, portal_host, portal_user):
        return False

    # Step 5: Install skills and scripts
    print("\nInstalling skills and scripts...")

    # Determine agentwire command path (venv or system)
    if is_externally_managed and "~/.agentwire-venv" in install_command:
        agentwire_cmd = "~/.agentwire-venv/bin/agentwire"
    else:
        agentwire_cmd = "agentwire"

    try:
        result = subprocess.run(
            ["ssh", ssh_target, f"{agentwire_cmd} skills install"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print_success("Skills and scripts installed")
        else:
            print_warning(f"Skills install had issues: {result.stderr[:200]}")

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print_warning("Could not install skills automatically")

    # Step 6: Verify say command works
    print("\nVerifying say command connectivity...")

    try:
        # Try to run say with test message (will fail if portal not running, but that's OK)
        result = subprocess.run(
            ["ssh", ssh_target, f"{agentwire_cmd} say --room test 'Setup complete'"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # We don't expect this to fully work yet (portal may not be running),
        # but the command should exist
        if "command not found" in result.stderr:
            print_warning("say command not found")
        else:
            print_success("say command is available")

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print_info("Could not verify say command (portal may not be running yet)")

    print()
    print_success(f"Remote setup complete for {ssh_target}")
    return True


def create_reverse_tunnel(portal_port: int, machine: dict) -> bool:
    """Create a reverse SSH tunnel for a remote machine to access the portal.

    Creates: ssh -R 8765:localhost:8765 -N -f user@host

    Args:
        portal_port: Local portal port to tunnel (usually 8765)
        machine: Machine dict with 'id', 'host', 'user'

    Returns:
        True if tunnel created successfully
    """
    machine_id = machine.get("id", "unknown")
    host = machine.get("host", "")
    user = machine.get("user", "")

    ssh_target = f"{user}@{host}" if user else host

    print(f"\nCreating reverse tunnel for {machine_id} ({ssh_target})...")

    # Build SSH command
    # -R remote_port:localhost:local_port - Reverse port forwarding
    # -N - Don't execute remote command
    # -f - Go to background
    # -o ExitOnForwardFailure=yes - Exit if port forward fails
    # -o ServerAliveInterval=60 - Keep connection alive
    # -o ServerAliveCountMax=3 - Max missed keepalives
    cmd = [
        "ssh",
        "-R", f"{portal_port}:localhost:{portal_port}",
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
            print_error(f"Tunnel creation failed: {result.stderr.strip()}")
            return False

        print_success(f"Reverse tunnel created: {ssh_target} port {portal_port} → localhost:{portal_port}")

        # Verify tunnel works
        print("Verifying tunnel...")
        verify_result = subprocess.run(
            ["ssh", ssh_target, f"curl -k -s https://localhost:{portal_port}/health"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if verify_result.returncode == 0:
            print_success("Tunnel verified - portal is accessible from remote machine")
        else:
            print_warning("Could not verify tunnel (portal may not be running yet)")

        return True

    except subprocess.TimeoutExpired:
        print_error("Tunnel creation timed out")
        return False
    except Exception as e:
        print_error(f"Tunnel creation failed: {e}")
        return False


def offer_autossh_setup(machine: dict, portal_port: int) -> None:
    """Offer to install and configure autossh for persistent tunnels.

    Args:
        machine: Machine dict with 'id', 'host', 'user'
        portal_port: Portal port number
    """
    machine_id = machine.get("id", "unknown")
    host = machine.get("host", "")
    user = machine.get("user", "")
    ssh_target = f"{user}@{host}" if user else host

    print(f"\n{BOLD}Persistent Tunnels with autossh{RESET}")
    print()
    print_info("autossh automatically restarts SSH tunnels if they fail.")
    print_info("This keeps the tunnel running even after network interruptions.")
    print()

    if not prompt_yes_no(f"Set up autossh for {machine_id}?", default=False):
        print_info(f"You can manually restart the tunnel with:")
        print_info(f"  ssh -R {portal_port}:localhost:{portal_port} -N -f {ssh_target}")
        return

    # Check if autossh is installed on portal machine (local)
    if not check_command_exists("autossh"):
        print_error("autossh not found on this machine")
        print()
        platform = detect_platform()
        if platform == "macos":
            print_info("Install with: brew install autossh")
        elif platform in ("linux", "wsl"):
            print_info("Install with: sudo apt install autossh")
        print()
        return

    # Create autossh command
    print(f"\nTo make the tunnel persistent, add this to your startup scripts:")
    print()
    print(f"{CYAN}autossh -M 0 -N -f -R {portal_port}:localhost:{portal_port} \\")
    print(f"  -o ServerAliveInterval=60 -o ServerAliveCountMax=3 \\")
    print(f"  {ssh_target}{RESET}")
    print()
    print_info("This will be started automatically on portal startup if added to agentwire config.")


def setup_remote_machine_config(
    host: str,
    user: str,
    projects_dir: str,
    portal_machine_id: str,
    portal_host: str,
    portal_user: str,
) -> bool:
    """Set up AgentWire config on a remote machine via SSH.

    Creates config.yaml and machines.json on the remote machine,
    configured to connect to this machine as the portal.

    Returns:
        True if successful
    """
    import socket
    local_hostname = socket.gethostname().lower()

    # Generate config.yaml for the remote machine
    config_yaml = f'''# AgentWire Configuration
# Generated by: agentwire init (from {local_hostname})

server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

projects:
  dir: "{projects_dir}"
  worktrees:
    enabled: true
    suffix: "-worktrees"

tts:
  backend: "none"
  url: "http://localhost:8100"
  default_voice: "default"

stt:
  backend: "none"
  language: "en"

agent:
  command: "claude --dangerously-skip-permissions"

# Network service locations - this machine connects to portal elsewhere
services:
  portal:
    machine: "{portal_machine_id}"
    port: 8765
    scheme: "https"
  tts:
    machine: null
    port: 8100
    scheme: "http"
'''

    # Generate machines.json with portal machine info
    machines_json = json.dumps({
        "machines": [{
            "id": portal_machine_id,
            "host": portal_host,
            "user": portal_user,
            "projects_dir": "~/projects",
        }]
    }, indent=2)

    try:
        ssh_target = f"{user}@{host}"

        # Create .agentwire directory
        subprocess.run(
            ["ssh", ssh_target, "mkdir -p ~/.agentwire"],
            check=True,
            capture_output=True,
            timeout=30,
        )

        # Write config.yaml
        subprocess.run(
            ["ssh", ssh_target, f"cat > ~/.agentwire/config.yaml"],
            input=config_yaml,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Write machines.json
        subprocess.run(
            ["ssh", ssh_target, f"cat > ~/.agentwire/machines.json"],
            input=machines_json,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Create rooms.json with empty object
        subprocess.run(
            ["ssh", ssh_target, f"cat > ~/.agentwire/rooms.json"],
            input="{}",
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Create portal_url file for say to work
        portal_url = f"https://{portal_host}:8765"
        subprocess.run(
            ["ssh", ssh_target, f"cat > ~/.agentwire/portal_url"],
            input=portal_url,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
        print_error(f"Failed to set up remote config: {e}")
        return False


def list_audio_devices() -> list[tuple[int, str]]:
    """List available audio input devices on macOS. Returns list of (index, name)."""
    if sys.platform != "darwin":
        return []

    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Parse stderr for audio devices (ffmpeg outputs device list to stderr)
        output = result.stderr
        devices = []
        in_audio_section = False

        for line in output.split("\n"):
            if "AVFoundation audio devices:" in line:
                in_audio_section = True
                continue
            if in_audio_section:
                # Lines look like: [AVFoundation indev @ 0x...] [0] Device Name
                if "[AVFoundation" in line and "]" in line:
                    # Extract device index and name
                    import re
                    match = re.search(r'\[(\d+)\]\s+(.+)$', line)
                    if match:
                        idx = int(match.group(1))
                        name = match.group(2).strip()
                        devices.append((idx, name))
        return devices
    except Exception:
        return []


def load_existing_config() -> Optional[dict]:
    """Load existing config if present."""
    config_path = CONFIG_DIR / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return None


def backup_config() -> Optional[Path]:
    """Backup existing config directory."""
    if CONFIG_DIR.exists():
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = CONFIG_DIR.parent / f".agentwire_backup_{timestamp}"
        shutil.copytree(CONFIG_DIR, backup_path)
        return backup_path
    return None


def check_python_version() -> tuple[bool, str]:
    """Check if Python version is >= 3.10.

    Returns:
        Tuple of (is_valid, version_string)
    """
    version_info = sys.version_info
    version_string = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    is_valid = version_info >= (3, 10)
    return is_valid, version_string


def get_python_upgrade_instructions(platform: str) -> str:
    """Get platform-specific Python upgrade instructions."""
    if platform == "macos":
        return """To upgrade Python on macOS:

  Using Homebrew (recommended):
    brew install python@3.12

  Using pyenv:
    pyenv install 3.12.0
    pyenv global 3.12.0

  More info: https://www.python.org/downloads/macos/"""
    elif platform in ("linux", "wsl"):
        return """To upgrade Python on Ubuntu/Debian:

  sudo apt update
  sudo apt install python3.12 python3.12-venv

  More info: https://www.python.org/downloads/"""
    else:
        return """Please visit https://www.python.org/downloads/ to install Python 3.10 or later."""


def check_ffmpeg() -> tuple[bool, str]:
    """Check if ffmpeg is installed.

    Returns:
        Tuple of (is_installed, path_or_message)
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return True, ffmpeg_path
    return False, "not found"


def get_ffmpeg_install_instructions(platform: str) -> str:
    """Get platform-specific ffmpeg install instructions."""
    if platform == "macos":
        return "Install with Homebrew: brew install ffmpeg"
    elif platform in ("linux", "wsl"):
        return "Install with apt: sudo apt install ffmpeg"
    else:
        return "Visit https://ffmpeg.org/download.html"


def check_stt_dependencies(backend: str, platform: str) -> tuple[bool, str]:
    """Check if STT backend dependencies are available.

    Returns:
        Tuple of (is_available, message)
    """
    if backend == "whisperkit":
        # Check for whisperkit-cli binary
        whisperkit_cli = shutil.which("whisperkit-cli")
        if not whisperkit_cli:
            return False, "whisperkit-cli binary not found"

        # Check for MacWhisper models directory
        models_dir = Path.home() / "Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml"
        if not models_dir.exists():
            return False, "MacWhisper models directory not found"

        # List available models
        try:
            models = [d.name for d in models_dir.iterdir() if d.is_dir()]
            if not models:
                return False, "No WhisperKit models found in MacWhisper directory"
            return True, f"Found {len(models)} model(s)"
        except Exception:
            return False, "Could not read models directory"

    elif backend == "whispercpp":
        return True, "Model path will be configured"

    elif backend == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return False, "OPENAI_API_KEY environment variable not set"
        return True, "API key found"

    elif backend == "faster-whisper":
        return True, "Faster-whisper will download models on first use"

    else:
        return True, "No dependencies required"


def get_stt_dependency_fix(backend: str) -> str:
    """Get instructions for fixing missing STT dependencies."""
    if backend == "whisperkit":
        return """Install MacWhisper to get WhisperKit:

  Download from: https://goodsnooze.gumroad.com/l/macwhisper

  After installation, models will be at:
  ~/Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/

  Or choose a different STT backend (whispercpp, openai)."""

    elif backend == "openai":
        return """Set your OpenAI API key:

  export OPENAI_API_KEY='your-api-key-here'

  Add to ~/.bashrc or ~/.zshrc for persistence."""

    return "No action needed"


def print_dependency_summary(checks: dict[str, tuple[bool, str]]) -> bool:
    """Print summary of dependency checks.

    Args:
        checks: Dict mapping check name to (passed, message) tuple

    Returns:
        True if all checks passed
    """
    print_header("Dependency Summary")

    all_passed = True
    for check_name, (passed, message) in checks.items():
        if passed:
            print_success(f"{check_name}: {message}")
        else:
            print_error(f"{check_name}: {message}")
            all_passed = False

    return all_passed


def run_onboarding(skip_session: bool = False) -> int:
    """Run the interactive onboarding wizard.

    Args:
        skip_session: If True, skip the final initial session setup prompt.
    """
    print()
    print(f"{BOLD}Welcome to AgentWire Setup!{RESET}")
    print()
    print("AgentWire is a multi-room voice interface for AI coding agents.")
    print("I'll walk you through configuring your environment.")
    print()

    # ─────────────────────────────────────────────────────────────
    # Pre-flight Checks
    # ─────────────────────────────────────────────────────────────
    print_header("Pre-flight Checks")

    platform = detect_platform()
    dependency_checks = {}

    # Check Python version
    python_valid, python_version = check_python_version()
    dependency_checks["Python version"] = (python_valid, f"{python_version} (required: >=3.10)")

    if not python_valid:
        print_error(f"Python {python_version} is too old (required: >=3.10)")
        print()
        print(get_python_upgrade_instructions(platform))
        print()
        return 1
    else:
        print_success(f"Python {python_version}")

    # Check ffmpeg
    ffmpeg_installed, ffmpeg_path = check_ffmpeg()
    dependency_checks["ffmpeg"] = (ffmpeg_installed, ffmpeg_path)

    if not ffmpeg_installed:
        print_warning(f"ffmpeg not found")
        print_info(get_ffmpeg_install_instructions(platform))
        print_info("Push-to-talk voice input will not work without ffmpeg")
    else:
        print_success(f"ffmpeg: {ffmpeg_path}")

    print()

    # Check for existing config
    existing_config = load_existing_config()
    existing_machines = None

    if existing_config is not None:
        print_warning("Existing AgentWire configuration found.")
        print()

        # Show current settings summary
        projects_dir = existing_config.get("projects", {}).get("dir", "~/projects")
        agent_cmd = existing_config.get("agent", {}).get("command", "claude")
        tts_backend = existing_config.get("tts", {}).get("backend", "none")
        stt_backend = existing_config.get("stt", {}).get("backend", "none")

        print(f"  Projects:  {projects_dir}")
        print(f"  Agent:     {agent_cmd}")
        print(f"  TTS:       {tts_backend}")
        print(f"  STT:       {stt_backend}")
        print()

        # Load existing machines
        machines_path = CONFIG_DIR / "machines.json"
        if machines_path.exists():
            try:
                with open(machines_path) as f:
                    existing_machines = json.load(f).get("machines", [])
                if existing_machines:
                    print(f"  Machines:  {len(existing_machines)} configured")
            except Exception:
                pass

        print()
        choice = prompt_choice(
            "What would you like to do?",
            [
                ("adjust", "Adjust specific settings"),
                ("fresh", "Start fresh (backs up current config)"),
                ("cancel", "Cancel"),
            ],
            default=1,
        )

        if choice == "cancel":
            print("\nSetup cancelled.")
            return 0

        if choice == "fresh":
            backup_path = backup_config()
            if backup_path:
                print_success(f"Backed up existing config to {backup_path}")
            existing_config = None
            existing_machines = None

    # Initialize config values with defaults or existing
    config = {
        "projects_dir": "~/projects",
        "agent_command": "claude --dangerously-skip-permissions",
        "tts_backend": "chatterbox",
        "tts_url": "http://localhost:8100",
        "tts_voice": "default",
        "stt_backend": "whisperkit" if detect_platform() == "macos" else "whispercpp",
        "stt_language": "en",
        "audio_input_device": "default",
        "generate_certs": True,
        "machines": [],
        # Network topology - where services run
        "is_portal_host": True,  # Is this machine hosting the portal?
        "portal_machine": None,  # If not portal host, which machine is?
        "tts_machine": None,  # Which machine runs TTS? (None = local)
    }

    # Pre-fill from existing config
    if existing_config:
        config["projects_dir"] = existing_config.get("projects", {}).get("dir", config["projects_dir"])
        config["agent_command"] = existing_config.get("agent", {}).get("command", config["agent_command"])
        config["tts_backend"] = existing_config.get("tts", {}).get("backend", config["tts_backend"])
        config["tts_url"] = existing_config.get("tts", {}).get("url", config["tts_url"])
        config["tts_voice"] = existing_config.get("tts", {}).get("default_voice", config["tts_voice"])
        config["stt_backend"] = existing_config.get("stt", {}).get("backend", config["stt_backend"])
        config["audio_input_device"] = existing_config.get("audio", {}).get("input_device", "default")
        config["generate_certs"] = False  # Already have certs if existing
        # Load existing services config
        services = existing_config.get("services", {})
        portal_machine = services.get("portal", {}).get("machine")
        config["is_portal_host"] = portal_machine is None
        config["portal_machine"] = portal_machine
        config["tts_machine"] = services.get("tts", {}).get("machine")

    if existing_machines:
        config["machines"] = existing_machines

    # ─────────────────────────────────────────────────────────────
    # Section 1: Projects Directory
    # ─────────────────────────────────────────────────────────────
    print_header("1. Projects Directory")

    print("Where do your code projects live?")
    print()
    print_info("This is the base directory where AgentWire looks for projects.")
    print_info("Session 'myapp' will map to ~/projects/myapp/")
    print()

    config["projects_dir"] = prompt("Projects directory", config["projects_dir"])

    # Expand and validate
    projects_path = Path(config["projects_dir"]).expanduser()
    if not projects_path.exists():
        if prompt_yes_no(f"Directory {projects_path} doesn't exist. Create it?"):
            projects_path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {projects_path}")
        else:
            print_warning("Directory will need to exist before using AgentWire")
    else:
        print_success(f"Found {projects_path}")

    # ─────────────────────────────────────────────────────────────
    # Section 2: Agent Command
    # ─────────────────────────────────────────────────────────────
    print_header("2. Agent Command")

    print("What command should AgentWire use to start Claude Code sessions?")
    print()

    agent_choice = prompt_choice(
        "",
        [
            ("skip", "claude --dangerously-skip-permissions (Recommended - full automation)"),
            ("standard", "claude (Standard - will prompt for permissions)"),
            ("custom", "Custom command (for Aider, Cursor, or other agents)"),
        ],
        default=1 if "--dangerously-skip-permissions" in config["agent_command"] else 2,
    )

    if agent_choice == "skip":
        config["agent_command"] = "claude --dangerously-skip-permissions"
    elif agent_choice == "standard":
        config["agent_command"] = "claude"
    else:
        config["agent_command"] = prompt("Enter custom command", config["agent_command"])

    print_success(f"Agent command: {config['agent_command']}")

    # ─────────────────────────────────────────────────────────────
    # Section 3: Network Role
    # ─────────────────────────────────────────────────────────────
    print_header("3. Network Role")

    print("AgentWire can run as a single machine or part of a multi-machine network.")
    print()
    print_info("Portal: The main web server where you access rooms and voice input.")
    print_info("Worker: A machine that runs Claude Code sessions, connected to a portal.")
    print()

    role_choice = prompt_choice(
        "What is this machine's role?",
        [
            ("portal", "Portal host (runs the web server - other machines connect here)"),
            ("worker", "Worker (connects to a portal running elsewhere)"),
            ("standalone", "Standalone (single machine, no network)"),
        ],
        default=1 if config["is_portal_host"] else 2,
    )

    if role_choice == "standalone":
        config["is_portal_host"] = True
        config["portal_machine"] = None
        print_success("Standalone mode: Portal and sessions run on this machine")
    elif role_choice == "portal":
        config["is_portal_host"] = True
        config["portal_machine"] = None
        print_success("This machine will host the portal")
    else:
        # Worker machine - needs to know where portal is
        config["is_portal_host"] = False
        print()
        print("Enter details for the machine running the portal:")
        print()

        portal_id = prompt("Portal machine ID (e.g., 'jordans-mini')", config.get("portal_machine") or "")
        if not portal_id:
            print_error("Portal machine ID is required for worker mode")
            portal_id = prompt("Portal machine ID")

        portal_host = prompt("Portal hostname or IP (e.g., '192.168.1.100')", "")
        portal_user = prompt("SSH user on portal machine", os.environ.get("USER", "user"))
        portal_projects = prompt("Projects directory on portal machine", "~/projects")

        config["portal_machine"] = portal_id

        # Add portal machine to machines list if not already there
        existing_ids = [m.get("id") for m in config["machines"]]
        if portal_id not in existing_ids:
            config["machines"].append({
                "id": portal_id,
                "host": portal_host,
                "user": portal_user,
                "projects_dir": portal_projects,
            })
            print_success(f"Added portal machine '{portal_id}' to machines list")

        # Test connection to portal
        if portal_host:
            print(f"\nTesting SSH connection to {portal_user}@{portal_host}...")
            if test_ssh_connection(portal_host, portal_user):
                print_success("Connection successful!")
            else:
                print_warning("Could not connect (portal may not be set up for SSH yet)")

    # ─────────────────────────────────────────────────────────────
    # Section 4: Text-to-Speech
    # ─────────────────────────────────────────────────────────────
    print_header("4. Text-to-Speech (TTS)")

    print("TTS converts agent responses to spoken audio.")
    print()

    tts_choice = prompt_choice(
        "Which TTS backend?",
        [
            ("chatterbox", "Chatterbox (Local, high quality, requires setup)"),
            ("elevenlabs", "ElevenLabs (Cloud API, requires API key)"),
            ("none", "None (Text only, no voice output)"),
        ],
        default=1 if config["tts_backend"] == "chatterbox" else
                2 if config["tts_backend"] == "elevenlabs" else 3,
    )

    config["tts_backend"] = tts_choice

    if tts_choice == "chatterbox":
        print()
        tts_location = prompt_choice(
            "Where is Chatterbox running?",
            [
                ("local", "Local machine (I'll start it with 'agentwire tts start')"),
                ("remote", "Remote machine (already running elsewhere)"),
            ],
            default=1,
        )

        if tts_location == "local":
            config["tts_url"] = "http://localhost:8100"
            print()
            print_info("Start the TTS server with: agentwire tts start")
        else:
            print()
            config["tts_url"] = prompt("Chatterbox server URL (e.g., http://dotdev-pc:8100)", config["tts_url"])
            # Test connection
            print(f"\nTesting connection to {config['tts_url']}...")
            try:
                import urllib.request
                req = urllib.request.urlopen(f"{config['tts_url']}/voices", timeout=3)
                print_success("TTS server is reachable!")
            except Exception:
                print_warning("Could not reach TTS server (may not be running yet)")

        print()
        config["tts_voice"] = prompt("Default voice", config["tts_voice"])

    elif tts_choice == "elevenlabs":
        print()
        print_info("Set ELEVENLABS_API_KEY environment variable with your API key")
        config["tts_voice"] = prompt("Default voice ID", "default")

    else:
        print_info("Voice output disabled. Agents will respond with text only.")

    # Audio input device (for voice cloning, STT, etc.) - only on macOS
    config["audio_input_device"] = "default"
    if platform == "macos":
        print()
        print(f"{DIM}Audio Input Device:{RESET}")
        print_info("Select which microphone to use for voice input and cloning.")
        print()

        # List available audio devices
        audio_devices = list_audio_devices()
        if audio_devices:
            device_options = [("default", "System default input device")]
            for idx, name in audio_devices:
                device_options.append((str(idx), f"{name} (device {idx})"))

            device_choice = prompt_choice("Which microphone?", device_options, default=1)
            config["audio_input_device"] = device_choice
            print_success(f"Audio input will use: {device_choice}")

    # ─────────────────────────────────────────────────────────────
    # Section 5: Speech-to-Text
    # ─────────────────────────────────────────────────────────────
    print_header("5. Speech-to-Text (STT)")

    print("STT converts your voice to text for sending to agents.")
    print()

    platform = detect_platform()

    if platform == "macos":
        stt_options = [
            ("whisperkit", "WhisperKit (Fast, local, macOS optimized)"),
            ("whispercpp", "whisper.cpp (Local, cross-platform)"),
            ("openai", "OpenAI API (Cloud, requires API key)"),
            ("none", "None (Typing only, no voice input)"),
        ]
        default_stt = 1
    else:
        stt_options = [
            ("whispercpp", "whisper.cpp (Local, good quality)"),
            ("faster-whisper", "faster-whisper (Local, optimized)"),
            ("openai", "OpenAI API (Cloud, requires API key)"),
            ("none", "None (Typing only, no voice input)"),
        ]
        default_stt = 1

    # Find current selection in options
    for i, (key, _) in enumerate(stt_options, 1):
        if key == config["stt_backend"]:
            default_stt = i
            break

    stt_choice = prompt_choice("Which STT backend?", stt_options, default=default_stt)
    config["stt_backend"] = stt_choice

    # Check STT dependencies
    if stt_choice != "none":
        print()
        stt_ok, stt_message = check_stt_dependencies(stt_choice, platform)
        dependency_checks[f"STT ({stt_choice})"] = (stt_ok, stt_message)

        if not stt_ok:
            print_error(f"STT dependency check failed: {stt_message}")
            print()
            print(get_stt_dependency_fix(stt_choice))
            print()
        else:
            print_success(f"{stt_choice}: {stt_message}")

    if stt_choice == "openai":
        print()
        print_info("Set OPENAI_API_KEY environment variable with your API key")
    elif stt_choice == "none":
        print_info("Voice input disabled. Use typing to communicate with agents.")
    else:
        if stt_choice not in dependency_checks:
            print_success(f"Using {stt_choice} for speech recognition")

    # ─────────────────────────────────────────────────────────────
    # Section 6: SSL Certificates
    # ─────────────────────────────────────────────────────────────
    print_header("6. SSL Certificates")

    print("SSL certificates are required for browser microphone access.")
    print_info("Browsers only allow mic access over HTTPS.")
    print()

    cert_path = CONFIG_DIR / "cert.pem"
    key_path = CONFIG_DIR / "key.pem"

    if cert_path.exists() and key_path.exists():
        print_success("SSL certificates already exist")
        if prompt_yes_no("Regenerate certificates?", default=False):
            config["generate_certs"] = True
        else:
            config["generate_certs"] = False
    else:
        config["generate_certs"] = prompt_yes_no("Generate self-signed SSL certificates?")

    # ─────────────────────────────────────────────────────────────
    # Section 7: Remote Machines (Optional)
    # ─────────────────────────────────────────────────────────────
    print_header("7. Remote Machines (Optional)")

    print("Remote machines allow you to run Claude Code sessions on other computers")
    print_info("(e.g., a GPU server for ML work, a cloud devbox, etc.)")
    print()

    if config["machines"]:
        print(f"Currently configured machines: {len(config['machines'])}")
        for m in config["machines"]:
            print(f"  - {m.get('id')}: {m.get('user', 'user')}@{m.get('host')}")
        print()

    # Track which machines need remote setup
    machines_to_setup = []

    if prompt_yes_no("Configure remote machines?", default=bool(config["machines"])):
        if config["machines"] and not prompt_yes_no("Keep existing machines and add more?"):
            config["machines"] = []

        while True:
            print()
            machine_id = prompt("Machine ID (short name, e.g., 'gpu-server')", "").strip()
            if not machine_id:
                break

            host = prompt("Hostname or IP")
            user = prompt("SSH user", os.environ.get("USER", "user"))
            projects_dir = prompt("Projects directory on remote", "~/projects")

            # Test connection
            print(f"\nTesting SSH connection to {user}@{host}...")
            connection_ok = test_ssh_connection(host, user)
            if connection_ok:
                print_success("Connection successful!")
                config["machines"].append({
                    "id": machine_id,
                    "host": host,
                    "user": user,
                    "projects_dir": projects_dir,
                })
                # Offer to set up remote config if this is the portal host
                if config["is_portal_host"]:
                    machines_to_setup.append({
                        "id": machine_id,
                        "host": host,
                        "user": user,
                        "projects_dir": projects_dir,
                    })
            else:
                print_error("Connection failed")
                if prompt_yes_no("Add anyway?", default=False):
                    config["machines"].append({
                        "id": machine_id,
                        "host": host,
                        "user": user,
                        "projects_dir": projects_dir,
                    })

            if not prompt_yes_no("\nAdd another machine?", default=False):
                break

    # Offer to set up remote machines with full installation
    if machines_to_setup and config["is_portal_host"]:
        print()
        print_header("Remote Machine Setup")
        print("I can install and configure AgentWire on remote machines automatically.")
        print()
        print_info("This will:")
        print_info("  • Check Python version and dependencies")
        print_info("  • Install AgentWire package (handles venv for Ubuntu)")
        print_info("  • Create configuration files")
        print_info("  • Install skills and scripts")
        print_info("  • Set up reverse SSH tunnels for portal access")
        print()

        local_hostname, local_ip = get_local_machine_info()
        local_user = os.environ.get("USER", "user")

        for machine in machines_to_setup:
            if prompt_yes_no(f"Set up AgentWire on {machine['id']} ({machine['user']}@{machine['host']})?"):
                if setup_remote_machine(
                    host=machine["host"],
                    user=machine["user"],
                    projects_dir=machine["projects_dir"],
                    portal_machine_id=local_hostname,
                    portal_host=local_ip,
                    portal_user=local_user,
                ):
                    # Offer reverse tunnel setup
                    if prompt_yes_no(f"\nCreate reverse SSH tunnel for {machine['id']}?", default=True):
                        portal_port = 8765  # Default portal port
                        if create_reverse_tunnel(portal_port, machine):
                            # Offer autossh for persistence
                            offer_autossh_setup(machine, portal_port)
                else:
                    print_warning(f"Could not set up {machine['id']} - you'll need to configure it manually")

    # ─────────────────────────────────────────────────────────────
    # Dependency Summary
    # ─────────────────────────────────────────────────────────────
    print()
    all_deps_ok = print_dependency_summary(dependency_checks)

    if not all_deps_ok:
        print()
        print_warning("Some dependencies are missing. AgentWire may not work correctly.")
        print_info("You can install missing dependencies later and re-run 'agentwire init'")
        print_info("Or use 'agentwire doctor' to check and fix issues after installation.")
        print()

        if not prompt_yes_no("Continue anyway?", default=False):
            print()
            print("Setup cancelled. Fix the issues above and run 'agentwire init' again.")
            return 1

    # ─────────────────────────────────────────────────────────────
    # Generate Configuration Files
    # ─────────────────────────────────────────────────────────────
    print_header("Saving Configuration")

    # Create config directory
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Write config.yaml
    # Build services section based on network role
    portal_machine_yaml = f'"{config["portal_machine"]}"' if config["portal_machine"] else "null"
    tts_machine_yaml = f'"{config["tts_machine"]}"' if config["tts_machine"] else "null"

    config_content = f"""# AgentWire Configuration
# Generated by: agentwire init

server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

projects:
  dir: "{config['projects_dir']}"
  worktrees:
    enabled: true
    suffix: "-worktrees"

tts:
  backend: "{config['tts_backend']}"
  url: "{config['tts_url']}"
  default_voice: "{config['tts_voice']}"

stt:
  backend: "{config['stt_backend']}"
  language: "{config['stt_language']}"

audio:
  input_device: {config['audio_input_device']}  # Microphone for voice input & cloning

agent:
  command: "{config['agent_command']}"

# Network service locations
# machine: null means service runs locally
# machine: "machine-id" means service runs on that remote machine
services:
  portal:
    machine: {portal_machine_yaml}
    port: 8765
    scheme: "https"
  tts:
    machine: {tts_machine_yaml}
    port: 8100
    scheme: "http"
"""

    config_path = CONFIG_DIR / "config.yaml"
    config_path.write_text(config_content)
    print_success(f"Created {config_path}")

    # Write machines.json
    machines_path = CONFIG_DIR / "machines.json"
    machines_content = {"machines": config["machines"]}
    machines_path.write_text(json.dumps(machines_content, indent=2) + "\n")
    print_success(f"Created {machines_path}")

    # Write rooms.json if not exists
    rooms_path = CONFIG_DIR / "rooms.json"
    if not rooms_path.exists():
        rooms_content = {
            "agentwire": {
                "roles": ["agentwire"],
                "voice": config["tts_voice"],
            }
        }
        rooms_path.write_text(json.dumps(rooms_content, indent=2) + "\n")
        print_success(f"Created {rooms_path}")

    # Create roles directory and default files
    roles_dir = CONFIG_DIR / "roles"
    roles_dir.mkdir(exist_ok=True)

    agentwire_role = roles_dir / "agentwire.md"
    if not agentwire_role.exists():
        agentwire_role.write_text("""# Role: AgentWire Session

You are the main agentwire session in the AgentWire system.
You coordinate worker sessions via /agentwire skills.

Available commands: /sessions, /send, /output, /new, /kill, /status, /jump
""")
        print_success(f"Created {agentwire_role}")

    worker_role = roles_dir / "worker.md"
    if not worker_role.exists():
        worker_role.write_text("""# Role: Worker

You are a worker session focused on completing assigned tasks.
Stay focused on your project directory and commit frequently.
""")
        print_success(f"Created {worker_role}")

    # Generate SSL certificates if requested
    if config["generate_certs"]:
        print()
        print("Generating SSL certificates...")
        try:
            subprocess.run(
                [
                    "openssl", "req", "-x509", "-newkey", "rsa:4096",
                    "-keyout", str(CONFIG_DIR / "key.pem"),
                    "-out", str(CONFIG_DIR / "cert.pem"),
                    "-days", "365", "-nodes",
                    "-subj", "/CN=localhost",
                ],
                check=True,
                capture_output=True,
            )
            print_success(f"Created {CONFIG_DIR / 'cert.pem'}")
            print_success(f"Created {CONFIG_DIR / 'key.pem'}")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to generate certificates: {e.stderr.decode() if e.stderr else 'unknown error'}")
        except FileNotFoundError:
            print_error("openssl not found. Install OpenSSL to generate certificates.")

    # ─────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────
    print_header("Local Setup Complete!")

    print(f"{BOLD}Your configuration:{RESET}")
    print(f"  Projects:    {config['projects_dir']}")
    print(f"  Agent:       {config['agent_command']}")
    print(f"  TTS:         {config['tts_backend']}", end="")
    if config['tts_backend'] == 'chatterbox':
        print(f" @ {config['tts_url']}")
    else:
        print()
    print(f"  STT:         {config['stt_backend']}")
    print(f"  Machines:    {len(config['machines'])} configured" if config['machines'] else "  Machines:    Local only")

    # ─────────────────────────────────────────────────────────────
    # Initial Session Setup (Optional)
    # ─────────────────────────────────────────────────────────────
    if not skip_session:
        print()
        print_info("The next step is optional: Claude can help you with advanced setup")
        print_info("(multi-machine networking, TTS configuration, testing services).")
        print()

        if prompt_yes_no("Ready to start initial session setup?"):
            from .init_agentwire import spawn_init_session
            return spawn_init_session()

    # User declined session setup (or skip_session=True) - show manual next steps
    print()
    print(f"{BOLD}Next steps:{RESET}")
    if config['tts_backend'] == 'chatterbox':
        print(f"  1. {CYAN}agentwire tts start{RESET}     # Start TTS server")
        print(f"  2. {CYAN}agentwire portal start{RESET}  # Start the web portal")
    else:
        print(f"  1. {CYAN}agentwire portal start{RESET}  # Start the web portal")
    print(f"  3. Open {CYAN}https://localhost:8765{RESET} in your browser")
    print()
    if not skip_session:
        print_info("Run 'agentwire dev' anytime to start the main agentwire session.")
        print()

    return 0
