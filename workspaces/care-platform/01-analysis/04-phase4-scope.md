# Phase 4 — Out of Scope (Deferred from Phase 3)

**Date**: 2026-03-14
**Decision**: User approved Phase 3 as production readiness with ALL security items, ALL execution modes, both LLM backends, all 7 dashboard views. The following items are explicitly deferred to Phase 4.

---

## Deferred Items

| Item                                                                     | Reason                                                                                                                                                    | When Needed                                                         |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Physical store isolation (separate process/container for trust store)    | Architectural change; application-layer TrustStore protocol is sufficient for Foundation use. Python's lack of true private fields is a known limitation. | When enterprise adopters require process-level isolation            |
| HSM key management (hardware security modules for signing keys)          | Requires hardware infrastructure. Ed25519 software keys with rotation (Phase 3) are sufficient for Foundation use.                                        | When enterprise adopters or regulators require hardware-backed keys |
| External hash chain anchoring (transparency log, timestamping authority) | Needs external anchoring service selection. Hash chain provides tamper detection; Audit Anchors provide EATP accountability.                              | When audit credibility with external regulators is required         |
| Multi-tenant isolation (separate trust stores per tenant)                | Foundation is single-org. Multi-tenant is commercial vendor territory.                                                                                    | When third-party deployers need to serve multiple organizations     |
| Multi-instance horizontal scaling (PostgreSQL with shared cache)         | Phase 3 adds PostgreSQL support but single-instance is sufficient for Foundation.                                                                         | When operational load exceeds single-instance capacity              |

## EATP SDK Gaps (Track Separately)

Phase 3 identified 14 gaps in the EATP SDK that CARE Platform currently works around. These should be addressed in the EATP SDK, not reimplemented in the platform. See `workspaces/care-platform/01-analysis/01-research/04-eatp-sdk-gaps.md` for the full list.
