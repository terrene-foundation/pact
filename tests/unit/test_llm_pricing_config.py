# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for L10: LLM pricing moved to configuration.

Validates that pricing dictionaries in OpenAI and Anthropic backends can
be overridden via the PACT_LLM_PRICING_JSON environment variable, with
sensible defaults when the variable is not set.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

# Skip entire module if anthropic SDK is not installed (not in CI deps)
pytest.importorskip("anthropic", reason="anthropic SDK not installed")


class TestOpenAIPricingConfig:
    """L10: OpenAI backend pricing is configurable via env var."""

    def test_default_pricing_exists(self):
        """Default pricing should be present for known models."""
        from pact_platform.use.execution.backends.openai_backend import _OPENAI_PRICING

        assert "gpt-4o" in _OPENAI_PRICING
        assert "gpt-4o-mini" in _OPENAI_PRICING

    def test_default_pricing_values_match_original(self):
        """Default pricing values should match the original hardcoded values."""
        from pact_platform.use.execution.backends.openai_backend import _OPENAI_PRICING

        input_price, output_price = _OPENAI_PRICING["gpt-4o"]
        expected_input = Decimal("2.5") / Decimal("1000000")
        expected_output = Decimal("10") / Decimal("1000000")
        assert input_price == expected_input
        assert output_price == expected_output

    def test_env_override_replaces_pricing(self, monkeypatch):
        """PACT_LLM_PRICING_JSON should override pricing when set."""
        custom_pricing = {
            "openai": {
                "custom-model": {
                    "input": "5.0",
                    "output": "20.0",
                }
            }
        }
        monkeypatch.setenv("PACT_LLM_PRICING_JSON", json.dumps(custom_pricing))

        # Re-import to pick up the env var
        import importlib

        import pact_platform.use.execution.backends.openai_backend as mod

        importlib.reload(mod)

        try:
            assert "custom-model" in mod._OPENAI_PRICING
            input_price, output_price = mod._OPENAI_PRICING["custom-model"]
            assert input_price == Decimal("5.0") / Decimal("1000000")
            assert output_price == Decimal("20.0") / Decimal("1000000")
        finally:
            # Reload without env var to restore defaults
            monkeypatch.delenv("PACT_LLM_PRICING_JSON", raising=False)
            importlib.reload(mod)

    def test_env_override_invalid_json_uses_defaults(self, monkeypatch):
        """Invalid JSON in PACT_LLM_PRICING_JSON should use defaults."""
        monkeypatch.setenv("PACT_LLM_PRICING_JSON", "not-valid-json{")

        import importlib

        import pact_platform.use.execution.backends.openai_backend as mod

        importlib.reload(mod)

        try:
            # Should still have the default pricing
            assert "gpt-4o" in mod._OPENAI_PRICING
        finally:
            monkeypatch.delenv("PACT_LLM_PRICING_JSON", raising=False)
            importlib.reload(mod)

    def test_estimate_cost_uses_pricing(self):
        """estimate_cost should use the configured pricing dict."""
        from pact_platform.build.config.env import EnvConfig
        from pact_platform.use.execution.backends.openai_backend import OpenAIBackend
        from pact_platform.use.execution.llm_backend import LLMResponse

        cfg = EnvConfig(pact_dev_mode=True, openai_api_key="test-key")
        backend = OpenAIBackend(cfg)

        response = LLMResponse(
            content="test",
            model="gpt-4o",
            provider="openai",
            input_tokens=1000,
            output_tokens=500,
            tool_calls=[],
            finish_reason="stop",
        )
        cost = backend.estimate_cost(response)
        assert cost > Decimal("0")


