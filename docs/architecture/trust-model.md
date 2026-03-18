# Trust Model

The CARE Platform implements a governed trust model that determines what agents can do, when, and under what constraints. Every agent action passes through the Trust Plane before execution. This page explains the model's structure: the fractal organization (TRUST / BUILD / USE), the EATP trust chain, trust postures, the verification gradient, ShadowEnforcer observation, and the fail-closed enforcement contract.

---

## Fractal Dual Plane Model

The CARE specification defines two planes:

- **Trust Plane** -- establishes, maintains, and verifies trust. No agent actions happen here. It answers: "Is this agent allowed to do this?"
- **Execution Plane** -- manages the runtime environment where agents operate. Every Execution Plane action passes through the Trust Plane first.

The CARE Platform organizes its codebase into three top-level packages that reflect this model:

| Package  | Plane           | Responsibility                                                                                       |
| -------- | --------------- | ---------------------------------------------------------------------------------------------------- |
| `trust/` | Trust Plane     | Constraint evaluation, verification gradient, audit chains, EATP bridge, signing, posture management |
| `build/` | (Configuration) | Organization definition: genesis config, teams, agents, envelopes, workspaces, templates             |
| `use/`   | Execution Plane | Agent runtime, sessions, approval queues, API server, observability                                  |

This is fractal: each team workspace mirrors the same dual-plane separation. The Trust Plane logic applies at every level -- from the platform root down to individual agent constraint envelopes.

---

## EATP Trust Chain

The platform's trust infrastructure is built on the EATP (Enterprise Agent Trust Protocol) trust lineage chain. The chain consists of five elements, each cryptographically linked:

### 1. Genesis Record

The root of trust. Created by the platform authority with an Ed25519 key pair. The `GenesisManager` (`trust/genesis.py`) wraps the EATP SDK's `GenesisRecord` with lifecycle operations: creation, validation, and renewal.

```
Authority creates genesis
  -> Ed25519 key pair generated
  -> Genesis record signed and stored
  -> All subsequent trust derives from this root
```

### 2. Delegation Record

Extends trust from one entity to another. The `DelegationManager` (`trust/delegation.py`) creates delegation chains with monotonic tightening validation -- a child delegation can only narrow constraints, never widen them.

### 3. Constraint Envelope

Defines the five-dimensional boundary for agent actions. See [Constraint Envelopes](constraint-envelopes.md) for detailed documentation. Each envelope is:

- **Frozen after construction** -- Pydantic `frozen=True` prevents post-creation widening
- **Signed with Ed25519** -- agents cannot modify their assigned constraints without detection
- **Content-hashed** -- SHA-256 for integrity verification and cache keying

### 4. Capability Attestation

A signed declaration of what an agent can do. The `CapabilityAttestation` class (`trust/attestation.py`) maps to EATP Element 4 -- recording specific capabilities an agent possesses and the authority that attested them.

### 5. Audit Anchor

A tamper-evident record of trust state at a point in time. The `AuditChain` (`trust/audit/anchor.py`) maintains SHA-256 hash-chained records -- each anchor links to the previous one, making any tampering detectable.

```
Genesis -> Delegation -> Constraint Envelope -> Attestation -> Audit Anchor
   |           |               |                    |              |
   v           v               v                    v              v
  Root      Extend         Bound agent          Declare          Record
 of trust   trust          actions              capability       state
```

The `EATPBridge` (`trust/eatp_bridge.py`) connects CARE models to the EATP SDK, translating between CARE configuration objects and EATP operations (`establish`, `delegate`, `verify`, `audit`).

---

## Trust Postures

Trust postures represent an agent's autonomy level. They evolve based on evidence -- upgrades are gradual and evidence-based, while downgrades are instant.

| Posture                | Autonomy | Description                                                                    |
| ---------------------- | -------- | ------------------------------------------------------------------------------ |
| **PSEUDO_AGENT**       | Minimal  | Maximum oversight. Used for emergency downgrade.                               |
| **SUPERVISED**         | Low      | Agent executes under close human supervision. Starting posture for new agents. |
| **SHARED_PLANNING**    | Medium   | Human and agent plan together, agent executes within agreed parameters.        |
| **CONTINUOUS_INSIGHT** | High     | Agent operates autonomously, human monitors and reviews.                       |
| **DELEGATED**          | Full     | Full delegation within constraint envelope boundaries.                         |

### Evidence-Based Upgrades

Upgrades require quantitative evidence. The `TrustPosture` class (`trust/posture.py`) enforces minimum thresholds per level:

