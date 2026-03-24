# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""LLM provider management — BYO API keys via ``.env``.

Manages LLM provider configuration and cost estimation for the PACT platform.
All API keys and model names are read from environment variables (per
rules/env-models.md and rules/security.md). Nothing is hardcoded.

Environment variables:
- ``ANTHROPIC_API_KEY``: Anthropic API key
- ``OPENAI_API_KEY``: OpenAI API key
- ``PACT_DEFAULT_PROVIDER``: Default provider (``anthropic`` or ``openai``)
- ``PACT_DEFAULT_MODEL``: Default model identifier
- ``PACT_ROLE_PROVIDER_<ROLE>``: Per-role provider override (upper-cased, hyphens to underscores)
- ``PACT_ROLE_MODEL_<ROLE>``: Per-role model override

Usage:
    from pact_platform.integrations.llm_providers import LLMProviderManager

    mgr = LLMProviderManager()

    # Get default provider
    config = mgr.get_provider()

    # Get per-role override
    config = mgr.get_provider(role_address="D1-R1-T1-R1")

    # Estimate cost
    cost = mgr.estimate_cost("anthropic", "claude-sonnet-4-6", 1000, 500)
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "LLMProviderManager",
    "ProviderConfig",
]


# ---------------------------------------------------------------------------
# 2026 pricing — per 1M tokens (input, output) in USD
#
# These are estimates for budget enforcement. Actual billing comes from the
# provider dashboard. Overridable via PACT_LLM_PRICING_JSON.
# ---------------------------------------------------------------------------
_PRICING: dict[str, dict[str, tuple[Decimal, Decimal]]] = {
    "anthropic": {
        "claude-sonnet-4-6": (Decimal("3"), Decimal("15")),
        "claude-haiku-4-5": (Decimal("0.80"), Decimal("4")),
        "claude-opus-4": (Decimal("15"), Decimal("75")),
    },
    "openai": {
        "gpt-4o": (Decimal("2.50"), Decimal("10")),
        "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
        "gpt-4-turbo": (Decimal("10"), Decimal("30")),
        "o3": (Decimal("2"), Decimal("8")),
        "o3-mini": (Decimal("1.10"), Decimal("4.40")),
    },
}

# Default pricing when model not found (conservative — uses Sonnet-class pricing)
_DEFAULT_PRICING: tuple[Decimal, Decimal] = (Decimal("3"), Decimal("15"))


@dataclass(frozen=True)
class ProviderConfig:
    """Immutable LLM provider configuration.

    Frozen dataclass per rules/governance.md Rule 3 — prevents runtime
    mutation of provider configuration by agent code.

    Attributes:
        provider: Provider identifier (``anthropic``, ``openai``).
        model: Model identifier (``claude-sonnet-4-6``, ``gpt-4o``, etc.).
        api_key: The API key for this provider. **Never log this value.**
        is_available: Whether this provider has a valid API key configured.
    """

    provider: str = ""
    model: str = ""
    api_key: str = ""
    is_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise to dict, redacting the API key.

        Returns:
            Dict with ``api_key`` replaced by a redacted indicator.
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": "***" if self.api_key else "",
            "is_available": self.is_available,
        }


@dataclass
class _ProviderEntry:
    """Internal mutable record for a registered provider."""

    provider: str
    api_key: str
    default_model: str
    env_key_var: str  # e.g. "ANTHROPIC_API_KEY"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)


