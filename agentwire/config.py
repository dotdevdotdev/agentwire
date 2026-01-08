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
    activity_threshold_seconds: float = 10.0  # Time in seconds before session is considered idle


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

    backend: str = "chatterbox"  # chatterbox | runpod | none
    url: str = "http://localhost:8100"
    default_voice: str = "bashbunni"
    # Voice parameters (applies to all backends)
    exaggeration: float = 0.5
    cfg_weight: float = 0.5
    # RunPod serverless configuration
    runpod_endpoint_id: str = ""
    runpod_api_key: str = ""
    runpod_timeout: int = 60


@dataclass
class STTConfig:
    """Speech-to-text configuration."""

    backend: str = field(default_factory=lambda: _default_stt_backend())
    model_path: Path | None = None
    language: str = "en"
    # Remote STT server configuration
    url: str = "http://localhost:8100"
    timeout: int = 30

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
class TemplatesConfig:
    """Session templates configuration."""

    dir: Path = field(
        default_factory=lambda: Path.home() / ".agentwire" / "templates"
    )

    def __post_init__(self):
        self.dir = _expand_path(self.dir) or self.dir


@dataclass
class Template:
    """A session template with pre-configured settings.

    Stored as YAML files in ~/.agentwire/templates/
    """

    name: str
    description: str = ""
    role: str | None = None  # Role file from ~/.agentwire/roles/
    voice: str | None = None  # TTS voice
    project: str | None = None  # Default project path
    initial_prompt: str = ""  # Context sent to Claude on session start
    bypass_permissions: bool = True  # Permission mode
    restricted: bool = False  # Restricted mode

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        d = {
            "name": self.name,
            "description": self.description,
            "initial_prompt": self.initial_prompt,
            "bypass_permissions": self.bypass_permissions,
            "restricted": self.restricted,
        }
        if self.role:
            d["role"] = self.role
        if self.voice:
            d["voice"] = self.voice
        if self.project:
            d["project"] = self.project
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Template":
        """Create Template from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            role=data.get("role"),
            voice=data.get("voice"),
            project=data.get("project"),
            initial_prompt=data.get("initial_prompt", ""),
            bypass_permissions=data.get("bypass_permissions", True),
            restricted=data.get("restricted", False),
        )

    def expand_variables(self, variables: dict[str, str]) -> str:
        """Expand template variables in the initial prompt.

        Supported variables:
        - {{project_name}} - Name of the project/session
        - {{branch}} - Current git branch
        - {{machine}} - Machine ID if remote
        """
        prompt = self.initial_prompt
        for key, value in variables.items():
            prompt = prompt.replace(f"{{{{{key}}}}}", value or "")
        return prompt


@dataclass
class PortalConfig:
    """Portal connection settings (for remote machines)."""

    url: str = "https://localhost:8765"  # URL to reach the portal


@dataclass
class ServiceConfig:
    """Configuration for a single service location."""

    machine: Optional[str] = None  # None = local, or machine ID from machines.json
    port: int = 8765
    health_endpoint: str = "/health"
    scheme: str = "http"  # http or https


@dataclass
class ServicesConfig:
    """Where each service runs in the network."""

    portal: ServiceConfig = field(default_factory=lambda: ServiceConfig(port=8765, scheme="https"))
    tts: ServiceConfig = field(default_factory=lambda: ServiceConfig(port=8100, scheme="http"))


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
    services: ServicesConfig = field(default_factory=ServicesConfig)
    templates: TemplatesConfig = field(default_factory=TemplatesConfig)


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
        activity_threshold_seconds=server_data.get("activity_threshold_seconds", 10.0),
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
        runpod_endpoint_id=tts_data.get("runpod_endpoint_id", ""),
        runpod_api_key=tts_data.get("runpod_api_key", ""),
        runpod_timeout=tts_data.get("runpod_timeout", 60),
    )

    # STT
    stt_data = data.get("stt", {})
    stt = STTConfig(
        backend=stt_data.get("backend", _default_stt_backend()),
        model_path=stt_data.get("model_path"),
        language=stt_data.get("language", "en"),
        url=stt_data.get("url", "http://localhost:8100"),
        timeout=stt_data.get("timeout", 30),
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

    # Services (network service locations)
    services_data = data.get("services", {})
    portal_service_data = services_data.get("portal", {})
    tts_service_data = services_data.get("tts", {})
    portal_service = ServiceConfig(
        machine=portal_service_data.get("machine"),
        port=portal_service_data.get("port", 8765),
        health_endpoint=portal_service_data.get("health_endpoint", "/health"),
        scheme=portal_service_data.get("scheme", "https"),  # Portal defaults to HTTPS
    )
    tts_service = ServiceConfig(
        machine=tts_service_data.get("machine"),
        port=tts_service_data.get("port", 8100),
        health_endpoint=tts_service_data.get("health_endpoint", "/health"),
        scheme=tts_service_data.get("scheme", "http"),  # TTS defaults to HTTP
    )
    services = ServicesConfig(
        portal=portal_service,
        tts=tts_service,
    )

    # Templates
    templates_data = data.get("templates", {})
    templates = TemplatesConfig(
        dir=templates_data.get("dir", "~/.agentwire/templates"),
    )

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
        services=services,
        templates=templates,
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

    # Debug logging for STT config
    import logging
    logger = logging.getLogger(__name__)
    if 'stt' in data:
        logger.info(f"STT config after env overrides: {data['stt']}")

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


# =============================================================================
# Template Management Functions
# =============================================================================


def load_templates(templates_dir: Optional[Path] = None) -> list[Template]:
    """Load all templates from the templates directory.

    Args:
        templates_dir: Path to templates directory. Defaults to config's templates.dir

    Returns:
        List of Template objects sorted by name.
    """
    if templates_dir is None:
        templates_dir = get_config().templates.dir

    templates_dir = Path(templates_dir).expanduser().resolve()

    if not templates_dir.exists():
        return []

    templates = []
    for file_path in templates_dir.glob("*.yaml"):
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f) or {}
            # Ensure name matches filename if not specified
            if not data.get("name"):
                data["name"] = file_path.stem
            templates.append(Template.from_dict(data))
        except Exception:
            # Skip invalid template files
            continue

    return sorted(templates, key=lambda t: t.name)


def load_template(name: str, templates_dir: Optional[Path] = None) -> Optional[Template]:
    """Load a specific template by name.

    Args:
        name: Template name (without .yaml extension)
        templates_dir: Path to templates directory. Defaults to config's templates.dir

    Returns:
        Template object if found, None otherwise.
    """
    if templates_dir is None:
        templates_dir = get_config().templates.dir

    templates_dir = Path(templates_dir).expanduser().resolve()
    template_file = templates_dir / f"{name}.yaml"

    if not template_file.exists():
        return None

    try:
        with open(template_file) as f:
            data = yaml.safe_load(f) or {}
        if not data.get("name"):
            data["name"] = name
        return Template.from_dict(data)
    except Exception:
        return None


def save_template(template: Template, templates_dir: Optional[Path] = None) -> bool:
    """Save a template to disk.

    Args:
        template: Template object to save
        templates_dir: Path to templates directory. Defaults to config's templates.dir

    Returns:
        True if saved successfully, False otherwise.
    """
    if templates_dir is None:
        templates_dir = get_config().templates.dir

    templates_dir = Path(templates_dir).expanduser().resolve()
    templates_dir.mkdir(parents=True, exist_ok=True)

    template_file = templates_dir / f"{template.name}.yaml"

    try:
        with open(template_file, "w") as f:
            yaml.safe_dump(template.to_dict(), f, default_flow_style=False, sort_keys=False)
        return True
    except Exception:
        return False


def delete_template(name: str, templates_dir: Optional[Path] = None) -> bool:
    """Delete a template from disk.

    Args:
        name: Template name (without .yaml extension)
        templates_dir: Path to templates directory. Defaults to config's templates.dir

    Returns:
        True if deleted successfully, False otherwise.
    """
    if templates_dir is None:
        templates_dir = get_config().templates.dir

    templates_dir = Path(templates_dir).expanduser().resolve()
    template_file = templates_dir / f"{name}.yaml"

    if not template_file.exists():
        return False

    try:
        template_file.unlink()
        return True
    except Exception:
        return False
