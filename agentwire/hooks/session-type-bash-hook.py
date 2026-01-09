#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
AgentWire Session Type Bash Hook
================================

Enforces bash command restrictions based on session type (orchestrator vs worker).

Orchestrator sessions:
- ALLOWED: agentwire *, remote-say *, say *, git status, git log, git diff
- BLOCKED: All other bash commands

Worker sessions:
- BLOCKED: remote-say *, say * (workers should not produce voice output)
- ALLOWED: Everything else

Exit codes:
  0 = Allow command
  2 = Block command (stderr fed back to Claude)
"""

import json
import os
import re
import sys
from pathlib import Path


def get_session_type() -> str | None:
    """Get session type from rooms.json using AGENTWIRE_ROOM env var."""
    room_name = os.environ.get("AGENTWIRE_ROOM")
    if not room_name:
        return None

    rooms_file = Path.home() / ".agentwire" / "rooms.json"
    if not rooms_file.exists():
        return None

    try:
        with open(rooms_file) as f:
            rooms = json.load(f)
        room_config = rooms.get(room_name, {})
        return room_config.get("type")
    except Exception:
        return None


def is_allowed_orchestrator_command(command: str) -> bool:
    """Check if command is allowed for orchestrator sessions.

    Allowed commands:
    - agentwire * (any agentwire subcommand)
    - remote-say "..." or say "..."
    - git status, git log, git diff (read-only git commands)
    """
    command = command.strip()

    # Allow agentwire commands
    if re.match(r'^agentwire\s', command) or command == 'agentwire':
        return True

    # Allow say/remote-say with quoted string
    if re.match(r'^(say|remote-say)\s+["\']', command):
        return True

    # Allow read-only git commands
    if re.match(r'^git\s+(status|log|diff|branch|show|remote|fetch)\b', command):
        return True

    # Allow cd and pwd for navigation
    if re.match(r'^(cd|pwd)\b', command):
        return True

    # Allow echo for debugging (useful for orchestrator feedback)
    if re.match(r'^echo\s', command):
        return True

    return False


def is_blocked_worker_command(command: str) -> bool:
    """Check if command should be blocked for worker sessions.

    Blocked commands:
    - remote-say * (workers should not produce voice output)
    - say * (workers should not produce voice output)
    """
    command = command.strip()

    # Block say/remote-say commands
    if re.match(r'^(say|remote-say)\s', command):
        return True

    return False


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If we can't parse input, allow the command
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only process Bash tool
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Get session type
    session_type = get_session_type()

    # No session type = no restrictions (backwards compat)
    if not session_type:
        sys.exit(0)

    if session_type == "orchestrator":
        if not is_allowed_orchestrator_command(command):
            # Block the command
            print(
                f"[Session Type: Orchestrator] Command blocked. "
                f"Orchestrators can only use: agentwire commands, say/remote-say, "
                f"and read-only git commands (status, log, diff).\n"
                f"To execute this command, spawn a worker session.",
                file=sys.stderr
            )
            sys.exit(2)

    elif session_type == "worker":
        if is_blocked_worker_command(command):
            # Block the command
            print(
                f"[Session Type: Worker] Command blocked. "
                f"Workers cannot use say/remote-say (voice output). "
                f"Only the orchestrator should communicate with the user via voice.",
                file=sys.stderr
            )
            sys.exit(2)

    # Allow the command
    sys.exit(0)


if __name__ == "__main__":
    main()
