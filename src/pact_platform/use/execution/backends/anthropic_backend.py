# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Anthropic Claude backend — implements LLMBackend for the Anthropic Messages API.

Uses the ``anthropic`` Python SDK. All configuration (API key, model name)
comes from ``EnvConfig``; nothing is hardcoded.

The Anthropic Messages API requires system messages to be passed as a
top-level ``system`` parameter, not inside the ``messages`` list. This
backend handles that separation automatically.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import anthropic

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
# Approximate pricing per token (USD).  These are estimates used for budget
# enforcement.  Actual billing comes from the provider dashboard.
# L10: Defaults can be overridden via PACT_LLM_PRICING_JSON env var.
# ---------------------------------------------------------------------------
_ANTHROPIC_PRICING_DEFAULTS: dict[str, tuple[Decimal, Decimal]] = {
    # model prefix -> (input $/token, output $/token)
    "claude-opus-4": (Decimal("15") / Decimal("1000000"), Decimal("75") / Decimal("1000000")),
    "claude-sonnet-4": (Decimal("3") / Decimal("1000000"), Decimal("15") / Decimal("1000000")),
    "claude-haiku": (Decimal("0.25") / Decimal("1000000"), Decimal("1.25") / Decimal("1000000")),
}


def _load_anthropic_pricing() -> dict[str, tuple[Decimal, Decimal]]:
    """Load Anthropic pricing, optionally overriding from PACT_LLM_PRICING_JSON.

    The env var should contain a JSON object with an 'anthropic' key mapping
    model names to ``{"input": "<price>", "output": "<price>"}`` where prices
    are per-million-token USD strings.

    Returns:
        Pricing dict (defaults merged with overrides from env).
    """
    import json
    import os

    pricing = dict(_ANTHROPIC_PRICING_DEFAULTS)

    raw = os.environ.get("PACT_LLM_PRICING_JSON", "")
    if not raw:
        return pricing

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Invalid JSON in PACT_LLM_PRICING_JSON — using default Anthropic pricing")
        return pricing

    anthropic_overrides = data.get("anthropic", {})
    if not isinstance(anthropic_overrides, dict):
        logger.warning(
            "PACT_LLM_PRICING_JSON 'anthropic' key is not a dict — using default pricing"
        )
        return pricing

    for model_name, prices in anthropic_overrides.items():
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


_ANTHROPIC_PRICING: dict[str, tuple[Decimal, Decimal]] = _load_anthropic_pricing()

# Fallback pricing when the model isn't recognised
_DEFAULT_INPUT_PRICE = Decimal("3") / Decimal("1000000")
_DEFAULT_OUTPUT_PRICE = Decimal("15") / Decimal("1000000")


class AnthropicBackend(LLMBackend):
    """LLM backend for Anthropic's Claude models.

    Reads the API key and default model from ``EnvConfig``. Constructs an
    ``anthropic.Anthropic`` client lazily (on first ``generate`` call) so
    that availability checks don't require a valid key.
    """

    def __init__(self, config: EnvConfig) -> None:
        self._api_key = config.anthropic_api_key
        self._model = config.anthropic_model
        # Lazy client — created on first generate() call
        self._client: anthropic.Anthropic | None = None
        if self._api_key:
            self._client = anthropic.Anthropic(api_key=self._api_key)

    # ------------------------------------------------------------------
    # LLMBackend interface
    # ------------------------------------------------------------------

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC

    @property
    def default_model(self) -> str:
        if not self._model:
            raise ValueError(
                "Anthropic model not configured. Set ANTHROPIC_MODEL in your "
                ".env file or pass anthropic_model to EnvConfig."
            )
        return self._model

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a request to the Anthropic Messages API.

        Separates system messages from the ``messages`` list and passes them
        as the top-level ``system`` parameter, as required by the Anthropic API.

        Args:
            request: The LLM request to send.

        Returns:
            Mapped ``LLMResponse`` with content, token counts, and tool calls.

        Raises:
            RuntimeError: If the backend is not available (no API key).
        """
        if self._client is None:
            raise RuntimeError(
                "AnthropicBackend is not available — no API key configured. "
                "Set ANTHROPIC_API_KEY in your .env file."
            )

        # Separate system message(s) from conversation messages
        system_content = ""
        conversation_messages: list[dict] = []
        for msg in request.messages:
            if msg.get("role") == "system":
                # Concatenate multiple system messages (rare but possible)
                if system_content:
                    system_content += "\n\n"
                system_content += msg.get("content", "")
            else:
                conversation_messages.append(msg)

        # Resolve model: prefer request.model, then default_model
        model = request.model if request.model else self.default_model

        # Build API kwargs
        api_kwargs: dict = {
            "model": model,
            "messages": conversation_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if system_content:
            api_kwargs["system"] = system_content

        # Pass tools if provided
        if request.tools:
            api_kwargs["tools"] = request.tools

        logger.debug(
            "Anthropic request: model=%s, messages=%d, system=%s, tools=%d",
            model,
            len(conversation_messages),
            bool(system_content),
            len(request.tools),
        )

        response = self._client.messages.create(**api_kwargs)

        # Map response content blocks
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        return LLMResponse(
            content="\n\n".join(text_parts) if text_parts else "",
            model=response.model,
            provider=self.provider.value,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "",
        )

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def estimate_cost(self, response: LLMResponse) -> Decimal:
        """Estimate the USD cost of an LLM response based on token counts.

        Uses approximate per-token pricing. For accurate billing, consult
        the Anthropic dashboard.

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

        Args:
            model: The model identifier string.

        Returns:
            (input_price_per_token, output_price_per_token) as Decimals.
        """
        for prefix, pricing in _ANTHROPIC_PRICING.items():
            if model.startswith(prefix):
                return pricing
        logger.info(
            "No specific pricing for model '%s', using default Anthropic rates",
            model,
        )
        return _DEFAULT_INPUT_PRICE, _DEFAULT_OUTPUT_PRICE
