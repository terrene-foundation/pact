# Phase 3 Research: Deferred Items & Implicit Gaps

**Date**: 2026-03-14
**Source**: RT4-RT10 reports, decisions.yml, production gap analysis

---

## Explicitly Deferred Items (14)

### From RT10 Accepted Findings (6)

| ID      | Finding                                   | Production Risk                                 | Effort       |
| ------- | ----------------------------------------- | ----------------------------------------------- | ------------ |
| RT10-A1 | Store isolation is application-layer only | HIGH (but mitigated by TrustStore protocol)     | Large        |
| RT10-A2 | Cumulative spend no thread lock           | LOW (asyncio single-threaded, spend persisted)  | Small        |
| RT10-A3 | Hash chain no external anchor             | MEDIUM (tamper detection but not prevention)    | Medium       |
| RT10-A4 | WebSocket no authentication               | HIGH (event stream exposes governance activity) | Small-Medium |
| RT10-A5 | In-flight actions survive revocation      | MEDIUM (millisecond window for fast actions)    | Medium       |
| RT10-A6 | Auth disabled when CARE_API_TOKEN empty   | CRITICAL in production                          | Small        |

### From RT5-RT6 Carried Forward (8)

| ID           | Finding                                        | Production Risk           | Effort       |
| ------------ | ---------------------------------------------- | ------------------------- | ------------ |
| RT5-03       | Nonce replay after restart (5-min window)      | MEDIUM                    | Small-Medium |
| RT5-14       | Non-SQLite stores allow genesis overwrite      | LOW (SQLite has triggers) | Small        |
| RT5-15       | Bootstrap BaseException handling               | LOW                       | Trivial      |
| RT5-17/20/28 | Missing spec-defined constraint parameters     | LOW-MEDIUM                | Medium       |
| RT5-19       | Financial 0.0 ambiguity (zero vs unconfigured) | MEDIUM                    | Small        |
| RT5-24       | Delegation expiry never enforced at runtime    | MEDIUM                    | Small        |
| RT5-26/27    | Audit chain missing EATP fields                | LOW-MEDIUM                | Small-Medium |

### From decisions.yml (2 new items)

| Item                               | Production Risk                         | Effort       |
| ---------------------------------- | --------------------------------------- | ------------ |
| HSM key management                 | LOW for Foundation, HIGH for enterprise | Large        |
| Rate limiting (internal per-agent) | MEDIUM                                  | Small-Medium |

---

## Implicit Gaps (12) — Not Flagged by Red Team

| ID  | Gap                                      | Risk            | Effort       |
| --- | ---------------------------------------- | --------------- | ------------ |
| I1  | Structured logging and observability     | HIGH            | Medium       |
| I2  | Health/readiness probes                  | MEDIUM          | Small        |
| I3  | Startup configuration validation         | MEDIUM          | Small-Medium |
| I4  | Secrets rotation (token + Ed25519 keys)  | HIGH            | Medium-Large |
| I5  | Backup and restore for trust store       | HIGH            | Small-Medium |
| I6  | Schema migration framework               | HIGH            | Medium       |
| I7  | Per-agent rate limiting in middleware    | MEDIUM          | Small-Medium |
| I8  | Graceful shutdown                        | MEDIUM          | Small-Medium |
| I9  | Multi-instance / horizontal scaling      | Decision needed | Variable     |
| I10 | Error reporting and alerting             | MEDIUM          | Small-Medium |
| I11 | Integration tests with real LLM backends | MEDIUM          | Medium       |
| I12 | Operator documentation                   | HIGH            | Medium       |

---

## Dependency Clusters

**Cluster 1 — API Security**: RT10-A4 + RT10-A6 + rate limiting → single "auth hardening" stream

**Cluster 2 — Constraint Model Completeness**: RT5-17/20/28 + RT5-19 → single "spec alignment" pass

**Cluster 3 — Physical Security Boundary**: RT10-A1 + HSM + RT10-A3 → long-term, separate from Phase 3 core

**Cluster 4 — Restart Resilience**: RT5-03 + RT10-A2 + RT5-15 → small "operational resilience" batch

---

## Prioritized Tiers

### Tier 1: Before Any Deployment (8 items, ~2-3 weeks)

RT10-A6 (empty token guard), RT10-A4 (WebSocket auth), I3 (config validation), I2 (health probes), I8 (graceful shutdown), RT5-03 (nonce persistence), RT5-15 (bootstrap fix), RT5-14 (genesis enforcement)

### Tier 2: Before Production (13 items, ~6-8 weeks)

RT5-19 (financial ambiguity), RT5-17/20/28 (constraint parameters), RT5-24 (delegation expiry), I1 (structured logging), I5 (backup/restore), I6 (migrations), I7 (agent rate limiting), I4 (secrets rotation), RT10-A5 (revocation check), RT5-26/27 (audit EATP completeness), RT10-A2 (spend lock), I10 (alerting), I12 (operator docs)

### Tier 3: Nice to Have (6 items, variable)

RT10-A1 (store isolation), HSM, RT10-A3 (external anchoring), I11 (LLM integration tests), I9 (multi-instance), I9-doc (single-instance documentation)
