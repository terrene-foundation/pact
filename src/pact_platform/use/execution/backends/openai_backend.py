# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""OpenAI backend — implements LLMBackend for the OpenAI Chat Completions API.

Uses the ``openai`` Python SDK. All configuration (API key, model name)
comes from ``EnvConfig``; nothing is hardcoded.

OpenAI accepts system messages inline in the ``messages`` list, so no
message-level transformation is needed — messages pass through directly.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import openai

from pact_platform.build.config.env import EnvConfig
from pact_platform.trust.store.cost_tracking import ApiCostRecord
from pact_platform.use.execution.llm_backend import (
    LLMBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Approximate pricing per token (USD).
# L10: Defaults can be overridden via PACT_LLM_PRICING_JSON env var.
# ---------------------------------------------------------------------------
_OPENAI_PRICING_DEFAULTS: dict[str, tuple[Decimal, Decimal]] = {
    # model prefix -> (input $/token, output $/token)
    "gpt-4o-mini": (Decimal("0.15") / Decimal("1000000"), Decimal("0.60") / Decimal("1000000")),
    "gpt-4o": (Decimal("2.5") / Decimal("1000000"), Decimal("10") / Decimal("1000000")),
    "gpt-4-turbo": (Decimal("10") / Decimal("1000000"), Decimal("30") / Decimal("1000000")),
    "gpt-4": (Decimal("30") / Decimal("1000000"), Decimal("60") / Decimal("1000000")),
    "gpt-3.5-turbo": (Decimal("0.5") / Decimal("1000000"), Decimal("1.5") / Decimal("1000000")),
    "o1": (Decimal("15") / Decimal("1000000"), Decimal("60") / Decimal("1000000")),
    "o1-mini": (Decimal("3") / Decimal("1000000"), Decimal("12") / Decimal("1000000")),
}


def _load_openai_pricing() -> dict[str, tuple[Decimal, Decimal]]:
    """Load OpenAI pricing, optionally overriding from PACT_LLM_PRICING_JSON.

    The env var should contain a JSON object with an 'openai' key mapping
    model names to ``{"input": "<price>", "output": "<price>"}`` where prices
    are per-million-token USD strings.

    Returns:
        Pricing dict (defaults merged with overrides from env).
    """
    import json
    import os

    pricing = dict(_OPENAI_PRICING_DEFAULTS)

    raw = os.environ.get("PACT_LLM_PRICING_JSON", "")
    if not raw:
        return pricing

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Invalid JSON in PACT_LLM_PRICING_JSON — using default OpenAI pricing")
        return pricing

    openai_overrides = data.get("openai", {})
    if not isinstance(openai_overrides, dict):
        logger.warning("PACT_LLM_PRICING_JSON 'openai' key is not a dict — using default pricing")
        return pricing

    for model_name, prices in openai_overrides.items():
        if not isinstance(prices, dict) or "input" not in prices or "output" not in prices:
            logger.warning(
                "Skipping invalid pricing entry for model '%s' in PACT_LLM_PRICING_JSON",
                model_name,
            )
            continue
        try:
            input_price = Decimal(str(prices["input"])) / Decimal("1000000")
            output_price = Decimal(str(prices["output"])) / Decimal("1000000")
            pricing[model_name] = (input_price, output_price)
        except Exception:
            logger.warning(
                "Failed to parse pricing for model '%s' in PACT_LLM_PRICING_JSON",
                model_name,
            )

    return pricing


_OPENAI_PRICING: dict[str, tuple[Decimal, Decimal]] = _load_openai_pricing()

_DEFAULT_INPUT_PRICE = Decimal("2.5") / Decimal("1000000")
_DEFAULT_OUTPUT_PRICE = Decimal("10") / Decimal("1000000")


class OpenAIBackend(LLMBackend):
    """LLM backend for OpenAI's Chat Completions API.

    Reads the API key and default model from ``EnvConfig``. Prefers
    ``openai_prod_model``; falls back to ``openai_dev_model`` if the
    production model is not configured.
    """

    def __init__(self, config: EnvConfig) -> None:
        self._api_key = config.openai_api_key
        self._prod_model = config.openai_prod_model
        self._dev_model = config.openai_dev_model
        # Lazy client — created if API key is available
        self._client: openai.OpenAI | None = None
        if self._api_key:
            self._client = openai.OpenAI(api_key=self._api_key)

    # ------------------------------------------------------------------
    # LLMBackend interface
    # ------------------------------------------------------------------

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI

    @property
    def default_model(self) -> str:
        if self._prod_model:
            return self._prod_model
        if self._dev_model:
            return self._dev_model
        raise ValueError(
            "OpenAI model not configured. Set OPENAI_PROD_MODEL or "
            "OPENAI_DEV_MODEL in your .env file."
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a request to the OpenAI Chat Completions API.

        Messages are passed directly (OpenAI accepts system role inline).

        Args:
            request: The LLM request to send.

        Returns:
            Mapped ``LLMResponse`` with content, token counts, and tool calls.

        Raises:
            RuntimeError: If the backend is not available (no API key).
        """
        if self._client is None:
            raise RuntimeError(
                "OpenAIBackend is not available — no API key configured. "
                "Set OPENAI_API_KEY in your .env file."
            )

        # Resolve model: prefer request.model, then default_model
        model = request.model if request.model else self.default_model

        # Build API kwargs
        api_kwargs: dict = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Pass tools if provided
        if request.tools:
            api_kwargs["tools"] = request.tools

        logger.debug(
            "OpenAI request: model=%s, messages=%d, tools=%d",
            model,
            len(request.messages),
            len(request.tools),
        )

        response = self._client.chat.completions.create(**api_kwargs)

        # Map response
        choice = response.choices[0]
        content = choice.message.content or ""

        # Map tool calls
        tool_calls: list[dict] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                )

        return LLMResponse(
            content=content,
            model=response.model,
            provider=self.provider.value,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "",
        )

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def estimate_cost(self, response: LLMResponse) -> Decimal:
        """Estimate the USD cost of an LLM response based on token counts.

        Uses approximate per-token pricing. For accurate billing, consult
        the OpenAI dashboard.

        Args:
            response: The LLM response with token counts.

        Returns:
            Estimated cost as a ``Decimal``.
        """
        if response.input_tokens == 0 and response.output_tokens == 0:
            return Decimal("0")

        input_price, output_price = self._get_pricing(response.model)
        cost = (input_price * response.input_tokens) + (output_price * response.output_tokens)
        return cost.quantize(Decimal("0.000001"))

    def create_cost_record(
        self,
        response: LLMResponse,
        agent_id: str,
        team_id: str = "",
        action_id: str = "",
    ) -> ApiCostRecord:
        """Create an ``ApiCostRecord`` from an LLM response.

        Convenience method that estimates cost and builds a record ready
        for ``CostTracker.record()``.

        Args:
            response: The LLM response to record.
            agent_id: The agent that made the call.
            team_id: The team the agent belongs to.
            action_id: Optional link to an audit anchor.

        Returns:
            A populated ``ApiCostRecord``.
        """
        return ApiCostRecord(
            agent_id=agent_id,
            team_id=team_id,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=self.estimate_cost(response),
            action_id=action_id,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_pricing(model: str) -> tuple[Decimal, Decimal]:
        """Look up per-token pricing for a model.

        Tries exact match first, then prefix match.

        Args:
            model: The model identifier string.

        Returns:
            (input_price_per_token, output_price_per_token) as Decimals.
        """
        # Exact match
        if model in _OPENAI_PRICING:
            return _OPENAI_PRICING[model]
        # Prefix match (e.g., "gpt-4o-2024-05-13" matches "gpt-4o")
        for prefix, pricing in sorted(_OPENAI_PRICING.items(), key=lambda x: -len(x[0])):
            if model.startswith(prefix):
                return pricing
        logger.info(
            "No specific pricing for model '%s', using default OpenAI rates",
            model,
        )
        return _DEFAULT_INPUT_PRICE, _DEFAULT_OUTPUT_PRICE
