# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Environment configuration — loads and validates all env vars at startup.

Provides a single ``load_env_config()`` function that returns a typed
``EnvConfig`` dataclass. Call this at the top of each entry point (server,
CLI, bootstrap) to fail-fast on missing required configuration.

Environment variables recognized by the CARE Platform:

| Variable                    | Required | Default                                      | Description                        |
|-----------------------------|----------|----------------------------------------------|------------------------------------|
| CARE_API_TOKEN              | No*      | ""                                           | Bearer token for API auth          |
| CARE_API_HOST               | No       | 0.0.0.0                                      | API server bind host               |
| CARE_API_PORT               | No       | 8000                                         | API server bind port               |
| CARE_CORS_ORIGINS           | No       | http://localhost:3000,http://localhost:3001   | Comma-separated CORS origins       |
| CARE_MAX_WS_SUBSCRIBERS     | No       | 50                                           | Max WebSocket subscribers          |
| CARE_DEV_MODE               | No       | false                                        | Allow empty API token if true      |
| CARE_RATE_LIMIT_GET         | No       | 60/minute                                    | Rate limit for GET requests        |
| CARE_RATE_LIMIT_POST        | No       | 10/minute                                    | Rate limit for POST requests       |
| OPENAI_API_KEY              | No       | ""                                           | OpenAI API key                     |
| OPENAI_PROD_MODEL           | No       | ""                                           | OpenAI production model name       |
| OPENAI_DEV_MODEL            | No       | ""                                           | OpenAI dev model name              |
| ANTHROPIC_API_KEY           | No       | ""                                           | Anthropic API key                  |
| ANTHROPIC_MODEL             | No       | ""                                           | Anthropic model name               |
| DEFAULT_LLM_MODEL           | No       | ""                                           | Fallback model name                |
| DATABASE_URL                | No       | ""                                           | PostgreSQL connection URL          |
| REDIS_URL                   | No       | ""                                           | Redis connection URL               |
| EATP_GENESIS_AUTHORITY      | No       | terrene.foundation                           | EATP genesis authority ID          |
| EATP_CREDENTIAL_TTL_SECONDS | No       | 300                                          | EATP credential TTL in seconds     |
| APP_ENV                     | No       | development                                  | Environment (development/staging/production) |
| DEBUG                       | No       | false                                        | Enable debug mode                  |
| LOG_LEVEL                   | No       | INFO                                         | Logging level                      |
| CARE_LOG_FORMAT             | No       | console                                      | Log output format (json or console)|

