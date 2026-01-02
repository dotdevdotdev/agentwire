"""
AgentWire configuration management.

Loads config from YAML file with sensible defaults and env var overrides.
"""

from __future__ import annotations

import logging
import os
import platform
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import yaml

if TYPE_CHECKING:
    from agentwire.watcher import Trigger

logger = logging.getLogger(__name__)


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
class UploadsConfig:
    """Uploads directory for images shared across machines."""

    dir: Path = field(
        default_factory=lambda: Path.home() / ".agentwire" / "uploads"
    )
    max_size_mb: int = 10
    cleanup_days: int = 7

    def __post_init__(self):
        self.dir = _expand_path(self.dir) or self.dir


@dataclass
class PortalConfig:
    """Portal connection settings (for remote machines)."""

    url: str = "https://localhost:8765"  # URL to reach the portal


@dataclass
class TriggerConfig:
    """Configuration for a single trigger.

    Triggers watch tmux output and fire actions when patterns match.

    Attributes:
        pattern: Regex pattern string to match against output.
        mode: "transient" matches each chunk as it arrives,
              "persistent" matches against accumulated buffer.
        action: Action to fire on match (tts, popup, notify, sound, send_keys, broadcast).
        enabled: Whether this trigger is active.
        template: Template string for action (e.g., TTS text with {group} substitutions).
        title: Title for popup/notify actions.
        body: Body text for popup/notify actions.
        keys: Keys to send for send_keys action.
        on: For persistent mode: "appear", "disappear", or "both".
    """

    pattern: str
    mode: str = "transient"
    action: str = "tts"
    enabled: bool = True
    template: str | None = None
    title: str | None = None
    body: str | None = None
    keys: str | None = None
    on: str = "appear"
    sound: str | None = None  # For sound action
    type: str | None = None   # For broadcast action (message type)
    data: str | None = None   # For broadcast action (data payload)


# Built-in trigger patterns
_SAY_PATTERN = r'(?:remote-)?say\s+(?:"([^"]+)"|\'([^\']+)\')'
_ASK_PATTERN = (
    r'\s*☐\s+(?P<header>.+?)\s*\n\s*\n'
    r'(?P<question>.+?\?)\s*\n\s*\n'
    r'(?P<options_block>(?:[❯\s]+\d+\.\s+.+\n(?:\s{3,}.+\n)?)+)'
)


@dataclass
class TriggersConfig:
    """Triggers configuration section.

    Contains built-in triggers (always present, can be disabled) and
    user-defined custom triggers loaded from config.

    Attributes:
        say_command: Built-in trigger for `say "text"` commands.
        ask_question: Built-in trigger for AskUserQuestion UI.
        custom: User-defined triggers keyed by name.
    """

    say_command: TriggerConfig = field(
        default_factory=lambda: TriggerConfig(
            pattern=_SAY_PATTERN,
            action="tts",
        )
    )
    ask_question: TriggerConfig = field(
        default_factory=lambda: TriggerConfig(
            pattern=_ASK_PATTERN,
            mode="persistent",
            action="popup",
        )
    )
    custom: dict[str, TriggerConfig] = field(default_factory=dict)

    def to_triggers(self) -> list[Trigger]:
        """Convert config to list of Trigger objects.

        Returns:
            List of Trigger objects for use with SessionWatcher.
        """
        from agentwire.watcher import Trigger

        triggers: list[Trigger] = []

        # Built-in: say_command
        if self.say_command.enabled:
            try:
                triggers.append(
                    Trigger(
                        name="say_command",
                        pattern=re.compile(self.say_command.pattern),
                        mode="transient",
                        action=self.say_command.action,
                        config=_trigger_config_to_dict(self.say_command),
                        enabled=True,
                        builtin=True,
                    )
                )
            except re.error as e:
                logger.warning(f"Invalid pattern for say_command: {e}")

        # Built-in: ask_question
        if self.ask_question.enabled:
            try:
                triggers.append(
                    Trigger(
                        name="ask_question",
                        pattern=re.compile(self.ask_question.pattern),
                        mode="persistent",
                        action=self.ask_question.action,
                        config=_trigger_config_to_dict(self.ask_question),
                        enabled=True,
                        builtin=True,
                    )
                )
            except re.error as e:
                logger.warning(f"Invalid pattern for ask_question: {e}")

        # Custom triggers
        for name, cfg in self.custom.items():
            if not cfg.enabled:
                continue
            try:
                triggers.append(
                    Trigger(
                        name=name,
                        pattern=re.compile(cfg.pattern),
                        mode=cfg.mode if cfg.mode in ("transient", "persistent") else "transient",
                        action=cfg.action,
                        config=_trigger_config_to_dict(cfg),
                        enabled=True,
                        builtin=False,
                    )
                )
            except re.error as e:
                logger.warning(f"Invalid pattern for trigger '{name}': {e}")

        return triggers


