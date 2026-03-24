# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for the integration layer — webhook adapters and LLM providers."""

from __future__ import annotations

import os

import pytest


class TestNotificationAdapterProtocol:
    """Verify the NotificationAdapter protocol works."""

    def test_protocol_importable(self):
        from pact_platform.integrations.notification_base import NotificationAdapter

        assert NotificationAdapter is not None

    def test_webhook_base_importable(self):
        from pact_platform.integrations.notification_base import WebhookAdapterBase

        assert WebhookAdapterBase is not None


class TestSlackAdapter:
    def test_importable(self):
        from pact_platform.integrations.slack_adapter import SlackAdapter

        assert SlackAdapter is not None

    def test_format_held_event(self):
        from pact_platform.integrations.slack_adapter import SlackAdapter

        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/test")
        payload = adapter._format_payload(
            "governance.held",
            {
                "decision_id": "dec-1",
                "agent_address": "D1-T1-R1",
                "action": "access_restricted_records",
                "reason": "Requires CONFIDENTIAL clearance",
            },
        )
        assert isinstance(payload, dict)


class TestDiscordAdapter:
    def test_importable(self):
        from pact_platform.integrations.discord_adapter import DiscordAdapter

        assert DiscordAdapter is not None


class TestTeamsAdapter:
    def test_importable(self):
        from pact_platform.integrations.teams_adapter import TeamsAdapter

        assert TeamsAdapter is not None


class TestLLMProviderManager:
    def test_importable(self):
        from pact_platform.integrations.llm_providers import LLMProviderManager

        assert LLMProviderManager is not None

    def test_estimate_cost_anthropic(self):
        from pact_platform.integrations.llm_providers import LLMProviderManager

        mgr = LLMProviderManager()
        cost = mgr.estimate_cost("anthropic", "claude-sonnet-4-6", 1000, 500)
        assert cost > 0
        assert isinstance(cost, float)

    def test_estimate_cost_openai(self):
        from pact_platform.integrations.llm_providers import LLMProviderManager

        mgr = LLMProviderManager()
        cost = mgr.estimate_cost("openai", "gpt-4o", 1000, 500)
        assert cost > 0
