"""
AgentWire configuration management.

Loads config from YAML file with sensible defaults and env var overrides.
"""

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def _expand_path(path: str | Path | None) -> Path | None:
    """Expand ~ and resolve path."""
    if path is None:
        return None
    return Path(path).expanduser().resolve()


@dataclass
class SSLConfig:
    """SSL certificate configuration."""

    cert: Path | None = None
    key: Path | None = None

    def __post_init__(self):
        self.cert = _expand_path(self.cert)
        self.key = _expand_path(self.key)

    @property
    def enabled(self) -> bool:
        """SSL is enabled if both cert and key exist."""
        return (
            self.cert is not None
            and self.key is not None
            and self.cert.exists()
            and self.key.exists()
        )


@dataclass
class ServerConfig:
    """WebSocket server configuration."""

    host: str = "0.0.0.0"
    port: int = 8765
    ssl: SSLConfig = field(default_factory=SSLConfig)


@dataclass
class WorktreesConfig:
    """Git worktrees configuration for parallel sessions."""

    enabled: bool = True
    suffix: str = "-worktrees"
    auto_create_branch: bool = True


@dataclass
class ProjectsConfig:
    """Projects directory configuration."""

    dir: Path = field(default_factory=lambda: Path.home() / "projects")
    worktrees: WorktreesConfig = field(default_factory=WorktreesConfig)

    def __post_init__(self):
        self.dir = _expand_path(self.dir) or Path.home() / "projects"


@dataclass
class TTSConfig:
    """Text-to-speech configuration."""

    backend: str = "chatterbox"  # chatterbox | elevenlabs | none
    url: str = "http://localhost:8100"
    default_voice: str = "bashbunni"


@dataclass
class STTConfig:
    """Speech-to-text configuration."""

    backend: str = field(default_factory=lambda: _default_stt_backend())
    model_path: Path | None = None
    language: str = "en"

    def __post_init__(self):
        self.model_path = _expand_path(self.model_path)


def _default_stt_backend() -> str:
    """Default STT backend based on platform."""
    if platform.system() == "Darwin":
        return "whisperkit"  # macOS - uses Apple Neural Engine
    return "openai"  # Linux/other - use OpenAI API


@dataclass
class AgentConfig:
    """Agent command configuration."""

    command: str = "claude --dangerously-skip-permissions"


@dataclass
class MachinesConfig:
    """Remote machines registry configuration."""

    file: Path = field(
        default_factory=lambda: Path.home() / ".agentwire" / "machines.json"
    )

    def __post_init__(self):
        self.file = _expand_path(self.file) or self.file


@dataclass
class RoomsConfig:
    """Room configurations file path."""

    file: Path = field(
        default_factory=lambda: Path.home() / ".agentwire" / "rooms.json"
    )

    def __post_init__(self):
        self.file = _expand_path(self.file) or self.file


@dataclass
class Config:
    """Root configuration for AgentWire."""

    server: ServerConfig = field(default_factory=ServerConfig)
    projects: ProjectsConfig = field(default_factory=ProjectsConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    machines: MachinesConfig = field(default_factory=MachinesConfig)
    rooms: RoomsConfig = field(default_factory=RoomsConfig)


def _merge_dict(base: dict, override: dict) -> dict:
    """Deep merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(data: dict) -> dict:
    """Apply environment variable overrides.

    Env vars use AGENTWIRE_ prefix with double underscore for nesting.
    Example: AGENTWIRE_SERVER__PORT=9000
    """
    prefix = "AGENTWIRE_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Parse key: AGENTWIRE_SERVER__PORT -> ["server", "port"]
        parts = key[len(prefix) :].lower().split("__")

        # Navigate to the right place in the dict
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the value (try to parse as int/bool/float)
        final_key = parts[-1]
        current[final_key] = _parse_env_value(value)

    return data


def _parse_env_value(value: str) -> str | int | float | bool:
    """Parse environment variable value to appropriate type."""
    # Boolean
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float
    try:
        return float(value)
    except ValueError:
        pass

    return value


def _dict_to_config(data: dict) -> Config:
    """Convert nested dict to Config dataclass."""
    # Server
    server_data = data.get("server", {})
    ssl_data = server_data.get("ssl", {})
    ssl = SSLConfig(
        cert=ssl_data.get("cert"),
        key=ssl_data.get("key"),
    )
    server = ServerConfig(
        host=server_data.get("host", "0.0.0.0"),
        port=server_data.get("port", 8765),
        ssl=ssl,
    )

    # Projects
    projects_data = data.get("projects", {})
    worktrees_data = projects_data.get("worktrees", {})
    worktrees = WorktreesConfig(
        enabled=worktrees_data.get("enabled", True),
        suffix=worktrees_data.get("suffix", "-worktrees"),
        auto_create_branch=worktrees_data.get("auto_create_branch", True),
    )
    projects = ProjectsConfig(
        dir=projects_data.get("dir", "~/projects"),
        worktrees=worktrees,
    )

    # TTS
    tts_data = data.get("tts", {})
    tts = TTSConfig(
        backend=tts_data.get("backend", "chatterbox"),
        url=tts_data.get("url", "http://localhost:8100"),
        default_voice=tts_data.get("default_voice", "bashbunni"),
    )

    # STT
    stt_data = data.get("stt", {})
    stt = STTConfig(
        backend=stt_data.get("backend", _default_stt_backend()),
        model_path=stt_data.get("model_path"),
        language=stt_data.get("language", "en"),
    )

    # Agent
    agent_data = data.get("agent", {})
    agent = AgentConfig(
        command=agent_data.get("command", "claude --dangerously-skip-permissions"),
    )

    # Machines
    machines_data = data.get("machines", {})
    machines = MachinesConfig(
        file=machines_data.get("file", "~/.agentwire/machines.json"),
    )

    # Rooms
    rooms_data = data.get("rooms", {})
    rooms = RoomsConfig(
        file=rooms_data.get("file", "~/.agentwire/rooms.json"),
    )

    return Config(
        server=server,
        projects=projects,
        tts=tts,
        stt=stt,
        agent=agent,
        machines=machines,
        rooms=rooms,
    )


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to ~/.agentwire/config.yaml

    Returns:
        Config object with all settings.

    Behavior:
        1. Starts with default values
        2. Merges config file if it exists
        3. Applies environment variable overrides
    """
    if config_path is None:
        config_path = Path.home() / ".agentwire" / "config.yaml"
    else:
        config_path = Path(config_path).expanduser().resolve()

    # Start with empty dict (defaults come from dataclasses)
    data: dict = {}

    # Load from file if it exists
    if config_path.exists():
        with open(config_path) as f:
            file_data = yaml.safe_load(f) or {}
            data = _merge_dict(data, file_data)

    # Apply environment variable overrides
    data = _apply_env_overrides(data)

    return _dict_to_config(data)


# Module-level config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global config instance (lazy loaded)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Optional[Path] = None) -> Config:
    """Reload configuration from disk."""
    global _config
    _config = load_config(config_path)
    return _config
