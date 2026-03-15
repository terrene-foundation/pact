# 402: Support Multiple LLM Backends

**Milestone**: 4 — Agent Execution Runtime
**Priority**: Medium (runtime independence — Gap 4)
**Estimated effort**: Medium
**Depends on**: 401
**Completed**: 2026-03-12
**Verified by**: LLMBackend ABC + LLMProvider enum + LLMRequest + LLMResponse + StubBackend + BackendRouter in `care_platform/execution/llm_backend.py`; 20 unit tests pass in `tests/unit/execution/test_llm_backend.py`

## Description

Support multiple LLM backends via agent configuration. Runtime (Claude, OpenAI, Gemini, local models) is a deployment choice, not an architectural constraint.

## Tasks

- [ ] Implement backend abstraction:
  - `LLMBackend` interface (generate, tool_call, embed)
  - `ClaudeBackend` — Anthropic API via Kaizen
  - `OpenAIBackend` — OpenAI API via Kaizen
  - `GeminiBackend` — Google API via Kaizen
  - `LocalBackend` — Ollama/vLLM for local models
- [ ] Implement per-agent backend configuration:
  - Agent definition specifies preferred backend and model
  - Fallback chain if preferred backend unavailable
  - Cost tracking per backend/model
- [ ] Implement backend health checking:
  - API availability monitoring
  - Rate limit awareness
  - Automatic failover to fallback
- [ ] Implement `.env` configuration:
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
  - `DEFAULT_LLM_MODEL` fallback
  - Per-team overrides possible
- [ ] Write integration tests (with mocked backends):
  - Backend selection based on agent config
  - Failover behavior
  - Cost tracking accuracy

## Acceptance Criteria

- At least two backends functional (Claude + OpenAI)
- Per-agent backend configuration works
- Failover handles backend unavailability
- Cost tracking per backend
- Integration tests with mocked backends passing
