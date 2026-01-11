"""
Project-level configuration (.agentwire.yml).

This file lives in project directories and is the source of truth for session config.
The portal's sessions.json is a runtime cache rebuilt from these files.
"""

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

    @classmethod
    def from_str(cls, value: str) -> "SessionType":
        """Parse session type from string."""
        value = value.lower().replace("_", "-")
        try:
            return cls(value)
        except ValueError:
            # Backwards compat: map old names
            if value == "orchestrator" or value == "agentwire":
                return cls.CLAUDE_BYPASS
            if value == "worker":
                return cls.CLAUDE_BYPASS
            return cls.CLAUDE_BYPASS  # Default

    def to_cli_flags(self) -> list[str]:
        """Convert to CLI flags for Claude."""
        if self == SessionType.BARE:
            return []  # No Claude
        elif self == SessionType.CLAUDE_BYPASS:
            return ["--dangerously-skip-permissions"]
        elif self == SessionType.CLAUDE_PROMPTED:
            return []  # Uses permission hooks, no bypass
        elif self == SessionType.CLAUDE_RESTRICTED:
            return ["--allowedTools", "Bash"]  # Only bash for say command
        return []


@dataclass
class ProjectConfig:
    """Project-level session configuration.

    Lives in .agentwire.yml in the project root.
    This is the source of truth for session config.
    """
    session: str  # tmux session name (required)
    type: SessionType = SessionType.CLAUDE_BYPASS
    roles: list[str] = field(default_factory=list)  # Composable roles
    voice: Optional[str] = None  # TTS voice

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        d = {
            "session": self.session,
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
        session = data.get("session", "")
        type_value = data.get("type", "claude-bypass")
        roles = data.get("roles", [])
        voice = data.get("voice")

        return cls(
            session=session,
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


def get_session_name_from_config(project_path: Optional[Path] = None) -> Optional[str]:
    """Get session name from project config.

    Convenience function for commands that need session context.

    Args:
        project_path: Path to search from. Defaults to cwd.

    Returns:
        Session name if config found, None otherwise.
    """
    config = load_project_config(project_path)
    return config.session if config else None


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
