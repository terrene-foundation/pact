# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for multi-LLM backend abstraction (Task 402)."""

import pytest

from pact_platform.use.execution.llm_backend import (
    BackendRouter,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    StubBackend,
)


class TestLLMModels:
    """Test LLMRequest and LLMResponse Pydantic models."""

    def test_llm_request_defaults(self):
        req = LLMRequest()
        assert req.messages == []
        assert req.model == ""
        assert req.temperature == 0.7
        assert req.max_tokens == 4096
        assert req.tools == []

    def test_llm_request_with_values(self):
        req = LLMRequest(
            messages=[{"role": "user", "content": "hello"}],
            model="claude-3",
            temperature=0.5,
            max_tokens=1024,
            tools=[{"name": "search"}],
        )
        assert len(req.messages) == 1
        assert req.model == "claude-3"
        assert req.temperature == 0.5
        assert req.max_tokens == 1024
        assert len(req.tools) == 1

    def test_llm_response_defaults(self):
        resp = LLMResponse()
        assert resp.content == ""
        assert resp.model == ""
        assert resp.provider == ""
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.tool_calls == []
        assert resp.finish_reason == ""


class TestStubBackend:
    """Test StubBackend for testing scenarios."""

    def test_returns_configured_response(self):
        backend = StubBackend(response_content="test output")
        request = LLMRequest(
            messages=[{"role": "user", "content": "hello"}],
            model="test-model",
        )
        response = backend.generate(request)
        assert response.content == "test output"
        assert response.model == "test-model"
        assert response.provider == "anthropic"
        assert response.input_tokens == 10
        assert response.output_tokens == 20

    def test_uses_default_model_when_request_model_empty(self):
        backend = StubBackend(response_content="test")
        request = LLMRequest(messages=[{"role": "user", "content": "hi"}])
        response = backend.generate(request)
        assert response.model == "stub-model"

    def test_tracks_call_history(self):
        backend = StubBackend()
        req1 = LLMRequest(messages=[{"role": "user", "content": "first"}])
        req2 = LLMRequest(messages=[{"role": "user", "content": "second"}])
        backend.generate(req1)
        backend.generate(req2)
        assert len(backend.call_history) == 2
        assert backend.call_history[0].messages[0]["content"] == "first"
        assert backend.call_history[1].messages[0]["content"] == "second"

    def test_provider_property(self):
        backend = StubBackend(provider_name=LLMProvider.OPENAI)
        assert backend.provider == LLMProvider.OPENAI

    def test_default_model_property(self):
        backend = StubBackend()
        assert backend.default_model == "stub-model"

    def test_is_available_default_true(self):
        backend = StubBackend()
        assert backend.is_available() is True

    def test_is_available_can_be_disabled(self):
        backend = StubBackend()
        backend._available = False
        assert backend.is_available() is False


class TestBackendRouter:
    """Test BackendRouter routing and failover logic."""

    def test_routes_to_preferred_backend(self):
        router = BackendRouter()
        anthropic = StubBackend(
            response_content="anthropic response",
            provider_name=LLMProvider.ANTHROPIC,
        )
        openai = StubBackend(
            response_content="openai response",
            provider_name=LLMProvider.OPENAI,
        )
        router.register_backend(anthropic)
        router.register_backend(openai)

        request = LLMRequest(messages=[{"role": "user", "content": "test"}])
        response = router.route(request, preferred=LLMProvider.OPENAI)
        assert response.content == "openai response"

    def test_falls_back_when_preferred_unavailable(self):
        router = BackendRouter()
        anthropic = StubBackend(
            response_content="anthropic response",
            provider_name=LLMProvider.ANTHROPIC,
        )
        openai = StubBackend(
            response_content="openai response",
            provider_name=LLMProvider.OPENAI,
        )
        openai._available = False
        router.register_backend(anthropic)
        router.register_backend(openai)
        router.set_fallback_order([LLMProvider.OPENAI, LLMProvider.ANTHROPIC])

        request = LLMRequest(messages=[{"role": "user", "content": "test"}])
        response = router.route(request, preferred=LLMProvider.OPENAI)
        assert response.content == "anthropic response"

    def test_raises_when_no_backends_available(self):
        router = BackendRouter()
        with pytest.raises(RuntimeError, match="No LLM backends available"):
            router.route(LLMRequest(messages=[{"role": "user", "content": "test"}]))

    def test_raises_when_all_backends_unavailable(self):
        router = BackendRouter()
        backend = StubBackend(provider_name=LLMProvider.ANTHROPIC)
        backend._available = False
        router.register_backend(backend)

        with pytest.raises(RuntimeError, match="No LLM backends available"):
            router.route(LLMRequest(messages=[{"role": "user", "content": "test"}]))

    def test_available_backends_reflects_registration(self):
        router = BackendRouter()
        assert router.available_backends() == []

        anthropic = StubBackend(provider_name=LLMProvider.ANTHROPIC)
        router.register_backend(anthropic)
        assert router.available_backends() == [LLMProvider.ANTHROPIC]

        openai = StubBackend(provider_name=LLMProvider.OPENAI)
        router.register_backend(openai)
        available = router.available_backends()
        assert LLMProvider.ANTHROPIC in available
        assert LLMProvider.OPENAI in available
        assert len(available) == 2

    def test_available_backends_excludes_unavailable(self):
        router = BackendRouter()
        backend = StubBackend(provider_name=LLMProvider.ANTHROPIC)
        router.register_backend(backend)
        assert router.available_backends() == [LLMProvider.ANTHROPIC]

        backend._available = False
        assert router.available_backends() == []

    def test_multiple_backends_registered(self):
        router = BackendRouter()
        for provider in [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.GOOGLE]:
            router.register_backend(StubBackend(provider_name=provider))
        assert len(router.available_backends()) == 3

    def test_routes_to_first_available_when_no_preferred(self):
        router = BackendRouter()
        anthropic = StubBackend(
            response_content="anthropic response",
            provider_name=LLMProvider.ANTHROPIC,
        )
        router.register_backend(anthropic)
        router.set_fallback_order([LLMProvider.ANTHROPIC])

        request = LLMRequest(messages=[{"role": "user", "content": "test"}])
        response = router.route(request)
        assert response.content == "anthropic response"

    def test_fallback_order_respected(self):
        router = BackendRouter()
        anthropic = StubBackend(
            response_content="anthropic",
            provider_name=LLMProvider.ANTHROPIC,
        )
        openai = StubBackend(
            response_content="openai",
            provider_name=LLMProvider.OPENAI,
        )
        google = StubBackend(
            response_content="google",
            provider_name=LLMProvider.GOOGLE,
        )
        router.register_backend(anthropic)
        router.register_backend(openai)
        router.register_backend(google)
        router.set_fallback_order([LLMProvider.GOOGLE, LLMProvider.OPENAI, LLMProvider.ANTHROPIC])

        # No preferred, should follow fallback order
        request = LLMRequest(messages=[{"role": "user", "content": "test"}])
        response = router.route(request)
        assert response.content == "google"

    def test_raises_when_preferred_not_registered_and_no_fallback(self):
        router = BackendRouter()
        anthropic = StubBackend(provider_name=LLMProvider.ANTHROPIC)
        router.register_backend(anthropic)
        # No fallback order set, preferred is not registered
        with pytest.raises(RuntimeError, match="No LLM backends available"):
            router.route(
                LLMRequest(messages=[{"role": "user", "content": "test"}]),
                preferred=LLMProvider.OPENAI,
            )
