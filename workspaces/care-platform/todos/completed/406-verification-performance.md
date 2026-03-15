# 406: Verification Performance Optimization

**Milestone**: 4 — Agent Execution Runtime
**Priority**: Medium (performance at scale)
**Estimated effort**: Medium

## Description

Optimize the verification gradient performance so that high-frequency agent actions (e.g., Analytics Agent's continuous monitoring) do not incur unacceptable latency. The EATP spec defines three verification levels: QUICK (~1ms), STANDARD (~5ms), FULL (~50ms). This todo validates and optimizes to meet these targets.

## Tasks

- [ ] Implement verification caching:
  - Short-lived verification token (5-minute TTL from 206)
  - Within TTL: QUICK verification uses cached result
  - After TTL: re-run STANDARD or FULL verification
  - Cache stored in memory (not database) — fast lookup
- [ ] Implement `VerificationCache`:
  - LRU cache with TTL eviction
  - Cache key: (agent_id, constraint_envelope_version)
  - Cache value: (trust_score, posture, expiry_timestamp)
- [ ] Implement adaptive verification level selection:
  - Default: STANDARD for most actions
  - QUICK: for actions in the cache TTL window (routine operations)
  - FULL: for cross-team operations, high-stakes actions, or first action of session
  - Configurable per-action-type in constraint envelope
- [ ] Benchmark verification at each level:
  - Measure QUICK, STANDARD, FULL latency with realistic trust chains (3-5 hop)
  - Target: QUICK < 1ms, STANDARD < 5ms, FULL < 100ms
  - Document results; fail build if targets exceeded by >2x
- [ ] Implement verification circuit breaker:
  - If verification system is slow or unavailable: fail-safe BLOCKED
  - Log circuit breaker events
  - Recovery: automatic when verification system recovers
- [ ] Write performance benchmarks:
  - 1000 QUICK verifications — measure p50, p95, p99
  - 100 STANDARD verifications
  - 10 FULL verifications
  - Compare to targets

## Acceptance Criteria

- QUICK verification < 1ms with cache hit
- STANDARD verification < 5ms
- FULL verification < 100ms (acceptable relaxation from 50ms target)
- Circuit breaker triggers and recovers correctly
- Benchmark results documented in test output

## Dependencies

- 104: Verification gradient engine (baseline performance)
- 206: Credential lifecycle (verification token TTL)
- 401: Kaizen agent bridge (high-frequency action path)

## References

- EATP Operations spec: Verification levels and performance targets
- EATP SDK: `src/eatp/cache.py` — existing cache implementation
- EATP SDK: `src/eatp/circuit_breaker.py` — existing circuit breaker
