# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Multi-LLM backend abstraction — runtime independence from any single LLM provider.

Provides an abstract LLMBackend interface, a StubBackend for testing, and a
BackendRouter that routes requests to the appropriate backend with failover.

This addresses Architecture Gap 4 (Runtime Independence): the PACT
must support multiple LLM backends, not just a single provider.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    LOCAL = "local"  # Ollama, vLLM


class LLMRequest(BaseModel):
    """A request to an LLM backend."""

    messages: list[dict] = Field(default_factory=list)
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: list[dict] = Field(default_factory=list)


class LLMResponse(BaseModel):
    """Response from an LLM backend."""

    content: str = ""
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[dict] = Field(default_factory=list)
    finish_reason: str = ""


class LLMBackend(ABC):
    """Abstract LLM backend interface.

    All LLM backends must inherit from this class and implement the abstract
    methods. This uses ABC (not Protocol) to require explicit inheritance,
    making the contract clear and enforceable at class definition time.
    """

    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        """The provider this backend connects to."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            request: The LLM request containing messages, model, and parameters.

        Returns:
            LLMResponse with the generated content and metadata.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is currently available.

        Returns:
            True if the backend can accept requests, False otherwise.
        """

    @property
    @abstractmethod
    def default_model(self) -> str:
        """The default model identifier for this backend."""


class StubBackend(LLMBackend):
    """Stub backend for testing -- returns configurable responses.

    This backend is for testing only. It records all requests in call_history
    and returns a configurable response string.
    """

    def __init__(
        self,
        response_content: str = "stub response",
        provider_name: LLMProvider = LLMProvider.ANTHROPIC,
    ) -> None:
        self._response = response_content
        self._provider = provider_name
        self._available = True
        self._calls: list[LLMRequest] = []

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a stub response and record the request."""
        self._calls.append(request)
        return LLMResponse(
            content=self._response,
            model=request.model or self.default_model,
            provider=self._provider.value,
            input_tokens=10,
            output_tokens=20,
        )

    def is_available(self) -> bool:
        return self._available

    @property
    def default_model(self) -> str:
        return "stub-model"

    @property
    def call_history(self) -> list[LLMRequest]:
        """Get the history of all requests sent to this backend."""
        return self._calls


class BackendRouter:
    """Routes LLM requests to appropriate backends with failover.

    The router maintains a registry of backends and a fallback order.
    When routing a request:
    1. If a preferred provider is specified AND available, use it.
    2. Otherwise, try providers in fallback order.
    3. If no providers are available, raise RuntimeError.

    Fail-loud: no silent defaults. If nothing is available, the caller
    gets a clear error.
    """

    def __init__(self) -> None:
        self._backends: dict[LLMProvider, LLMBackend] = {}
        self._fallback_order: list[LLMProvider] = []

    def register_backend(self, backend: LLMBackend) -> None:
        """Register an LLM backend.

        Args:
            backend: The backend to register. Overwrites any existing backend
                     for the same provider.
        """
        self._backends[backend.provider] = backend
        logger.info(
            "Registered LLM backend: provider=%s, default_model=%s",
            backend.provider.value,
            backend.default_model,
        )

    def set_fallback_order(self, order: list[LLMProvider]) -> None:
        """Set the fallback order for when the preferred backend is unavailable.

        Args:
            order: Ordered list of providers to try. First available wins.
        """
        self._fallback_order = list(order)
        logger.info(
            "Set fallback order: %s",
            [p.value for p in self._fallback_order],
        )

    def route(
        self,
        request: LLMRequest,
        preferred: LLMProvider | None = None,
    ) -> LLMResponse:
        """Route request to the best available backend.

        Args:
            request: The LLM request to route.
            preferred: Optional preferred provider. If available, this provider
                       is used. Otherwise, fallback order is followed.

        Returns:
            LLMResponse from the selected backend.

        Raises:
            RuntimeError: If no backends are available to handle the request.
        """
        # Try preferred provider first
        if preferred is not None:
            backend = self._backends.get(preferred)
            if backend is not None and backend.is_available():
                logger.debug("Routing to preferred backend: %s", preferred.value)
                return backend.generate(request)
            logger.info(
                "Preferred backend '%s' unavailable, falling back",
                preferred.value,
            )

        # Try fallback order
        for provider in self._fallback_order:
            backend = self._backends.get(provider)
            if backend is not None and backend.is_available():
                logger.debug("Routing to fallback backend: %s", provider.value)
                return backend.generate(request)

        # No fallback order and no preferred specified -- try any registered backend.
        # When a preferred provider was explicitly requested, we do NOT silently
        # fall back to an arbitrary backend. Explicit is better than implicit.
        if not self._fallback_order and preferred is None:
            for provider, backend in self._backends.items():
                if backend.is_available():
                    logger.debug(
                        "No fallback order; routing to first available: %s",
                        provider.value,
                    )
                    return backend.generate(request)

        raise RuntimeError(
            "No LLM backends available to handle request. "
            f"Registered: {[p.value for p in self._backends]}. "
            f"Fallback order: {[p.value for p in self._fallback_order]}."
        )

    def available_backends(self) -> list[LLMProvider]:
        """Get list of currently available backend providers.

        Returns:
            List of LLMProvider values for backends that report as available.
        """
        return [provider for provider, backend in self._backends.items() if backend.is_available()]
