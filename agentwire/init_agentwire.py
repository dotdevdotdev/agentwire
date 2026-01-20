"""Spawn initial agentwire session with init instructions for advanced setup."""

import importlib.resources
import subprocess
import time
from pathlib import Path

from .project_config import detect_default_agent_type

# ANSI colors (matching onboarding.py)
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{YELLOW}!{RESET} {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")


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


def tmux_session_exists(session_name: str) -> bool:
    """Check if a tmux session exists."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True,
    )
    return result.returncode == 0


def load_init_prompt() -> str:
    """Load the init prompt template from package resources."""
    try:
        # Python 3.9+ way to read package resources
        files = importlib.resources.files("agentwire")
        prompt_path = files.joinpath("prompts", "init.md")
        return prompt_path.read_text()
    except Exception as e:
        # Fallback: try reading from filesystem relative to this file
        fallback_path = Path(__file__).parent / "prompts" / "init.md"
        if fallback_path.exists():
            return fallback_path.read_text()
        print_error(f"Could not load init prompt: {e}")
        return ""


def send_to_session(session_name: str, text: str) -> bool:
    """Send text to a tmux session using agentwire send."""
    # Use agentwire send which handles the pause-before-enter properly
    result = subprocess.run(
        ["agentwire", "send", "-s", session_name, text],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def spawn_init_session() -> int:
    """Spawn agentwire session with init instructions.

    Returns:
        Exit code (0 for success)
    """
    session_name = "agentwire"

    # Check if session already exists
    if tmux_session_exists(session_name):
        print(f"\n{YELLOW}Session '{session_name}' already exists.{RESET}")

        choice = prompt_choice(
            "What would you like to do?",
            [
                ("attach", "Attach to existing session"),
                ("restart", "Kill and restart with init prompt"),
                ("cancel", "Cancel"),
            ],
            default=1,
        )

        if choice == "cancel":
            print("\nSetup cancelled.")
            return 0

        if choice == "attach":
            print("\nAttaching to session... (Ctrl+B D to detach)")
            subprocess.run(["tmux", "attach-session", "-t", session_name])
            return 0

        if choice == "restart":
            print("Killing existing session...")
            subprocess.run(["tmux", "kill-session", "-t", session_name])

    # Find project directory (where agentwire source lives)
    # First check if we're in a development environment
    project_root = Path(__file__).parent.parent
    if not (project_root / "pyproject.toml").exists():
        # Fallback to standard location
        project_root = Path.home() / "projects" / "agentwire"

    if not project_root.exists():
        # Use home projects directory as fallback
        project_root = Path.home() / "projects"

    print(f"\n{BOLD}Starting agentwire session...{RESET}")
    print(f"Working directory: {project_root}")

    # Create tmux session
    result = subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
        "-c", str(project_root),
    ])

    if result.returncode != 0:
        print_error("Failed to create tmux session")
        return 1

    print_success("Created tmux session")

    # Detect which agent to use and start it
    agent_type = detect_default_agent_type()
    if agent_type == "opencode":
        agent_command = "opencode"
    else:
        agent_command = "claude --dangerously-skip-permissions"

    subprocess.run([
        "tmux", "send-keys", "-t", session_name,
        agent_command, "Enter"
    ])

    print(f"Waiting for {agent_type} to start...")

    # Wait for agent to be ready (check for prompt)
    # Agents typically take 2-4 seconds to initialize
    time.sleep(3)

    # Load and send the init prompt
    init_prompt = load_init_prompt()

    if not init_prompt:
        print_warning("Could not load init prompt, starting empty session")
    else:
        print("Sending init instructions...")

        # Use agentwire send which handles multiline prompts properly
        if send_to_session(session_name, init_prompt):
            print_success("Sent init instructions to Claude")
        else:
            print_warning("Could not send via agentwire, trying direct tmux...")
            # Fallback: send a shorter intro if agentwire send fails
            intro = "You are helping set up AgentWire. Start by greeting the user and asking about their setup (single machine or multiple machines). Use AskUserQuestion for choices."
            subprocess.run([
                "tmux", "send-keys", "-t", session_name,
                intro, "Enter"
            ])

    print(f"\n{GREEN}✓{RESET} Session started with init instructions")
    print(f"\n{BOLD}Attaching to session...{RESET} (Ctrl+B D to detach)")

    # Attach user to the session
    subprocess.run(["tmux", "attach-session", "-t", session_name])

    return 0
