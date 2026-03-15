# Todo 2501: Anthropic Claude Backend Implementation

**Milestone**: M25 — LLM Backend Integration
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2101

## What

Implement `AnthropicBackend` extending the `LLMBackend` ABC. Use the `anthropic` Python SDK. Read `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` from environment (loaded via `.env`). Support messages (single-turn and multi-turn), tool use (function calling), and streaming responses. Implement error handling for rate limits (429, exponential backoff with jitter), timeouts, and malformed responses. The backend must extract real token counts from API responses and expose them for cost tracking.

## Where

- `src/care_platform/execution/backends/anthropic.py`

## Evidence

- [ ] `AnthropicBackend` instantiates without error when `ANTHROPIC_API_KEY` is set
- [ ] `AnthropicBackend` generates a real text response via the Anthropic API
- [ ] Tool use (function calling) round-trip completes successfully
- [ ] Streaming mode yields incremental chunks and assembles the final response
- [ ] Rate limit errors (429) trigger exponential backoff with jitter and retry
- [ ] Timeout errors raise a typed exception without leaking the raw SDK error
- [ ] Malformed API responses raise a typed exception with context
- [ ] Token counts (prompt, completion, total) are present on every response object
- [ ] Unit and integration tests cover all the above scenarios