| Target Posture     | Min Days | Min Operations | Min Success Rate | ShadowEnforcer Required |
| ------------------ | -------- | -------------- | ---------------- | ----------------------- |
| SUPERVISED         | 7        | 10             | 90%              | No                      |
| SHARED_PLANNING    | 90       | 100            | 95%              | Yes (90% pass rate)     |
| CONTINUOUS_INSIGHT | 180      | 500            | 98%              | Yes (95% pass rate)     |
| DELEGATED          | 365      | 1000           | 99%              | Yes (98% pass rate)     |

### Instant Downgrades

Any negative incident triggers immediate downgrade. No evidence is required. The platform can downgrade to any lower posture, including emergency downgrade to PSEUDO_AGENT via the EATP SDK's `emergency_downgrade()`.

### Never-Delegated Actions

Certain actions must always require human approval regardless of posture. The `NEVER_DELEGATED_ACTIONS` set includes: `content_strategy`, `novel_outreach`, `crisis_response`, `financial_decisions`, `modify_constraints`, `modify_governance`, and `external_publication`.

---

## Verification Gradient

The verification gradient classifies every agent action into one of four levels that determine how the action is handled. See [Verification Gradient](verification-gradient.md) for detailed documentation.

| Level             | Behavior                         |
| ----------------- | -------------------------------- |
| **AUTO_APPROVED** | Execute and log                  |
| **FLAGGED**       | Execute but highlight for review |
| **HELD**          | Queue for human approval         |
| **BLOCKED**       | Reject outright                  |

---

## ShadowEnforcer

The `ShadowEnforcer` (`trust/shadow_enforcer.py`) runs verification gradient evaluation in parallel with normal agent operations. It collects metrics that feed into trust posture upgrade evidence.

Key properties:

- **Never blocks** -- it only observes and records what WOULD have happened
- **Never holds** -- actions proceed regardless of shadow evaluation
- **Never modifies** -- agent behavior is unchanged by shadow enforcement

The ShadowEnforcer tracks rolling metrics per agent: total evaluations, auto-approved count, flagged count, held count, and blocked count. These metrics produce a `shadow_enforcer_pass_rate` that is a prerequisite for posture upgrades beyond SUPERVISED.

The ShadowEnforcer is explicitly exempt from the fail-closed contract (see below) because its observation-only nature means that failing open does not compromise trust enforcement.

---

## Fail-Closed Enforcement

Every error path in the trust and constraint layers must deny, block, or restrict -- never silently allow. This is the fail-closed contract, documented in [Fail-Closed Contract](fail-closed-contract.md).

| Scenario                                | Required Behavior                 |
| --------------------------------------- | --------------------------------- |
| Exception during verification           | BLOCKED                           |
| Missing agent_id                        | BLOCKED                           |
| Service unavailable                     | BLOCKED                           |
| Unknown posture                         | PSEUDO_AGENT (most restrictive)   |
| Exception in constraint evaluation      | DENIED                            |
| Timeout during trust chain lookup       | BLOCKED                           |
| Unparseable envelope expiry             | Treated as expired (fail-closed)  |
| Invalid timezone in temporal constraint | Logged warning, falls back to UTC |

The `scripts/lint_fail_closed.py` script enforces this contract in CI by scanning trust-plane files for patterns that silently swallow errors.

---

## Trust Scoring

The `TrustScore` class (`trust/scoring.py`) computes a weighted score from five factors:

| Factor              | Weight | Description                                           |
| ------------------- | ------ | ----------------------------------------------------- |
| Chain completeness  | 30%    | Count of 5 EATP elements present (0.0 to 1.0)         |
| Delegation depth    | 15%    | Shorter chains score higher (inverse ratio)           |
| Constraint coverage | 25%    | Dimensions configured out of 5                        |
| Posture level       | 20%    | PSEUDO_AGENT=0.0 through DELEGATED=1.0                |
| Chain recency       | 10%    | Fresher attestations score higher (age vs 90-day max) |

Scores map to letter grades: A+ (>=0.95), A (>=0.85), B+ (>=0.75), B (>=0.65), C (>=0.50), D (>=0.35), F (<0.35).

---

## Further Reading

- [Constraint Envelopes](constraint-envelopes.md) -- five-dimension boundary model
- [Verification Gradient](verification-gradient.md) -- action classification engine
- [Fail-Closed Contract](fail-closed-contract.md) -- error path enforcement
- [Architecture Overview](../architecture.md) -- full module structure and data flow