* CARE_API_TOKEN is required unless CARE_DEV_MODE=true.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Load .env file into os.environ if it exists.

    Searches for .env in the current working directory and up to 3 parent
    directories. Only sets variables not already present in os.environ.
    """
    # Walk upward from cwd to find .env
    search = Path.cwd()
    for _ in range(4):
        env_file = search / ".env"
        if env_file.is_file():
            _parse_env_file(env_file)
            return
        parent = search.parent
        if parent == search:
            break
        search = parent


def _parse_env_file(env_path: Path) -> None:
    """Parse a .env file and inject into os.environ (lightweight, no deps)."""
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        eq = line.find("=")
        if eq == -1:
            continue
        key = line[:eq].strip()
        val = line[eq + 1 :].strip()
        # Strip surrounding quotes
        is_quoted = (val.startswith('"') and val.endswith('"') and len(val) >= 2) or (
            val.startswith("'") and val.endswith("'") and len(val) >= 2
        )
        if is_quoted:
            val = val[1:-1]
        else:
            comment_idx = val.find(" #")
            if comment_idx > -1:
                val = val[:comment_idx].strip()
        if key not in os.environ:
            os.environ[key] = val


def _bool_env(key: str, default: bool = False) -> bool:
    """Parse a boolean env var (true/1/yes → True)."""
    val = os.environ.get(key, "").lower()
    if not val:
        return default
    return val in ("true", "1", "yes")


def _int_env(key: str, default: int) -> int:
    """Parse an integer env var with fallback."""
    val = os.environ.get(key, "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        logger.warning("Invalid integer for %s='%s', using default %d", key, val, default)
        return default


import re as _re

_RATE_LIMIT_RE = _re.compile(r"^\d+/(second|minute|hour|day)$")


def _validate_rate_limit(value: str, env_key: str) -> str:
    """RT12-015 / RT13: Validate rate limit format at startup (fail-fast).

    Expected format: ``<count>/<period>`` where period is one of
    second, minute, hour, day. Example: ``60/minute``.
    """
    if not _RATE_LIMIT_RE.match(value):
        raise EnvConfigError(
            f"Invalid rate limit format for {env_key}='{value}'. "
            f"Expected format: '<count>/<period>' where period is "
            f"second, minute, hour, or day. Example: '60/minute'."
        )
    return value


@dataclass(frozen=True)
class EnvConfig:
    """Typed, validated environment configuration for the CARE Platform."""

    # API
    care_api_token: str = ""
    care_api_host: str = "0.0.0.0"
    care_api_port: int = 8000
    care_cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"]
    )
    care_max_ws_subscribers: int = 50
    care_dev_mode: bool = False
    care_rate_limit_get: str = "60/minute"
    care_rate_limit_post: str = "10/minute"

    # LLM
    openai_api_key: str = ""
    openai_prod_model: str = ""
    openai_dev_model: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    default_llm_model: str = ""

    # Database
    database_url: str = ""
    redis_url: str = ""

    # EATP
    eatp_genesis_authority: str = "terrene.foundation"
    eatp_credential_ttl_seconds: int = 300

    # Application
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "console"

    @property
    def is_production(self) -> bool:
        """True when running in production mode (not dev mode)."""
        return not self.care_dev_mode

    @property
    def has_openai(self) -> bool:
        """True when OpenAI API key is configured."""
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        """True when Anthropic API key is configured."""
        return bool(self.anthropic_api_key)


class EnvConfigError(Exception):
    """Raised when environment configuration is invalid."""


def load_env_config(*, load_dotenv: bool = True) -> EnvConfig:
    """Load and validate environment configuration.

    Call this at the top of each entry point (server, CLI, bootstrap).

    Args:
        load_dotenv: Whether to load .env file first. Set to False in tests
            where env is already configured.

    Returns:
        Validated EnvConfig with all recognized environment variables.

    Raises:
        EnvConfigError: When required configuration is missing or invalid.
    """
    if load_dotenv:
        _load_dotenv()

    cors_raw = os.environ.get("CARE_CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
    cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

    config = EnvConfig(
        care_api_token=os.environ.get("CARE_API_TOKEN", ""),
        care_api_host=os.environ.get("CARE_API_HOST", "0.0.0.0"),
        care_api_port=_int_env("CARE_API_PORT", 8000),
        care_cors_origins=cors_origins,
        care_max_ws_subscribers=_int_env("CARE_MAX_WS_SUBSCRIBERS", 50),
        care_dev_mode=_bool_env("CARE_DEV_MODE"),
        care_rate_limit_get=_validate_rate_limit(
            os.environ.get("CARE_RATE_LIMIT_GET", "60/minute"), "CARE_RATE_LIMIT_GET"
        ),
        care_rate_limit_post=_validate_rate_limit(
            os.environ.get("CARE_RATE_LIMIT_POST", "10/minute"), "CARE_RATE_LIMIT_POST"
        ),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_prod_model=os.environ.get("OPENAI_PROD_MODEL", ""),
        openai_dev_model=os.environ.get("OPENAI_DEV_MODEL", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", ""),
        default_llm_model=os.environ.get("DEFAULT_LLM_MODEL", ""),
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", ""),
        eatp_genesis_authority=os.environ.get("EATP_GENESIS_AUTHORITY", "terrene.foundation"),
        eatp_credential_ttl_seconds=_int_env("EATP_CREDENTIAL_TTL_SECONDS", 300),
        app_env=os.environ.get("APP_ENV", "development"),
        debug=_bool_env("DEBUG"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        log_format=os.environ.get("CARE_LOG_FORMAT", "console"),
    )

    # Validate: CARE_API_TOKEN required in production mode
    if config.is_production and not config.care_api_token:
        raise EnvConfigError(
            "CARE_API_TOKEN is required in production mode. "
            "Set CARE_API_TOKEN to a secure token, or set CARE_DEV_MODE=true "
            "for local development (not recommended for production)."
        )

    if config.care_dev_mode and not config.care_api_token:
        logger.warning("Running in dev mode with no API token. Do not use in production.")

    return config
