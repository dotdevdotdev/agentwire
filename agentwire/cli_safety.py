"""Safety CLI commands for AgentWire damage control integration."""

import importlib.resources
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


# Default config directory
CONFIG_DIR = Path.home() / ".agentwire"
HOOKS_DIR = CONFIG_DIR / "hooks" / "damage-control"
LOGS_DIR = CONFIG_DIR / "logs" / "damage-control"
PATTERNS_FILE = HOOKS_DIR / "patterns.yaml"

# Files to install from the package
DAMAGE_CONTROL_FILES = [
    "patterns.yaml",
    "bash-tool-damage-control.py",
    "edit-tool-damage-control.py",
    "write-tool-damage-control.py",
    "audit_logger.py",
]


def get_damage_control_source() -> Path:
    """Get the path to the damage-control hooks in the installed package."""
    # First try: hooks/damage-control inside the agentwire package
    package_dir = Path(__file__).parent
    source_dir = package_dir / "hooks" / "damage-control"
    if source_dir.exists():
        return source_dir

    # Fallback: try importlib.resources (for installed packages)
    try:
        with importlib.resources.files("agentwire").joinpath("hooks/damage-control") as p:
            if p.exists():
                return Path(p)
    except (TypeError, FileNotFoundError):
        pass

    raise FileNotFoundError("Could not find damage-control hooks in package")


def is_glob_pattern(pattern: str) -> bool:
    """Check if a pattern contains glob wildcards."""
    return '*' in pattern or '?' in pattern or '[' in pattern


def glob_to_regex(pattern: str) -> str:
    """Convert a glob pattern to a regex pattern."""
    result = ""
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == '*':
            result += '.*'
        elif c == '?':
            result += '.'
        elif c == '[':
            j = i + 1
            while j < len(pattern) and pattern[j] != ']':
                j += 1
            result += pattern[i:j+1]
            i = j
        elif c in '.^$+{}|()\\':
            result += '\\' + c
        else:
            result += c
        i += 1
    return result


def matches_path_in_command(pattern: str, command: str) -> bool:
    """
    Check if a path pattern matches in the command in a file-path context.
    
    For glob patterns, we ensure we're matching file paths,
    not method calls like module.method().
    """
    expanded = os.path.expanduser(pattern)
    
    if not is_glob_pattern(pattern):
        # Non-glob: simple substring match (existing behavior)
        return expanded in command
    
    # Glob pattern: convert to regex and match in file-path contexts only
    glob_regex = glob_to_regex(expanded)
    
    # Only match in file-path contexts:
    # - Preceded by: space, /, =, ", ', <, >, or start of string
    # - Followed by: space, ", ', ), <, >, or end of string
    file_path_regex = r'(?:^|[\s/="\'<>])' + glob_regex + r'(?:[\s"\')<>]|$)'
    
    try:
        match = re.search(file_path_regex, command, re.IGNORECASE)
    except re.error:
        return False
    
    if not match:
        return False
    
    # Extra check: reject if it looks like a method call (preceded by identifier char and dot)
    # Method calls look like: module.method()
    extension = pattern.split('*')[-1] if '*' in pattern else pattern
    if extension.startswith('.'):
        extension = extension[1:]
    if extension:
        method_call_regex = r'\w\.' + re.escape(extension) + r'\s*\('
        if re.search(method_call_regex, command):
            return False
    
    return True


