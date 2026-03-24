# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Platform integrations — notification adapters and LLM provider management.

Provides webhook-based notification delivery for governance events (Slack,
Discord, Microsoft Teams) and BYO-key LLM provider configuration with
cost estimation.

Usage:
    from pact_platform.integrations import (
        NotificationAdapter,
        WebhookAdapterBase,
        SlackAdapter,
        DiscordAdapter,
        TeamsAdapter,
        LLMProviderManager,
    )
"""

from __future__ import annotations

from pact_platform.integrations.discord_adapter import DiscordAdapter
from pact_platform.integrations.llm_providers import (
    LLMProviderManager,
    ProviderConfig,
)
from pact_platform.integrations.notification_base import (
    NotificationAdapter,
    WebhookAdapterBase,
)
from pact_platform.integrations.slack_adapter import SlackAdapter
from pact_platform.integrations.teams_adapter import TeamsAdapter

__all__ = [
    "NotificationAdapter",
    "WebhookAdapterBase",
    "SlackAdapter",
    "DiscordAdapter",
    "TeamsAdapter",
    "LLMProviderManager",
    "ProviderConfig",
]
