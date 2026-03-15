# Todo 2502: OpenAI Backend Implementation

**Milestone**: M25 — LLM Backend Integration
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2101

## What

Implement `OpenAIBackend` extending the `LLMBackend` ABC. Use the `openai` Python SDK. Read `OPENAI_API_KEY` and `OPENAI_PROD_MODEL` / `OPENAI_DEV_MODEL` from environment (loaded via `.env`), selecting the appropriate model based on the `CARE_ENV` value. Support messages (single-turn and multi-turn), tool use (function calling), and streaming responses. Implement error handling for rate limits (429, exponential backoff with jitter), timeouts, context-length exceeded errors, and malformed responses. Extract real token counts from API responses for cost tracking.

## Where

- `src/care_platform/execution/backends/openai.py`

## Evidence

- [ ] `OpenAIBackend` instantiates without error when `OPENAI_API_KEY` is set
- [ ] `OpenAIBackend` generates a real text response via the OpenAI API
- [ ] Tool use (function calling) round-trip completes successfully
- [ ] Streaming mode yields incremental chunks and assembles the final response
- [ ] Rate limit errors (429) trigger exponential backoff with jitter and retry
- [ ] Context-length exceeded errors raise a typed exception with guidance
- [ ] Timeout errors raise a typed exception without leaking the raw SDK error
- [ ] Token counts (prompt, completion, total) are present on every response object
- [ ] Unit and integration tests cover all the above scenarios