def _trigger_config_to_dict(cfg: TriggerConfig) -> dict[str, Any]:
    """Extract action-specific config from TriggerConfig.

    Args:
        cfg: The trigger configuration.

    Returns:
        Dict with non-None action-specific fields.
    """
    result: dict[str, Any] = {}
    if cfg.template is not None:
        result["template"] = cfg.template
    if cfg.title is not None:
        result["title"] = cfg.title
    if cfg.body is not None:
        result["body"] = cfg.body
    if cfg.keys is not None:
        result["keys"] = cfg.keys
    if cfg.on != "appear":
        result["on"] = cfg.on
    if cfg.sound is not None:
        result["sound"] = cfg.sound
    if cfg.type is not None:
        result["type"] = cfg.type
    if cfg.data is not None:
        result["data"] = cfg.data
    return result


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
    uploads: UploadsConfig = field(default_factory=UploadsConfig)
    portal: PortalConfig = field(default_factory=PortalConfig)
    triggers: TriggersConfig = field(default_factory=TriggersConfig)


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


def _parse_trigger_config(data: dict) -> TriggerConfig:
    """Parse a single trigger config from dict.

    Args:
        data: Dict with trigger configuration.

    Returns:
        TriggerConfig instance.
    """
    return TriggerConfig(
        pattern=data.get("pattern", ""),
        mode=data.get("mode", "transient"),
        action=data.get("action", "tts"),
        enabled=data.get("enabled", True),
        template=data.get("template"),
        title=data.get("title"),
        body=data.get("body"),
        keys=data.get("keys"),
        on=data.get("on", "appear"),
        sound=data.get("sound"),
        type=data.get("type"),
        data=data.get("data"),
    )


def _parse_triggers_config(data: dict) -> TriggersConfig:
    """Parse the triggers section from config dict.

    Args:
        data: Dict with triggers configuration.

    Returns:
        TriggersConfig instance with built-in and custom triggers.
    """
    # Parse built-in trigger overrides
    say_command_data = data.get("say_command", {})
    ask_question_data = data.get("ask_question", {})

    # Create built-in configs, merging with defaults
    say_command = TriggerConfig(
        pattern=say_command_data.get("pattern", _SAY_PATTERN),
        mode="transient",  # Always transient for say
        action=say_command_data.get("action", "tts"),
        enabled=say_command_data.get("enabled", True),
        template=say_command_data.get("template"),
        title=say_command_data.get("title"),
        body=say_command_data.get("body"),
        keys=say_command_data.get("keys"),
        on="appear",
    )

    ask_question = TriggerConfig(
        pattern=ask_question_data.get("pattern", _ASK_PATTERN),
        mode="persistent",  # Always persistent for ask
        action=ask_question_data.get("action", "popup"),
        enabled=ask_question_data.get("enabled", True),
        template=ask_question_data.get("template"),
        title=ask_question_data.get("title"),
        body=ask_question_data.get("body"),
        keys=ask_question_data.get("keys"),
        on=ask_question_data.get("on", "appear"),
    )

    # Parse custom triggers (everything except built-in names)
    builtin_names = {"say_command", "ask_question"}
    custom: dict[str, TriggerConfig] = {}

    for name, trigger_data in data.items():
        if name in builtin_names:
            continue
        if not isinstance(trigger_data, dict):
            continue
        if "pattern" not in trigger_data:
            logger.warning(f"Skipping trigger '{name}': missing pattern")
            continue

        custom[name] = _parse_trigger_config(trigger_data)

    return TriggersConfig(
        say_command=say_command,
        ask_question=ask_question,
        custom=custom,
    )


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

    # Uploads
    uploads_data = data.get("uploads", {})
    uploads = UploadsConfig(
        dir=uploads_data.get("dir", "~/.agentwire/uploads"),
        max_size_mb=uploads_data.get("max_size_mb", 10),
        cleanup_days=uploads_data.get("cleanup_days", 7),
    )

    # Portal
    portal_data = data.get("portal", {})
    portal = PortalConfig(
        url=portal_data.get("url", "https://localhost:8765"),
    )

    # Triggers
    triggers = _parse_triggers_config(data.get("triggers", {}))

    return Config(
        server=server,
        projects=projects,
        tts=tts,
        stt=stt,
        agent=agent,
        machines=machines,
        rooms=rooms,
        uploads=uploads,
        portal=portal,
        triggers=triggers,
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
