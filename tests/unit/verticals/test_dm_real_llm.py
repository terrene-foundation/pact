# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for real LLM backend configuration — Task 5060.

Validates that DMTeamRunner can switch a single agent (content creator)
from StubBackend to a real LLM backend. Budget-controlled.

Note: These tests validate the CONFIGURATION, not actual LLM calls.
Real LLM calls require API keys and are tested in integration tests with
the appropriate env vars set.
"""

from __future__ import annotations

import pytest

from care_platform.build.verticals.dm_runner import DMTeamRunner


class TestRealLLMBackendConfiguration:
    """DMTeamRunner can switch content creator from StubBackend to real LLM."""

    def test_default_is_stub_backend(self):
        """By default, all agents use StubBackend."""
        runner = DMTeamRunner()
        assert runner.is_dry_run is True

    def test_enable_real_llm_for_content_creator(self):
        """Can configure content creator to use a real LLM provider."""
        runner = DMTeamRunner()
        runner.enable_real_llm(
            agent_id="dm-content-creator",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key-not-real",
            max_budget_usd=1.00,
        )
        assert runner.is_dry_run is False
        agent_backend = runner.get_agent_backend("dm-content-creator")
        assert agent_backend is not None
        assert agent_backend != "stub"

    def test_enable_real_llm_requires_api_key(self):
        """Enabling real LLM without an API key raises ValueError."""
        runner = DMTeamRunner()
        with pytest.raises(ValueError, match="api_key"):
            runner.enable_real_llm(
                agent_id="dm-content-creator",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key="",
                max_budget_usd=1.00,
            )

    def test_enable_real_llm_requires_budget(self):
        """Budget must be positive when enabling real LLM."""
        runner = DMTeamRunner()
        with pytest.raises(ValueError, match="budget"):
            runner.enable_real_llm(
                agent_id="dm-content-creator",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key="test-key",
                max_budget_usd=0.0,
            )

    def test_enable_real_llm_for_unknown_agent_raises(self):
        """Enabling real LLM for unknown agent raises ValueError."""
        runner = DMTeamRunner()
        with pytest.raises(ValueError, match="not registered"):
            runner.enable_real_llm(
                agent_id="unknown-agent",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key="test-key",
                max_budget_usd=1.00,
            )

    def test_other_agents_remain_stub_after_enabling_one(self):
        """Enabling real LLM for content creator leaves other agents on StubBackend."""
        runner = DMTeamRunner()
        runner.enable_real_llm(
            agent_id="dm-content-creator",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key-not-real",
            max_budget_usd=1.00,
        )
        for agent_id in [
            "dm-team-lead",
            "dm-analytics",
            "dm-community-manager",
            "dm-seo-specialist",
        ]:
            backend = runner.get_agent_backend(agent_id)
            assert backend == "stub", f"Agent {agent_id} should still be on stub backend"

    def test_supported_providers(self):
        """DMTeamRunner.supported_providers returns available provider names."""
        runner = DMTeamRunner()
        providers = runner.supported_providers
        assert "anthropic" in providers
        assert "openai" in providers
