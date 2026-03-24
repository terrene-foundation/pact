# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for environment configuration loading (M21: 2101-2103)."""

import pytest

from pact_platform.build.config.env import EnvConfig, EnvConfigError, load_env_config


class TestEnvConfig:
    """Test EnvConfig dataclass properties."""

    def test_default_values(self):
        cfg = EnvConfig()
        assert cfg.pact_api_token == ""
        assert cfg.pact_api_host == "0.0.0.0"
        assert cfg.pact_api_port == 8000
        assert cfg.pact_dev_mode is False
        assert cfg.is_production is True
        assert cfg.has_openai is False
        assert cfg.has_anthropic is False

    def test_is_production_when_dev_mode_false(self):
        cfg = EnvConfig(pact_dev_mode=False)
        assert cfg.is_production is True

    def test_is_not_production_when_dev_mode_true(self):
        cfg = EnvConfig(pact_dev_mode=True)
        assert cfg.is_production is False

    def test_has_openai_when_key_set(self):
        cfg = EnvConfig(openai_api_key="sk-test")
        assert cfg.has_openai is True

    def test_has_anthropic_when_key_set(self):
        cfg = EnvConfig(anthropic_api_key="sk-ant-test")
        assert cfg.has_anthropic is True

    def test_frozen_dataclass(self):
        cfg = EnvConfig()
        with pytest.raises(AttributeError):
            cfg.pact_api_token = "new-value"  # type: ignore[misc]


class TestLoadEnvConfig:
    """Test load_env_config function."""

    def test_production_mode_requires_token(self, monkeypatch):
        """Server should refuse to start without token in production mode."""
        monkeypatch.delenv("PACT_DEV_MODE", raising=False)
        monkeypatch.delenv("PACT_API_TOKEN", raising=False)
        with pytest.raises(EnvConfigError, match="PACT_API_TOKEN is required"):
            load_env_config(load_dotenv=False)

    def test_production_mode_with_token_succeeds(self, monkeypatch):
        """Server should start with token in production mode."""
        monkeypatch.setenv("PACT_API_TOKEN", "test-token-123")
        monkeypatch.delenv("PACT_DEV_MODE", raising=False)
        cfg = load_env_config(load_dotenv=False)
        assert cfg.pact_api_token == "test-token-123"
        assert cfg.is_production is True

    def test_dev_mode_without_token_succeeds(self, monkeypatch):
        """Server should start in dev mode without token."""
        monkeypatch.setenv("PACT_DEV_MODE", "true")
        monkeypatch.delenv("PACT_API_TOKEN", raising=False)
        cfg = load_env_config(load_dotenv=False)
        assert cfg.pact_dev_mode is True
        assert cfg.pact_api_token == ""

    def test_dev_mode_with_token_succeeds(self, monkeypatch):
        """Dev mode with token should work without warning."""
        monkeypatch.setenv("PACT_DEV_MODE", "true")
        monkeypatch.setenv("PACT_API_TOKEN", "dev-token")
        cfg = load_env_config(load_dotenv=False)
        assert cfg.pact_dev_mode is True
        assert cfg.pact_api_token == "dev-token"

    def test_reads_all_env_vars(self, monkeypatch):
        """All recognized environment variables should be read."""
        monkeypatch.setenv("PACT_API_TOKEN", "tok")
        monkeypatch.setenv("PACT_API_HOST", "127.0.0.1")
        monkeypatch.setenv("PACT_API_PORT", "9000")
        monkeypatch.setenv("PACT_CORS_ORIGINS", "http://a.com,http://b.com")
        monkeypatch.setenv("PACT_MAX_WS_SUBSCRIBERS", "100")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        monkeypatch.setenv("OPENAI_PROD_MODEL", "gpt-4o")
        monkeypatch.setenv("OPENAI_DEV_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        monkeypatch.setenv("DEFAULT_LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("DATABASE_URL", "postgresql://test")
        monkeypatch.setenv("REDIS_URL", "redis://test")
        monkeypatch.setenv("EATP_GENESIS_AUTHORITY", "test.authority")
        monkeypatch.setenv("EATP_CREDENTIAL_TTL_SECONDS", "600")
        monkeypatch.setenv("APP_ENV", "staging")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        cfg = load_env_config(load_dotenv=False)

        assert cfg.pact_api_token == "tok"
        assert cfg.pact_api_host == "127.0.0.1"
        assert cfg.pact_api_port == 9000
        assert cfg.pact_cors_origins == ["http://a.com", "http://b.com"]
        assert cfg.pact_max_ws_subscribers == 100
        assert cfg.openai_api_key == "sk-openai"
        assert cfg.openai_prod_model == "gpt-4o"
        assert cfg.openai_dev_model == "gpt-4o-mini"
        assert cfg.anthropic_api_key == "sk-ant"
        assert cfg.anthropic_model == "claude-sonnet-4-6"
        assert cfg.default_llm_model == "gpt-4o"
        assert cfg.database_url == "postgresql://test"
        assert cfg.redis_url == "redis://test"
        assert cfg.eatp_genesis_authority == "test.authority"
        assert cfg.eatp_credential_ttl_seconds == 600
        assert cfg.app_env == "staging"
        assert cfg.debug is True
        assert cfg.log_level == "DEBUG"

    def test_optional_vars_use_defaults(self, monkeypatch):
        """Missing optional vars should use documented defaults."""
        monkeypatch.setenv("PACT_DEV_MODE", "true")
        # Clear all optional vars
        for key in [
            "PACT_API_HOST",
            "PACT_API_PORT",
            "PACT_CORS_ORIGINS",
            "PACT_MAX_WS_SUBSCRIBERS",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "APP_ENV",
            "DEBUG",
            "LOG_LEVEL",
        ]:
            monkeypatch.delenv(key, raising=False)

        cfg = load_env_config(load_dotenv=False)
        assert cfg.pact_api_host == "0.0.0.0"
        assert cfg.pact_api_port == 8000
        assert cfg.pact_max_ws_subscribers == 50
        assert cfg.app_env == "development"
        assert cfg.debug is False
        assert cfg.log_level == "INFO"

    def test_invalid_port_uses_default(self, monkeypatch):
        """Invalid integer env vars should fall back to defaults."""
        monkeypatch.setenv("PACT_DEV_MODE", "true")
        monkeypatch.setenv("PACT_API_PORT", "not-a-number")
        cfg = load_env_config(load_dotenv=False)
        assert cfg.pact_api_port == 8000

    def test_boolean_parsing_variants(self, monkeypatch):
        """Boolean env vars should accept true/1/yes."""
        monkeypatch.setenv("PACT_API_TOKEN", "tok")
        for val in ("true", "True", "TRUE", "1", "yes", "YES"):
            monkeypatch.setenv("PACT_DEV_MODE", val)
            cfg = load_env_config(load_dotenv=False)
            assert cfg.pact_dev_mode is True, f"Failed for PACT_DEV_MODE={val}"

    def test_boolean_false_variants(self, monkeypatch):
        """Non-true boolean values should be False."""
        monkeypatch.setenv("PACT_API_TOKEN", "tok")
        for val in ("false", "0", "no", "anything-else"):
            monkeypatch.setenv("PACT_DEV_MODE", val)
            cfg = load_env_config(load_dotenv=False)
            assert cfg.pact_dev_mode is False, f"Failed for PACT_DEV_MODE={val}"
