# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Configuration loader — loads and validates CARE Platform YAML config files."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from care_platform.config.schema import PlatformConfig


class ConfigError(Exception):
    """Raised when configuration is invalid."""


def load_config(path: str | Path) -> PlatformConfig:
    """Load and validate a CARE Platform configuration file.

    Args:
        path: Path to a YAML configuration file.

    Returns:
        Validated PlatformConfig object.

    Raises:
        ConfigError: If the file cannot be read or the config is invalid.
    """
    config_path = Path(path)

    if not config_path.exists():
        msg = f"Configuration file not found: {config_path}"
        raise ConfigError(msg)

    if config_path.suffix not in (".yml", ".yaml"):
        msg = f"Configuration file must be .yml or .yaml, got: {config_path.suffix}"
        raise ConfigError(msg)

    try:
        raw = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as e:
        msg = f"Invalid YAML in {config_path}: {e}"
        raise ConfigError(msg) from e

    if not isinstance(raw, dict):
        msg = f"Configuration must be a YAML mapping, got {type(raw).__name__}"
        raise ConfigError(msg)

    try:
        return PlatformConfig(**raw)
    except ValidationError as e:
        errors = []
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            errors.append(f"  {loc}: {err['msg']}")
        msg = "Configuration validation failed:\n" + "\n".join(errors)
        raise ConfigError(msg) from e


def load_config_from_dict(data: dict) -> PlatformConfig:
    """Load and validate a CARE Platform configuration from a dictionary.

    Args:
        data: Configuration dictionary (e.g., from parsed YAML).

    Returns:
        Validated PlatformConfig object.

    Raises:
        ConfigError: If the config is invalid.
    """
    try:
        return PlatformConfig(**data)
    except ValidationError as e:
        errors = []
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            errors.append(f"  {loc}: {err['msg']}")
        msg = "Configuration validation failed:\n" + "\n".join(errors)
        raise ConfigError(msg) from e
