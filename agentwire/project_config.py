"""
Project-level configuration (.agentwire.yml).

This file lives in project directories and is the source of truth for session config.
"""

import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class SessionType(str, Enum):
    """Session type determines Claude execution mode."""
    BARE = "bare"                    # No Claude, just tmux session
    CLAUDE_BYPASS = "claude-bypass"  # Claude with --dangerously-skip-permissions
    CLAUDE_PROMPTED = "claude-prompted"  # Claude with permission hooks
    CLAUDE_RESTRICTED = "claude-restricted"  # Claude with only say allowed
    OPENCODE_BYPASS = "opencode-bypass"    # OpenCode with full permissions
    OPENCODE_PROMPTED = "opencode-prompted"  # OpenCode with permission prompts
    OPENCODE_RESTRICTED = "opencode-restricted"  # OpenCode worker (bash only)

    # Universal types (agent-agnostic, map to agent-specific types)
    STANDARD = "standard"  # Full automation -> claude-bypass or opencode-bypass
    WORKER = "worker"      # Worker pane -> claude-restricted or opencode-restricted
    VOICE = "voice"        # Voice with prompts -> claude-prompted or opencode-prompted

    @classmethod
    def from_str(cls, value: str) -> "SessionType":
        """Parse session type from string."""
        value = value.lower().replace("_", "-")
        try:
            return cls(value)
        except ValueError:
            return cls.CLAUDE_BYPASS  # Default for unknown types

    def to_cli_flags(self) -> list[str]:
        """Convert to CLI flags for Claude."""
        if self == SessionType.BARE:
            return []  # No Claude
        elif self == SessionType.CLAUDE_BYPASS:
            return ["--dangerously-skip-permissions"]
        elif self == SessionType.CLAUDE_PROMPTED:
            return []  # Uses permission hooks, no bypass
        elif self == SessionType.CLAUDE_RESTRICTED:
            return ["--tools", "Bash"]  # ONLY bash tool (for say command)
        return []


def detect_default_agent_type() -> str:
    """Detect which AI agent is installed from config or by checking PATH.

    Priority:
    1. Check ~/.agentwire/config.yaml for agent.command
    2. Use shutil.which() to detect installed agent
    3. Default to "claude" for backward compatibility

    Returns:
        "claude" or "opencode"
    """
    import yaml

    # Check config first
    config_path = Path.home() / ".agentwire" / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
                agent_command = config.get("agent", {}).get("command", "")
                if "claude" in agent_command:
                    return "claude"
                elif "opencode" in agent_command:
                    return "opencode"
        except Exception:
            pass

    # Detect from PATH
    if shutil.which("claude"):
        return "claude"
    elif shutil.which("opencode"):
        return "opencode"

    # Default for backward compatibility
    return "claude"


def normalize_session_type(session_type: str, agent_type: str) -> str:
    """Map universal session types to agent-specific types.

    Args:
        session_type: "standard", "worker", "voice", or agent-specific type
        agent_type: "claude" or "opencode"

    Returns:
        Agent-specific session type

    Examples:
        >>> normalize_session_type("standard", "claude")
        "claude-bypass"
        >>> normalize_session_type("worker", "opencode")
        "opencode-restricted"
    """
    # If already agent-specific, return as-is
    agent_specific_types = [
        "claude-bypass", "claude-prompted", "claude-restricted",
        "opencode-bypass", "opencode-prompted", "opencode-restricted",
        "bare"
    ]
    if session_type in agent_specific_types:
        return session_type

    # Map universal types to agent-specific
    if session_type == "standard":
        return f"{agent_type}-bypass"
    elif session_type == "worker":
        return f"{agent_type}-restricted"
    elif session_type == "voice":
        return f"{agent_type}-prompted"

    # Unknown type, default to standard
    return f"{agent_type}-bypass"


@dataclass
class ProjectConfig:
    """Project-level configuration for a project directory.

    Lives in .agentwire.yml in the project root.
    Shared by all sessions running in this project folder.
    Session name is NOT stored here - it's runtime context from environment.
    """
    type: SessionType = SessionType.CLAUDE_BYPASS
    roles: list[str] = field(default_factory=list)  # Composable roles
    voice: Optional[str] = None  # TTS voice

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        d = {
            "type": self.type.value,
        }
        if self.roles:
            d["roles"] = self.roles
        if self.voice:
            d["voice"] = self.voice
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        """Create ProjectConfig from dictionary."""
        type_value = data.get("type", "claude-bypass")
        roles = data.get("roles", [])
        voice = data.get("voice")

        return cls(
            type=SessionType.from_str(type_value) if isinstance(type_value, str) else type_value,
            roles=roles if isinstance(roles, list) else [roles] if roles else [],
            voice=voice,
        )


def find_project_config(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find .agentwire.yml by walking up from start_path.

    Args:
        start_path: Directory to start searching from. Defaults to cwd.

    Returns:
        Path to .agentwire.yml if found, None otherwise.
    """
    if start_path is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start_path).resolve()

    current = start_path
    while current != current.parent:
        config_file = current / ".agentwire.yml"
        if config_file.exists():
            return config_file
        current = current.parent

    # Check root
    config_file = current / ".agentwire.yml"
    if config_file.exists():
        return config_file

    return None


def load_project_config(path: Optional[Path] = None) -> Optional[ProjectConfig]:
    """Load project config from .agentwire.yml.

    Args:
        path: Path to .agentwire.yml or directory containing it.
              If None, searches from cwd upward.

    Returns:
        ProjectConfig if found and valid, None otherwise.
    """
    if path is None:
        config_path = find_project_config()
    elif path.is_dir():
        config_path = path / ".agentwire.yml"
    else:
        config_path = path

    if config_path is None or not config_path.exists():
        return None

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return ProjectConfig.from_dict(data)
    except Exception:
        return None


def save_project_config(config: ProjectConfig, project_dir: Path) -> bool:
    """Save project config to .agentwire.yml.

    Args:
        config: ProjectConfig to save
        project_dir: Directory to save config in

    Returns:
        True if saved successfully, False otherwise.
    """
    project_dir = Path(project_dir).resolve()
    config_file = project_dir / ".agentwire.yml"

    try:
        with open(config_file, "w") as f:
            yaml.safe_dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)
        return True
    except Exception:
        return False


def get_voice_from_config(project_path: Optional[Path] = None) -> Optional[str]:
    """Get voice from project config.

    Convenience function for say command.

    Args:
        project_path: Path to search from. Defaults to cwd.

    Returns:
        Voice name if config found and has voice, None otherwise.
    """
    config = load_project_config(project_path)
    return config.voice if config else None
