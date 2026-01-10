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
- ALLOWED: agentwire *, say *, remote-say *, git status/log/diff, cd, pwd, echo, sleep
- BLOCKED: All other bash commands

Worker sessions:
- BLOCKED: say *, remote-say * (workers should not produce voice output)
- ALLOWED: Everything else

Exit codes:
  0 = Allow command
  2 = Block command (stderr fed back to Claude)
"""

import json
import os
import re
import sys


def get_session_type() -> str | None:
    """Get session type from AGENTWIRE_SESSION_TYPE env var.

    This env var is set by 'agentwire new' when creating sessions with
    --worker or --orchestrator flags.

    Returns: "orchestrator", "worker", or None (no restrictions)
    """
    return os.environ.get("AGENTWIRE_SESSION_TYPE")


def is_allowed_orchestrator_command(command: str) -> bool:
    """Check if command is allowed for orchestrator sessions.

    Allowed commands:
    - agentwire * (any agentwire subcommand)
    - say "...", remote-say "..."
    - git status, git log, git diff (read-only git commands)
    """
    command = command.strip()

    # Allow agentwire commands
    if re.match(r'^agentwire\s', command) or command == 'agentwire':
        return True

    # Allow say and remote-say with quoted string
    if re.match(r'^(remote-)?say\s+["\']', command):
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

    # Allow sleep for timing/waiting
    if re.match(r'^sleep\s', command):
        return True

    return False


def is_blocked_worker_command(command: str) -> bool:
    """Check if command should be blocked for worker sessions.

    Blocked commands:
    - say *, remote-say * (workers should not produce voice output)
    """
    command = command.strip()

    # Block say and remote-say commands
    if re.match(r'^(remote-)?say\s', command):
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

    # No session type = no restrictions
    if not session_type:
        sys.exit(0)

    if session_type == "orchestrator":
        if not is_allowed_orchestrator_command(command):
            # Block the command
            print(
                f"[Session Type: Orchestrator] Command blocked. "
                f"Orchestrators can only use: agentwire commands, say/remote-say, "
                f"read-only git commands, cd, pwd, echo, sleep.\n"
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
