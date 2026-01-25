"""
File I/O utilities for JSON and YAML with consistent error handling.

Provides wrappers that:
- Handle missing files gracefully with defaults
- Provide clear error messages with file context
- Support atomic writes to prevent corruption
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import yaml


def load_json(path: Path | str, default: Optional[dict] = None) -> dict:
    """Load JSON file with optional default for missing files.

    Args:
        path: Path to JSON file.
        default: Value to return if file doesn't exist. None means raise.

    Returns:
        Parsed JSON as dict.

    Raises:
        FileNotFoundError: If file missing and no default provided.
        json.JSONDecodeError: If file contains invalid JSON.

    Example:
        config = load_json(config_path, default={})
    """
    path = Path(path)

    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"JSON file not found: {path}")

    with open(path, "r") as f:
        return json.load(f)


def save_json(
    path: Path | str,
    data: dict | list,
    indent: int = 2,
    atomic: bool = True,
) -> None:
    """Save data to JSON file.

    Args:
        path: Path to JSON file.
        data: Data to serialize.
        indent: JSON indentation (default 2).
        atomic: Write to temp file then rename (prevents corruption).

    Example:
        save_json(config_path, {"version": 1})
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if atomic:
        # Write to temp file then atomic rename
        fd, temp_path = tempfile.mkstemp(
            suffix=".json",
            dir=path.parent,
        )
        try:
            with open(fd, "w") as f:
                json.dump(data, f, indent=indent)
            shutil.move(temp_path, path)
        except Exception:
            # Clean up temp file on error
            Path(temp_path).unlink(missing_ok=True)
            raise
    else:
        with open(path, "w") as f:
            json.dump(data, f, indent=indent)


def load_yaml(path: Path | str, default: Optional[dict] = None) -> dict:
    """Load YAML file with optional default for missing files.

    Args:
        path: Path to YAML file.
        default: Value to return if file doesn't exist. None means raise.

    Returns:
        Parsed YAML as dict.

    Raises:
        FileNotFoundError: If file missing and no default provided.
        yaml.YAMLError: If file contains invalid YAML.

    Example:
        config = load_yaml(Path("~/.agentwire/config.yaml").expanduser())
    """
    path = Path(path)

    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"YAML file not found: {path}")

    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def save_yaml(
    path: Path | str,
    data: dict,
    atomic: bool = True,
) -> None:
    """Save data to YAML file.

    Args:
        path: Path to YAML file.
        data: Data to serialize.
        atomic: Write to temp file then rename (prevents corruption).

    Example:
        save_yaml(config_path, {"server": {"port": 8765}})
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if atomic:
        fd, temp_path = tempfile.mkstemp(
            suffix=".yaml",
            dir=path.parent,
        )
        try:
            with open(fd, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            shutil.move(temp_path, path)
        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise
    else:
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