class LLMProviderManager:
    """Manages LLM provider configuration and cost tracking.

    Reads from ``.env`` (via ``os.environ``) on construction:
    - ``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY`` — provider credentials
    - ``PACT_DEFAULT_PROVIDER`` — which provider to use by default
    - ``PACT_DEFAULT_MODEL`` — which model to use by default

    Per-role overrides are read from:
    - ``PACT_ROLE_PROVIDER_<ROLE>`` — override provider for a specific role address
    - ``PACT_ROLE_MODEL_<ROLE>`` — override model for a specific role address

    Where ``<ROLE>`` is the role address with hyphens replaced by underscores
    and converted to uppercase. For example, role ``D1-R1-T1-R1`` maps to
    env vars ``PACT_ROLE_PROVIDER_D1_R1_T1_R1`` and ``PACT_ROLE_MODEL_D1_R1_T1_R1``.
    """

    def __init__(self) -> None:
        self.providers: dict[str, _ProviderEntry] = {}
        self._default_provider = ""
        self._default_model = ""
        self._role_overrides: dict[str, tuple[str, str]] = {}  # role -> (provider, model)
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load provider configuration from environment variables.

        Reads API keys, default provider/model, and per-role overrides.
        Logs configuration status without exposing secret values.
        """
        # Anthropic
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            self.providers["anthropic"] = _ProviderEntry(
                provider="anthropic",
                api_key=anthropic_key,
                default_model="claude-sonnet-4-6",
                env_key_var="ANTHROPIC_API_KEY",
            )
            logger.info("LLMProviderManager: Anthropic provider loaded")

        # OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            self.providers["openai"] = _ProviderEntry(
                provider="openai",
                api_key=openai_key,
                default_model="gpt-4o",
                env_key_var="OPENAI_API_KEY",
            )
            logger.info("LLMProviderManager: OpenAI provider loaded")

        # Defaults
        self._default_provider = os.environ.get("PACT_DEFAULT_PROVIDER", "").lower()
        self._default_model = os.environ.get("PACT_DEFAULT_MODEL", "")

        # Fall back to first available provider if no default set
        if not self._default_provider and self.providers:
            # Prefer anthropic if available, then openai
            if "anthropic" in self.providers:
                self._default_provider = "anthropic"
            elif "openai" in self.providers:
                self._default_provider = "openai"

        if not self._default_model and self._default_provider:
            entry = self.providers.get(self._default_provider)
            if entry:
                self._default_model = entry.default_model

        logger.info(
            "LLMProviderManager: default_provider=%s, default_model=%s, " "available_providers=%s",
            self._default_provider or "(none)",
            self._default_model or "(none)",
            list(self.providers.keys()),
        )

        # Per-role overrides from env
        self._load_role_overrides()

    def _load_role_overrides(self) -> None:
        """Scan environment for PACT_ROLE_PROVIDER_* and PACT_ROLE_MODEL_* variables."""
        provider_prefix = "PACT_ROLE_PROVIDER_"
        model_prefix = "PACT_ROLE_MODEL_"

        # Collect all role keys from both provider and model env vars
        role_keys: set[str] = set()
        for key in os.environ:
            if key.startswith(provider_prefix):
                role_keys.add(key[len(provider_prefix) :])
            elif key.startswith(model_prefix):
                role_keys.add(key[len(model_prefix) :])

        for role_key in role_keys:
            provider = os.environ.get(
                f"{provider_prefix}{role_key}", self._default_provider
            ).lower()
            model = os.environ.get(f"{model_prefix}{role_key}", self._default_model)
            # Convert env key back to role address: D1_R1_T1_R1 -> D1-R1-T1-R1
            role_address = role_key.replace("_", "-")
            self._role_overrides[role_address] = (provider, model)
            logger.info(
                "LLMProviderManager: role override %s -> provider=%s, model=%s",
                role_address,
                provider,
                model,
            )

    def get_provider(self, role_address: str = "") -> ProviderConfig:
        """Get provider configuration, optionally overridden per role.

        Resolution order:
        1. Per-role override (``PACT_ROLE_PROVIDER_<ROLE>``)
        2. Default provider (``PACT_DEFAULT_PROVIDER``)
        3. First available provider

        Args:
            role_address: Optional D/T/R address for per-role overrides.

        Returns:
            Frozen ``ProviderConfig`` with provider, model, and API key.
            If no providers are configured, returns a config with
            ``is_available=False``.
        """
        provider_name = self._default_provider
        model_name = self._default_model

        # Check per-role override
        if role_address and role_address in self._role_overrides:
            override_provider, override_model = self._role_overrides[role_address]
            if override_provider:
                provider_name = override_provider
            if override_model:
                model_name = override_model

        # Look up the provider entry
        entry = self.providers.get(provider_name)
        if entry is None:
            logger.warning(
                "LLMProviderManager: provider '%s' not found or not configured",
                provider_name,
            )
            return ProviderConfig(
                provider=provider_name,
                model=model_name,
                api_key="",
                is_available=False,
            )

        return ProviderConfig(
            provider=entry.provider,
            model=model_name or entry.default_model,
            api_key=entry.api_key,
            is_available=entry.is_available,
        )

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost in USD for a given token count.

        Uses 2026 pricing tables. For accurate billing, consult the
        provider's dashboard.

        All numeric inputs are validated with ``math.isfinite()`` per
        rules/trust-plane-security.md Rule 3 and rules/pact-governance.md
        Rule 6.

        Args:
            provider: Provider identifier (``anthropic``, ``openai``).
            model: Model identifier.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD as a float.

        Raises:
            ValueError: If token counts are negative or non-finite.
        """
        # Validate inputs — NaN/Inf bypass numeric comparisons
        for name, value in [
            ("input_tokens", input_tokens),
            ("output_tokens", output_tokens),
        ]:
            if not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric, got {type(value).__name__}")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite, got {value!r}")
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value}")

        provider_pricing = _PRICING.get(provider.lower(), {})

        # Try exact model match first, then prefix match
        pricing = provider_pricing.get(model)
        if pricing is None:
            for model_prefix, model_pricing in provider_pricing.items():
                if model.startswith(model_prefix):
                    pricing = model_pricing
                    break

        if pricing is None:
            logger.info(
                "No specific pricing for %s/%s, using default rates",
                provider,
                model,
            )
            pricing = _DEFAULT_PRICING

        input_price_per_m, output_price_per_m = pricing

        cost = (
            input_price_per_m * Decimal(str(input_tokens))
            + output_price_per_m * Decimal(str(output_tokens))
        ) / Decimal("1000000")

        return float(cost.quantize(Decimal("0.000001")))

    def list_providers(self) -> list[dict[str, Any]]:
        """List all configured providers with availability status.

        Returns:
            List of dicts with provider info (API keys redacted).
        """
        result: list[dict[str, Any]] = []
        for name, entry in self.providers.items():
            result.append(
                {
                    "provider": name,
                    "default_model": entry.default_model,
                    "is_available": entry.is_available,
                    "is_default": name == self._default_provider,
                }
            )
        return result

    def list_models(self, provider: str = "") -> list[dict[str, Any]]:
        """List known models with pricing for a provider (or all providers).

        Args:
            provider: Optional provider name to filter by.

        Returns:
            List of dicts with model name, provider, and pricing.
        """
        result: list[dict[str, Any]] = []
        for prov_name, models in _PRICING.items():
            if provider and prov_name != provider.lower():
                continue
            for model_name, (input_price, output_price) in models.items():
                result.append(
                    {
                        "provider": prov_name,
                        "model": model_name,
                        "input_price_per_m": float(input_price),
                        "output_price_per_m": float(output_price),
                    }
                )
        return result
