# Todo 2503: Backend Router Wiring with .env Configuration

**Milestone**: M25 — LLM Backend Integration
**Priority**: High
**Effort**: Small
**Source**: Phase 3 requirement
**Dependencies**: 2501, 2502

## What

Wire `BackendRouter` to auto-discover and register available backends at startup based on API keys present in `.env`. If `ANTHROPIC_API_KEY` is set, register `AnthropicBackend` as the primary. If `OPENAI_API_KEY` is set, register `OpenAIBackend` as the fallback. Log available backends at startup so operators can verify the configuration. The router must attempt the primary backend first, fall over to the next available backend on unrecoverable error, and raise a typed `NoBackendAvailableError` when all registered backends are exhausted. Update `bootstrap.py` to initialise and expose the router.

## Where

- `src/care_platform/execution/llm_backend.py`
- `src/care_platform/bootstrap.py`

## Evidence

- [ ] Router registers only backends whose API keys are present in `.env`
- [ ] At startup, a log line lists all registered backends in priority order
- [ ] When the primary backend fails with an unrecoverable error, the router falls over to the next backend and completes the request
- [ ] When no backends are registered, router raises `NoBackendAvailableError` with a clear message
- [ ] `bootstrap.py` initialises the router and makes it available to the rest of the runtime
- [ ] Unit tests cover: single-backend registration, multi-backend failover, no-backend error
