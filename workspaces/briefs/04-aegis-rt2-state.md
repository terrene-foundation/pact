# Aegis State After RT2 (2026-03-21)

**Context**: Corrections to inaccuracies in 03-delegate-integration-brief.md, based on Aegis RT2 red team (5 parallel reviewers, 16,851 tests passing, 30+ findings fixed).

## What Aegis Actually Has (Corrected)

### Governance (corrected from brief)

| Capability | Brief Claimed | Actual State |
|---|---|---|
| KSPs | "No KSPs" | Full implementation: DataFlow model, CRUD API, service with evaluate_downward_access(), RT2-hardened (classification whitelist, path traversal protection) |
| Envelopes | "Flat" | 3-layer: RoleEnvelope + TaskEnvelope + EnvelopeCompositionService. RT2 added: bootstrap mode (HELD actions, 30-day expiry), REVOKED terminal state, fail-closed on corrupted JSON |
| Thread safety | "Not thread-safe" | Partially correct — individual services have threading.Lock (RT2 fixed 4 singletons), but no unified GovernanceEngine facade. PACT's approach is architecturally superior. |
| Frozen context | "Mutable refs" | Correct — Aegis passes mutable DataFlow record dicts. PACT's frozen dataclass approach is architecturally superior. |

### Governance Features Aegis Has

- D/T/R grammar enforcement with auto-R creation (is_vacant tracking)
- Positional addressing (address_service.py, compile on org structure change)
- 5-level classification with EATP naming (public/restricted/confidential/secret/top_secret)
- Compartment isolation for SECRET/TOP_SECRET
- Posture-caps-clearance (effective = min(role.max_clearance, posture_ceiling))
- 5-step access enforcement (clearance → compartment → containment → KSP/bridge → deny)
- Monotonic tightening validation (child ≤ parent at every dimension)
- Verification gradient (4 zones: auto/flagged/held/blocked)
- NEVER_DELEGATED_ACTIONS (7 governance actions always HELD)
- Bridge trust (bilateral, role-anchored, persisted to DB after RT2)
- Emergency bypass (time-bounded, tiered approval)
- Vacant role exclusion from trust/execution (RT2 fix)

### Operational Surface (unchanged from brief)

- 112 DataFlow models
- 83+ API routers
- 60+ agentic services
- 5 webhook adapters
- 6 runtime adapters
- 16,851 tests passing

### What PACT GovernanceEngine Has That Aegis Should Import

These are architectural patterns Aegis should adopt when consuming kailash-pact-rs:

1. **Thread-safe GovernanceEngine facade** — single entry point with Lock, not 20 separate services
2. **Frozen context returns** — immutable results prevent mutation bugs
3. **NaN/Inf protection** — reject non-finite values in envelope dimensions
4. **Bounded store collections** — MAX_STORE_SIZE prevents memory exhaustion
5. **Compile-once org model** — CompiledOrg as immutable graph, not live DB queries per access check

## Architectural Style Differences (Not Feature Gaps)

| Concern | PACT Platform | Aegis | Which Is Better |
|---|---|---|---|
| Governance computation | Pure functions on frozen dataclasses | DataFlow workflows on DB records | PACT (correctness) |
| Persistence | Protocol-based stores (pluggable) | DataFlow ORM (Kailash-specific) | Aegis (production maturity) |
| API surface | ~30 endpoints | 83+ endpoints | Aegis (breadth) |
| Testing | 968 governance tests | 16,851 total tests | Aegis (coverage) |
| Frontend | Next.js + Flutter | React (responsive) | PACT (mobile) |

The right approach: Aegis imports governance computation from kailash-pact-rs, keeps its own persistence and API layers.
