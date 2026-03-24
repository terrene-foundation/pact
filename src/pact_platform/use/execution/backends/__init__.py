# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""LLM backend implementations and router factory.

Provides concrete ``LLMBackend`` implementations for Anthropic and OpenAI,
plus a factory function that wires up a ``BackendRouter`` from ``EnvConfig``.

Usage::

    from pact_platform.build.config.env import load_env_config
    from pact_platform.use.execution.backends import create_backend_router

    config = load_env_config()
    router = create_backend_router(config)
    response = router.route(request, preferred=LLMProvider.ANTHROPIC)
"""

from __future__ import annotations

import logging

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.execution.backends.anthropic_backend import AnthropicBackend
from pact_platform.use.execution.backends.openai_backend import OpenAIBackend
from pact_platform.use.execution.llm_backend import BackendRouter, LLMProvider

logger = logging.getLogger(__name__)

__all__ = [
    "AnthropicBackend",
    "OpenAIBackend",
    "create_backend_router",
]


def create_backend_router(config: EnvConfig) -> BackendRouter:
    """Create a ``BackendRouter`` configured from environment variables.

    Registers each backend whose API key is present in ``config`` and
    sets a fallback order based on which backends are available.

    Args:
        config: The validated environment configuration.

    Returns:
        A ``BackendRouter`` with all available backends registered
        and a fallback order configured.
    """
    router = BackendRouter()
    available_providers: list[LLMProvider] = []

    # --- Anthropic ---
    if config.has_anthropic:
        anthropic_backend = AnthropicBackend(config)
        router.register_backend(anthropic_backend)
        available_providers.append(LLMProvider.ANTHROPIC)
        logger.info(
            "Registered Anthropic backend: model=%s",
            config.anthropic_model or "(not set)",
        )

    # --- OpenAI ---
    if config.has_openai:
        openai_backend = OpenAIBackend(config)
        router.register_backend(openai_backend)
        available_providers.append(LLMProvider.OPENAI)
        logger.info(
            "Registered OpenAI backend: prod_model=%s, dev_model=%s",
            config.openai_prod_model or "(not set)",
            config.openai_dev_model or "(not set)",
        )

    # Set fallback order: Anthropic first (if available), then OpenAI
    if available_providers:
        router.set_fallback_order(available_providers)
        logger.info(
            "Backend fallback order: %s",
            [p.value for p in available_providers],
        )
    else:
        logger.warning(
            "No LLM backends configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
        )

    return router
