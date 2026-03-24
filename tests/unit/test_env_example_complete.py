# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for Task 5028: .env.example completeness.

Validates that .env.example documents all environment variables
recognized by the PACT. Prevents configuration drift where
new env vars are added to code but not documented.
"""

from __future__ import annotations

import re
from pathlib import Path

# Project root — .env.example lives here
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_EXAMPLE = _PROJECT_ROOT / ".env.example"
_ENV_PY = _PROJECT_ROOT / "src" / "pact_platform" / "build" / "config" / "env.py"


def _parse_env_example_keys() -> set[str]:
    """Extract all environment variable names from .env.example.

    Handles commented and uncommented lines like:
        PACT_API_TOKEN=value
        # PACT_API_TOKEN=value
    """
    keys: set[str] = set()
    text = _ENV_EXAMPLE.read_text()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip leading comment marker(s) and whitespace
        uncommented = line.lstrip("# ").strip()
        if "=" in uncommented:
            key = uncommented.split("=", 1)[0].strip()
            # Only valid env var names
            if re.match(r"^[A-Z][A-Z0-9_]*$", key):
                keys.add(key)
    return keys


def _parse_env_py_keys() -> set[str]:
    """Extract all os.environ.get/os.environ[...] keys from env.py."""
    keys: set[str] = set()
    text = _ENV_PY.read_text()
    # Match os.environ.get("KEY", ...) and os.environ["KEY"]
    for match in re.finditer(r'os\.environ(?:\.get)?\(\s*["\']([A-Z][A-Z0-9_]*)["\']', text):
        keys.add(match.group(1))
    # Also match _bool_env("KEY") and _int_env("KEY")
    for match in re.finditer(r'_(?:bool|int)_env\(\s*["\']([A-Z][A-Z0-9_]*)["\']', text):
        keys.add(match.group(1))
    return keys


class TestEnvExampleExists:
    """Basic checks that .env.example is present and non-empty."""

    def test_env_example_file_exists(self):
        """.env.example must exist at the project root."""
        assert _ENV_EXAMPLE.is_file(), f"Missing .env.example at {_ENV_EXAMPLE}"

    def test_env_example_is_not_empty(self):
        """.env.example must have content."""
        content = _ENV_EXAMPLE.read_text().strip()
        assert len(content) > 0, ".env.example is empty"


class TestEnvExampleCompleteness:
    """Every env var used in env.py must appear in .env.example."""

    def test_all_env_py_keys_documented(self):
        """All keys from env.py should be documented in .env.example."""
        env_example_keys = _parse_env_example_keys()
        env_py_keys = _parse_env_py_keys()

        missing = env_py_keys - env_example_keys
        assert not missing, (
            f"Environment variables used in env.py but missing from .env.example: "
            f"{sorted(missing)}. Add them to .env.example so developers know about them."
        )

    def test_pact_api_token_documented(self):
        """PACT_API_TOKEN must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "PACT_API_TOKEN" in keys

    def test_pact_api_host_documented(self):
        """PACT_API_HOST must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "PACT_API_HOST" in keys

    def test_pact_api_port_documented(self):
        """PACT_API_PORT must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "PACT_API_PORT" in keys

    def test_pact_dev_mode_documented(self):
        """PACT_DEV_MODE must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "PACT_DEV_MODE" in keys

    def test_pact_log_format_documented(self):
        """PACT_LOG_FORMAT must be in .env.example (added by task 5024)."""
        keys = _parse_env_example_keys()
        assert "PACT_LOG_FORMAT" in keys

    def test_database_url_documented(self):
        """DATABASE_URL must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "DATABASE_URL" in keys

    def test_postgres_password_documented(self):
        """POSTGRES_PASSWORD must be in .env.example (used by docker-compose)."""
        keys = _parse_env_example_keys()
        assert "POSTGRES_PASSWORD" in keys

    def test_rate_limit_vars_documented(self):
        """PACT_RATE_LIMIT_GET and PACT_RATE_LIMIT_POST must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "PACT_RATE_LIMIT_GET" in keys
        assert "PACT_RATE_LIMIT_POST" in keys

    def test_eatp_vars_documented(self):
        """EATP config vars must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "EATP_GENESIS_AUTHORITY" in keys
        assert "EATP_CREDENTIAL_TTL_SECONDS" in keys

    def test_cors_origins_documented(self):
        """PACT_CORS_ORIGINS must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "PACT_CORS_ORIGINS" in keys

    def test_max_ws_subscribers_documented(self):
        """PACT_MAX_WS_SUBSCRIBERS must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "PACT_MAX_WS_SUBSCRIBERS" in keys

    def test_redis_url_documented(self):
        """REDIS_URL must be in .env.example."""
        keys = _parse_env_example_keys()
        assert "REDIS_URL" in keys
