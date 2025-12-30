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


def run_onboarding() -> int:
    """Run the interactive onboarding wizard."""
    print()
    print(f"{BOLD}Welcome to AgentWire Setup!{RESET}")
    print()
    print("AgentWire is a multi-room voice interface for AI coding agents.")
    print("I'll walk you through configuring your environment.")
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
        "generate_certs": True,
        "machines": [],
    }

    # Pre-fill from existing config
    if existing_config:
        config["projects_dir"] = existing_config.get("projects", {}).get("dir", config["projects_dir"])
        config["agent_command"] = existing_config.get("agent", {}).get("command", config["agent_command"])
        config["tts_backend"] = existing_config.get("tts", {}).get("backend", config["tts_backend"])
        config["tts_url"] = existing_config.get("tts", {}).get("url", config["tts_url"])
        config["tts_voice"] = existing_config.get("tts", {}).get("default_voice", config["tts_voice"])
        config["stt_backend"] = existing_config.get("stt", {}).get("backend", config["stt_backend"])
        config["generate_certs"] = False  # Already have certs if existing

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
    # Section 3: Text-to-Speech
    # ─────────────────────────────────────────────────────────────
    print_header("3. Text-to-Speech (TTS)")

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
        config["tts_url"] = prompt("Chatterbox server URL", config["tts_url"])
        config["tts_voice"] = prompt("Default voice", config["tts_voice"])
        print()
        print_info("Start the TTS server with: agentwire tts start")

    elif tts_choice == "elevenlabs":
        print()
        print_info("Set ELEVENLABS_API_KEY environment variable with your API key")
        config["tts_voice"] = prompt("Default voice ID", "default")

    else:
        print_info("Voice output disabled. Agents will respond with text only.")

    # ─────────────────────────────────────────────────────────────
    # Section 4: Speech-to-Text
    # ─────────────────────────────────────────────────────────────
    print_header("4. Speech-to-Text (STT)")

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

    if stt_choice == "openai":
        print()
        print_info("Set OPENAI_API_KEY environment variable with your API key")
    elif stt_choice == "none":
        print_info("Voice input disabled. Use typing to communicate with agents.")
    else:
        print_success(f"Using {stt_choice} for speech recognition")

    # ─────────────────────────────────────────────────────────────
    # Section 5: SSL Certificates
    # ─────────────────────────────────────────────────────────────
    print_header("5. SSL Certificates")

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
    # Section 6: Remote Machines (Optional)
    # ─────────────────────────────────────────────────────────────
    print_header("6. Remote Machines (Optional)")

    print("Remote machines allow you to run Claude Code sessions on other computers")
    print_info("(e.g., a GPU server for ML work, a cloud devbox, etc.)")
    print()

    if config["machines"]:
        print(f"Currently configured machines: {len(config['machines'])}")
        for m in config["machines"]:
            print(f"  - {m.get('id')}: {m.get('user', 'user')}@{m.get('host')}")
        print()

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
            if test_ssh_connection(host, user):
                print_success("Connection successful!")
                config["machines"].append({
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

    # ─────────────────────────────────────────────────────────────
    # Generate Configuration Files
    # ─────────────────────────────────────────────────────────────
    print_header("Saving Configuration")

    # Create config directory
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Write config.yaml
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

agent:
  command: "{config['agent_command']}"
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
                "role": "orchestrator",
                "voice": config["tts_voice"],
            }
        }
        rooms_path.write_text(json.dumps(rooms_content, indent=2) + "\n")
        print_success(f"Created {rooms_path}")

    # Create roles directory and default files
    roles_dir = CONFIG_DIR / "roles"
    roles_dir.mkdir(exist_ok=True)

    orchestrator_role = roles_dir / "orchestrator.md"
    if not orchestrator_role.exists():
        orchestrator_role.write_text("""# Role: Orchestrator

You are the orchestrator session in the AgentWire system.
You coordinate worker and chatbot sessions via /agentwire skills.

Available commands: /sessions, /send, /output, /new, /kill, /status, /jump
""")
        print_success(f"Created {orchestrator_role}")

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
    print_header("Setup Complete!")

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

    print()
    print(f"{BOLD}Next steps:{RESET}")
    if config['tts_backend'] == 'chatterbox':
        print(f"  1. {CYAN}agentwire tts start{RESET}     # Start TTS server")
        print(f"  2. {CYAN}agentwire portal start{RESET}  # Start the web portal")
    else:
        print(f"  1. {CYAN}agentwire portal start{RESET}  # Start the web portal")
    print(f"  3. Open {CYAN}https://localhost:8765{RESET} in your browser")
    print()

    return 0