def load_patterns() -> Dict[str, Any]:
    """Load patterns from patterns.yaml."""
    if not yaml:
        print("Error: PyYAML not installed. Install with: pip install pyyaml", file=sys.stderr)
        return {}

    if not PATTERNS_FILE.exists():
        return {}

    try:
        with open(PATTERNS_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading patterns: {e}", file=sys.stderr)
        return {}


def check_command_safety(command: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Dry-run check if a command would be blocked/allowed/asked.

    Returns dict with:
        - decision: "allow" | "block" | "ask"
        - reason: string description
        - pattern: matched pattern (if any)
    """
    patterns = load_patterns()

    # Check bash tool patterns
    bash_patterns = patterns.get("bashToolPatterns", [])
    for pattern_obj in bash_patterns:
        if isinstance(pattern_obj, dict):
            pattern = pattern_obj.get("pattern", "")
            action = pattern_obj.get("action", "block")
            reason = pattern_obj.get("reason", "Matched pattern")
        else:
            continue

        try:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "decision": action,
                    "reason": reason,
                    "pattern": pattern,
                    "command": command
                }
        except re.error:
            if verbose:
                print(f"Warning: Invalid regex pattern: {pattern}", file=sys.stderr)

    # Check path-based restrictions (simplified check)
    zero_access = patterns.get("zeroAccessPaths", [])
    read_only = patterns.get("readOnlyPaths", [])
    no_delete = patterns.get("noDeletePaths", [])


    for path in zero_access:
        if matches_path_in_command(path, command):
            return {
                "decision": "block",
                "reason": f"Zero-access path: {path}",
                "pattern": f"zeroAccessPath: {path}",
                "command": command
            }

    for path in read_only:
        if matches_path_in_command(path, command) and any(op in command for op in ["rm", "mv", "sed -i", ">"]):
            return {
                "decision": "block",
                "reason": f"Read-only path: {path}",
                "pattern": f"readOnlyPath: {path}",
                "command": command
            }

    for path in no_delete:
        if matches_path_in_command(path, command) and "rm" in command:
            return {
                "decision": "block",
                "reason": f"No-delete path: {path}",
                "pattern": f"noDeletePath: {path}",
                "command": command
            }

    return {
        "decision": "allow",
        "reason": "No patterns matched",
        "pattern": None,
        "command": command
    }


def get_safety_status() -> Dict[str, Any]:
    """Get current safety status - patterns count, recent blocks, etc."""
    patterns = load_patterns()

    status = {
        "hooks_installed": HOOKS_DIR.exists(),
        "patterns_file": str(PATTERNS_FILE),
        "patterns_exist": PATTERNS_FILE.exists(),
        "logs_dir": str(LOGS_DIR),
        "logs_exist": LOGS_DIR.exists(),
        "pattern_counts": {
            "bash_patterns": len(patterns.get("bashToolPatterns", [])),
            "zero_access_paths": len(patterns.get("zeroAccessPaths", [])),
            "read_only_paths": len(patterns.get("readOnlyPaths", [])),
            "no_delete_paths": len(patterns.get("noDeletePaths", [])),
        },
        "recent_blocks": []
    }

    # Count recent blocks from today's log
    if LOGS_DIR.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"{today}.jsonl"
        if log_file.exists():
            try:
                blocks = []
                with open(log_file, "r") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get("decision") == "blocked":
                                blocks.append(entry)
                        except json.JSONDecodeError:
                            continue
                status["recent_blocks"] = blocks[-5:]  # Last 5 blocks
            except Exception as e:
                status["error"] = f"Error reading logs: {e}"

    return status


def query_audit_logs(
    tail: Optional[int] = None,
    session: Optional[str] = None,
    today: bool = False,
    pattern: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query audit logs with filters.

    Args:
        tail: Limit to last N entries
        session: Filter by session_id
        today: Only show today's entries
        pattern: Filter by pattern match (regex or substring)
    """
    if not LOGS_DIR.exists():
        return []

    entries = []

    # Determine which log files to read
    if today:
        log_files = [LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"]
    else:
        log_files = sorted(LOGS_DIR.glob("*.jsonl"), reverse=True)

    for log_file in log_files:
        if not log_file.exists():
            continue

        try:
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)

                        # Apply filters
                        if session and entry.get("session_id") != session:
                            continue

                        if pattern:
                            # Check if pattern matches command or blocked_by
                            cmd = entry.get("command", "")
                            blocked_by = entry.get("blocked_by", "")
                            if pattern.lower() not in cmd.lower() and pattern.lower() not in blocked_by.lower():
                                continue

                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    # Apply tail limit
    if tail:
        entries = entries[-tail:]

    return entries


def format_safety_status(status: Dict[str, Any]) -> str:
    """Format safety status for display."""
    lines = []
    lines.append("AgentWire Safety Status")
    lines.append("=" * 50)
    lines.append("")

    if not status["hooks_installed"]:
        lines.append("⚠️  Hooks not installed")
        lines.append(f"   Run: agentwire safety install")
        return "\n".join(lines)

    lines.append(f"✓ Hooks directory: {status['hooks_installed']}")
    lines.append(f"✓ Patterns file: {status['patterns_file']}")
    lines.append(f"  Exists: {status['patterns_exist']}")
    lines.append("")

    lines.append("Pattern Counts:")
    for name, count in status["pattern_counts"].items():
        lines.append(f"  • {name.replace('_', ' ').title()}: {count}")
    lines.append("")

    lines.append(f"Audit Logs: {status['logs_dir']}")
    lines.append(f"  Exists: {status['logs_exist']}")
    lines.append("")

    if status["recent_blocks"]:
        lines.append(f"Recent Blocks (last {len(status['recent_blocks'])}):")
        for block in status["recent_blocks"]:
            timestamp = block.get("timestamp", "unknown")
            cmd = block.get("command", "unknown")[:60]
            reason = block.get("blocked_by", "unknown")[:50]
            lines.append(f"  [{timestamp}] {cmd}")
            lines.append(f"    → {reason}")
        lines.append("")
    else:
        lines.append("No recent blocks found.")
        lines.append("")

    return "\n".join(lines)


def format_check_result(result: Dict[str, Any]) -> str:
    """Format check result for display."""
    decision = result["decision"]

    if decision == "allow":
        icon = "✓"
        color = "\033[32m"  # Green
    elif decision == "block":
        icon = "✗"
        color = "\033[31m"  # Red
    else:  # ask
        icon = "?"
        color = "\033[33m"  # Yellow

    reset = "\033[0m"

    lines = []
    lines.append(f"{color}{icon} Decision: {decision.upper()}{reset}")
    lines.append(f"  Reason: {result['reason']}")
    if result.get("pattern"):
        lines.append(f"  Pattern: {result['pattern']}")
    lines.append(f"  Command: {result['command']}")

    return "\n".join(lines)


def format_audit_logs(entries: List[Dict[str, Any]]) -> str:
    """Format audit log entries for display."""
    if not entries:
        return "No audit log entries found."

    lines = []
    lines.append(f"Audit Logs ({len(entries)} entries)")
    lines.append("=" * 80)
    lines.append("")

    for entry in entries:
        timestamp = entry.get("timestamp", "unknown")
        session = entry.get("session_id", "unknown")
        tool = entry.get("tool", "unknown")
        cmd = entry.get("command", "unknown")
        decision = entry.get("decision", "unknown")
        blocked_by = entry.get("blocked_by", "")

        # Color code by decision
        if decision == "blocked":
            color = "\033[31m"  # Red
        elif decision == "asked":
            color = "\033[33m"  # Yellow
        else:
            color = "\033[32m"  # Green
        reset = "\033[0m"

        lines.append(f"[{timestamp}] {color}{decision.upper()}{reset}")
        lines.append(f"  Session: {session}")
        lines.append(f"  Tool: {tool}")
        lines.append(f"  Command: {cmd[:100]}")
        if blocked_by:
            lines.append(f"  Blocked by: {blocked_by[:80]}")
        lines.append("")

    return "\n".join(lines)


def safety_check_cmd(command: str, verbose: bool = False) -> int:
    """CLI command: agentwire safety check"""
    result = check_command_safety(command, verbose)
    print(format_check_result(result))
    return 0 if result["decision"] == "allow" else 1


def safety_status_cmd() -> int:
    """CLI command: agentwire safety status"""
    status = get_safety_status()
    print(format_safety_status(status))
    return 0


def safety_logs_cmd(
    tail: Optional[int] = None,
    session: Optional[str] = None,
    today: bool = False,
    pattern: Optional[str] = None
) -> int:
    """CLI command: agentwire safety logs"""
    entries = query_audit_logs(tail, session, today, pattern)
    print(format_audit_logs(entries))
    return 0


def safety_install_cmd() -> int:
    """CLI command: agentwire safety install - interactive setup"""
    print("AgentWire Safety Installation")
    print("=" * 50)
    print()

    # Check if already installed
    if HOOKS_DIR.exists() and PATTERNS_FILE.exists():
        print("⚠️  Safety hooks already installed")
        print(f"   Location: {HOOKS_DIR}")
        response = input("Reinstall? [y/N] ").strip().lower()
        if response != "y":
            print("Installation cancelled.")
            return 0

    print("This will install damage control security hooks to:")
    print(f"  {HOOKS_DIR}")
    print()
    print("The hooks will:")
    print("  • Block dangerous commands (rm -rf /, etc.)")
    print("  • Protect sensitive files (.env, SSH keys, etc.)")
    print("  • Log all security decisions")
    print()

    response = input("Proceed with installation? [y/N] ").strip().lower()
    if response != "y":
        print("Installation cancelled.")
        return 0

    # Find source files in package
    try:
        source_dir = get_damage_control_source()
    except FileNotFoundError as e:
        print(f"\n⚠️  {e}")
        print("   The damage-control hooks are missing from the package.")
        return 1

    # Create directories
    print()
    print("Creating directories...")
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created {HOOKS_DIR}")
    print(f"✓ Created {LOGS_DIR}")

    # Copy files from package to user config
    print()
    print("Installing hooks...")
    for filename in DAMAGE_CONTROL_FILES:
        source_file = source_dir / filename
        target_file = HOOKS_DIR / filename
        if source_file.exists():
            shutil.copy2(source_file, target_file)
            # Make scripts executable
            if filename.endswith(".py"):
                target_file.chmod(0o755)
            print(f"✓ Installed {filename}")
        else:
            print(f"⚠️  Missing {filename} in package")

    print()
    print("✓ Installation complete!")
    print()
    print("Next steps:")
    print("  1. Test with: agentwire safety check 'rm -rf /'")
    print("  2. View status: agentwire safety status")
    print("  3. Configure patterns: edit ~/.agentwire/hooks/damage-control/patterns.yaml")

    return 0