class TestAnthropicPricingConfig:
    """L10: Anthropic backend pricing is configurable via env var."""

    def test_default_pricing_exists(self):
        """Default pricing should be present for known models."""
        from pact_platform.use.execution.backends.anthropic_backend import _ANTHROPIC_PRICING

        assert "claude-sonnet-4" in _ANTHROPIC_PRICING
        assert "claude-opus-4" in _ANTHROPIC_PRICING

    def test_default_pricing_values_match_original(self):
        """Default pricing values should match the original hardcoded values."""
        from pact_platform.use.execution.backends.anthropic_backend import _ANTHROPIC_PRICING

        input_price, output_price = _ANTHROPIC_PRICING["claude-sonnet-4"]
        expected_input = Decimal("3") / Decimal("1000000")
        expected_output = Decimal("15") / Decimal("1000000")
        assert input_price == expected_input
        assert output_price == expected_output

    def test_env_override_replaces_pricing(self, monkeypatch):
        """PACT_LLM_PRICING_JSON should override Anthropic pricing when set."""
        custom_pricing = {
            "anthropic": {
                "claude-custom": {
                    "input": "10.0",
                    "output": "50.0",
                }
            }
        }
        monkeypatch.setenv("PACT_LLM_PRICING_JSON", json.dumps(custom_pricing))

        import importlib

        import pact_platform.use.execution.backends.anthropic_backend as mod

        importlib.reload(mod)

        try:
            assert "claude-custom" in mod._ANTHROPIC_PRICING
            input_price, output_price = mod._ANTHROPIC_PRICING["claude-custom"]
            assert input_price == Decimal("10.0") / Decimal("1000000")
            assert output_price == Decimal("50.0") / Decimal("1000000")
        finally:
            monkeypatch.delenv("PACT_LLM_PRICING_JSON", raising=False)
            importlib.reload(mod)

    def test_env_override_invalid_json_uses_defaults(self, monkeypatch):
        """Invalid JSON in PACT_LLM_PRICING_JSON should use defaults."""
        monkeypatch.setenv("PACT_LLM_PRICING_JSON", "not-valid-json{")

        import importlib

        import pact_platform.use.execution.backends.anthropic_backend as mod

        importlib.reload(mod)

        try:
            assert "claude-sonnet-4" in mod._ANTHROPIC_PRICING
        finally:
            monkeypatch.delenv("PACT_LLM_PRICING_JSON", raising=False)
            importlib.reload(mod)

    def test_estimate_cost_uses_pricing(self):
        """estimate_cost should use the configured pricing dict."""
        from pact_platform.build.config.env import EnvConfig
        from pact_platform.use.execution.backends.anthropic_backend import AnthropicBackend
        from pact_platform.use.execution.llm_backend import LLMResponse

        cfg = EnvConfig(pact_dev_mode=True, anthropic_api_key="test-key")
        backend = AnthropicBackend(cfg)

        response = LLMResponse(
            content="test",
            model="claude-sonnet-4-20260514",
            provider="anthropic",
            input_tokens=1000,
            output_tokens=500,
            tool_calls=[],
            finish_reason="end_turn",
        )
        cost = backend.estimate_cost(response)
        assert cost > Decimal("0")


class TestCombinedPricingOverride:
    """L10: PACT_LLM_PRICING_JSON can contain both openai and anthropic."""

    def test_combined_override(self, monkeypatch):
        """Both providers should be configurable in a single JSON string."""
        custom_pricing = {
            "openai": {
                "gpt-5": {"input": "30.0", "output": "60.0"},
            },
            "anthropic": {
                "claude-next": {"input": "20.0", "output": "100.0"},
            },
        }
        monkeypatch.setenv("PACT_LLM_PRICING_JSON", json.dumps(custom_pricing))

        import importlib

        import pact_platform.use.execution.backends.anthropic_backend as anthropic_mod
        import pact_platform.use.execution.backends.openai_backend as openai_mod

        importlib.reload(openai_mod)
        importlib.reload(anthropic_mod)

        try:
            assert "gpt-5" in openai_mod._OPENAI_PRICING
            assert "claude-next" in anthropic_mod._ANTHROPIC_PRICING
        finally:
            monkeypatch.delenv("PACT_LLM_PRICING_JSON", raising=False)
            importlib.reload(openai_mod)
            importlib.reload(anthropic_mod)
