# Todo 2505: LLM Backend Integration Tests (Real APIs)

**Milestone**: M25 — LLM Backend Integration
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2501, 2502

## What

Integration tests that call the real Anthropic and OpenAI APIs. Tests must be gated behind API key availability: if the relevant key is absent from the environment the test is skipped with a clear skip message (not failed). Cover: response generation (single-turn message), tool use round-trip, error handling for invalid inputs, rate limit recovery (mock 429 to avoid actual throttling), streaming response assembly, and cost extraction (token counts returned and non-zero). Tests must not hardcode model strings; read model names from the same environment variables the backends use.

## Where

- `tests/integration/test_llm_backends.py`

## Evidence

- [ ] Tests skip gracefully when `ANTHROPIC_API_KEY` is absent
- [ ] Tests skip gracefully when `OPENAI_API_KEY` is absent
- [ ] `AnthropicBackend` response generation test passes with real API call
- [ ] `OpenAIBackend` response generation test passes with real API call
- [ ] Tool use round-trip test passes for both backends
- [ ] Rate limit recovery test passes (using mock 429 injection)
- [ ] Streaming test passes for both backends
- [ ] Token count extraction test confirms non-zero counts for both backends
- [ ] No model strings hardcoded in test file
