"""Mission safety validator for AgentWire damage control integration."""

import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

try:
    from .cli_safety import check_command_safety, load_patterns
except ImportError:
    # Fallback if imported standalone
    from cli_safety import check_command_safety, load_patterns


class SafetyWarning:
    """Represents a safety warning found in a mission file."""

    def __init__(
        self,
        line_number: int,
        line_content: str,
        command: str,
        decision: str,
        reason: str,
        pattern: str = None
    ):
        self.line_number = line_number
        self.line_content = line_content
        self.command = command
        self.decision = decision
        self.reason = reason
        self.pattern = pattern

    def __str__(self) -> str:
        severity = "CRITICAL" if self.decision == "block" else "WARNING"
        icon = "✗" if self.decision == "block" else "?"

        lines = [
            f"{icon} {severity} at line {self.line_number}:",
            f"  Command: {self.command}",
            f"  Reason: {self.reason}",
        ]
        if self.pattern:
            lines.append(f"  Pattern: {self.pattern}")
        lines.append(f"  Context: {self.line_content[:80]}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "line_number": self.line_number,
            "line_content": self.line_content,
            "command": self.command,
            "decision": self.decision,
            "reason": self.reason,
            "pattern": self.pattern,
        }


def extract_bash_commands(line: str) -> List[str]:
    """
    Extract bash commands from a mission line.

    Looks for:
    - Backtick code blocks: `command`
    - Inline code in descriptions
    - Commands after colons or dashes
    """
    commands = []

    # Pattern 1: Backtick code blocks
    backtick_pattern = r'`([^`]+)`'
    for match in re.finditer(backtick_pattern, line):
        cmd = match.group(1).strip()
        # Skip if it looks like a file path or URL
        if not cmd.startswith(('http://', 'https://', '/', '~/', './')):
            # Skip if it's just a variable or single word
            if ' ' in cmd or any(op in cmd for op in ['rm', 'mv', 'cp', 'git', 'chmod']):
                commands.append(cmd)

    # Pattern 2: Commands in task descriptions
    # Example: "- Run `git status` to check"
    # Example: "Execute: rm -rf /tmp"
    description_pattern = r'(?:run|execute|call|invoke)[\s:]+(.+?)(?:\s+to\s+|$)'
    for match in re.finditer(description_pattern, line, re.IGNORECASE):
        cmd = match.group(1).strip()
        # Clean up trailing punctuation
        cmd = re.sub(r'[.,;]$', '', cmd)
        if cmd and not cmd.startswith(('http://', 'https://')):
            commands.append(cmd)

    return commands


def validate_mission_safety(mission_file: Path, verbose: bool = False) -> List[SafetyWarning]:
    """
    Validate a mission file for dangerous commands.

    Args:
        mission_file: Path to mission markdown file
        verbose: If True, print progress

    Returns:
        List of SafetyWarning objects
    """
    if not mission_file.exists():
        if verbose:
            print(f"Mission file not found: {mission_file}")
        return []

    warnings = []
    patterns = load_patterns()

    if verbose:
        print(f"Scanning mission: {mission_file}")
        print(f"Loaded {len(patterns.get('bashToolPatterns', []))} bash patterns")

    try:
        with open(mission_file, "r") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, start=1):
            # Skip headings and empty lines
            if line.strip().startswith('#') or not line.strip():
                continue

            # Extract potential bash commands from line
            commands = extract_bash_commands(line)

            for cmd in commands:
                # Check command safety
                result = check_command_safety(cmd, verbose=False)

                if result["decision"] in ["block", "ask"]:
                    warning = SafetyWarning(
                        line_number=line_num,
                        line_content=line.strip(),
                        command=cmd,
                        decision=result["decision"],
                        reason=result["reason"],
                        pattern=result.get("pattern")
                    )
                    warnings.append(warning)

                    if verbose:
                        print(f"  Line {line_num}: {result['decision'].upper()} - {cmd[:60]}")

    except Exception as e:
        if verbose:
            print(f"Error reading mission file: {e}")
        return []

    return warnings


def format_mission_safety_report(
    mission_file: Path,
    warnings: List[SafetyWarning]
) -> str:
    """Format safety warnings into a readable report."""
    lines = []

    lines.append(f"Mission Safety Report: {mission_file.name}")
    lines.append("=" * 80)
    lines.append("")

    if not warnings:
        lines.append("✓ No safety warnings found")
        return "\n".join(lines)

    # Count by severity
    blocks = [w for w in warnings if w.decision == "block"]
    asks = [w for w in warnings if w.decision == "ask"]

    lines.append(f"Found {len(warnings)} potential issues:")
    lines.append(f"  • Critical (would be blocked): {len(blocks)}")
    lines.append(f"  • Warnings (would require confirmation): {len(asks)}")
    lines.append("")

    # Show all warnings
    for i, warning in enumerate(warnings, start=1):
        lines.append(f"{i}. {warning}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("Recommendation:")
    if blocks:
        lines.append("  ⚠️  This mission contains commands that would be BLOCKED.")
        lines.append("  Review the critical issues above before executing.")
    else:
        lines.append("  ℹ️  This mission contains commands that may require confirmation.")
        lines.append("  Review warnings above and be prepared to approve during execution.")

    return "\n".join(lines)


def validate_mission_cmd(mission_file_path: str, verbose: bool = False) -> int:
    """
    CLI command for mission safety validation.

    Returns:
        0 if no blocks found, 1 if blocks found, 2 on error
    """
    mission_file = Path(mission_file_path).expanduser()

    if not mission_file.exists():
        print(f"Error: Mission file not found: {mission_file}")
        return 2

    warnings = validate_mission_safety(mission_file, verbose)
    report = format_mission_safety_report(mission_file, warnings)

    print(report)

    # Return non-zero if blocks found
    blocks = [w for w in warnings if w.decision == "block"]
    return 1 if blocks else 0


# CLI usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python mission_safety.py <mission-file.md>")
        print("       python mission_safety.py <mission-file.md> --verbose")
        sys.exit(2)

    mission_path = sys.argv[1]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    exit_code = validate_mission_cmd(mission_path, verbose)
    sys.exit(exit_code)
