"""
AgentWire utility modules.

Provides shared functionality across the codebase:
- subprocess: Command execution with consistent error handling
- file_io: JSON/YAML loading and saving with error context
- paths: Centralized path management for ~/.agentwire/
"""

from agentwire.utils.file_io import load_json, load_yaml, save_json, save_yaml
from agentwire.utils.paths import (
    agentwire_dir,
    config_path,
    logs_dir,
    machines_path,
    uploads_dir,
    voices_dir,
)
from agentwire.utils.subprocess import run_command, run_command_check

__all__ = [
    # subprocess
    "run_command",
    "run_command_check",
    # file_io
    "load_json",
    "save_json",
    "load_yaml",
    "save_yaml",
    # paths
    "agentwire_dir",
    "config_path",
    "machines_path",
    "logs_dir",
    "voices_dir",
    "uploads_dir",
]
