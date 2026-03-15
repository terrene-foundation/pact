# CARE Platform Architecture

This document describes the architecture of the CARE Platform -- the module structure, data flow, trust enforcement pipeline, and extension points.

---

## Architecture Layers

The CARE Platform is organized into five architecture layers, each building on the one below:

| Layer                | Modules                    | Responsibility                                                           |
| -------------------- | -------------------------- | ------------------------------------------------------------------------ |
| **1. Configuration** | `config/`                  | Organization definition: genesis, teams, agents, envelopes, workspaces   |
| **2. Trust**         | `trust/`                   | EATP trust lifecycle: genesis, delegation, posture, attestation, scoring |
| **3. Constraint**    | `constraint/`              | Constraint envelope evaluation and verification gradient classification  |
| **4. Execution**     | `execution/`, `workspace/` | Agent runtime, sessions, approval queues, cross-functional bridges       |
| **5. Audit**         | `audit/`, `persistence/`   | Tamper-evident audit chains, trust object storage                        |

---

## Trust Plane vs Execution Plane

Following the CARE Dual Plane Model, every component belongs to one of two planes:

### Trust Plane

The Trust Plane establishes, maintains, and verifies the trust infrastructure. No agent action occurs here -- this plane answers the question "is this agent allowed to do this?"

**Modules**: `trust/`, `constraint/`, `audit/`

Key responsibilities:

- **Genesis establishment** (`trust/genesis.py`, `trust/eatp_bridge.py`) -- create the cryptographic root of trust with Ed25519 key pairs
- **Delegation management** (`trust/delegation.py`) -- delegate capabilities with monotonic tightening validation
- **Trust posture lifecycle** (`trust/posture.py`) -- manage evolutionary trust levels (Supervised through Delegated)
- **Capability attestation** (`trust/attestation.py`) -- signed declarations of agent capabilities
- **Trust scoring** (`trust/scoring.py`) -- five-factor weighted trust assessment
- **Constraint evaluation** (`constraint/envelope.py`) -- evaluate actions against five constraint dimensions
- **Verification gradient** (`constraint/gradient.py`) -- classify actions as AUTO_APPROVED, FLAGGED, HELD, or BLOCKED
- **Audit chains** (`audit/anchor.py`) -- tamper-evident records with SHA-256 hash chaining

### Execution Plane

The Execution Plane manages the runtime environment where agents operate. Every action in the Execution Plane passes through the Trust Plane for verification.

**Modules**: `execution/`, `workspace/`

Key responsibilities:

- **Agent and team definitions** (`execution/agent.py`) -- runtime representations combining config with trust state
- **Agent registry** (`execution/registry.py`) -- track agent status and lifecycle
- **Session management** (`execution/session.py`) -- manage execution sessions with checkpoints
- **Approval queues** (`execution/approval.py`) -- queue HELD actions for human approval
- **Workspace management** (`workspace/models.py`) -- workspace-as-knowledge-base for agent teams
- **Cross-functional bridges** (`workspace/bridge.py`) -- controlled inter-team data and communication flow

---

## Module Structure

```
care_platform/
  __init__.py             Package root with public API exports

  config/
    schema.py             Pydantic models: PlatformConfig, AgentConfig, TeamConfig,
                          ConstraintEnvelopeConfig (5 dimensions), VerificationGradientConfig,
                          GenesisConfig, WorkspaceConfig, TrustPostureLevel, VerificationLevel
    loader.py             YAML configuration loader
    defaults.py           Default configuration values

  trust/
    eatp_bridge.py        EATPBridge -- connects CARE models to EATP SDK operations
                          (establish_genesis, delegate, verify_action, record_audit)
    genesis.py            GenesisManager -- genesis lifecycle (create, validate, renew)
    delegation.py         DelegationManager -- delegation chains with monotonic tightening
                          (create_delegation, validate_tightening, walk_chain)
    posture.py            TrustPosture -- evolutionary trust lifecycle
                          (can_upgrade, upgrade, downgrade, is_action_always_held)
    attestation.py        CapabilityAttestation -- EATP Element 4 signed declarations
    scoring.py            TrustScore -- five-factor weighted scoring
                          (chain completeness, depth, coverage, posture, recency)
    credentials.py        Short-lived credential management
    messaging.py          Trust-aware inter-agent messaging
    reasoning.py          Reasoning trace capture for audit
    revocation.py         Trust revocation (surgical and cascade)
    shadow_enforcer.py    ShadowEnforcer -- validates agent decisions without blocking

  constraint/
    envelope.py           ConstraintEnvelope -- runtime evaluation against 5 dimensions
                          (evaluate_action, is_tighter_than, content_hash)
    gradient.py           GradientEngine -- classifies actions into verification levels
                          (classify with QUICK/STANDARD/FULL thoroughness)
    middleware.py         Constraint enforcement middleware
    signing.py            Constraint envelope signing

  execution/
    agent.py              AgentDefinition, TeamDefinition -- runtime agent/team models
    registry.py           AgentRegistry -- agent status tracking
    session.py            PlatformSession, SessionManager -- execution session management
    approval.py           ApprovalQueue -- queue for HELD actions
    hook_enforcer.py      Pre/post execution hooks
    llm_backend.py        LLM backend abstraction (multi-provider)

  audit/
    anchor.py             AuditAnchor, AuditChain -- tamper-evident SHA-256 hash chains
                          (append, verify_chain_integrity, export)
    pipeline.py           Audit pipeline processing

  workspace/
    models.py             Workspace, WorkspaceRegistry -- workspace lifecycle
    bridge.py             Bridge, BridgeManager -- cross-functional bridges
                          (standing, scoped, ad-hoc with dual-side approval)

  persistence/
    store.py              TrustStore protocol, MemoryStore, FilesystemStore
    audit_query.py        Audit anchor query capabilities
    cost_tracking.py      LLM cost tracking and budget enforcement
    posture_history.py    Posture change persistence
    versioning.py         Configuration versioning

  org/
    builder.py            Organization builder for platform bootstrapping

  verticals/
    dm_team.py            Domain-specific team template (Digital Marketing)

  cli/
    (entry point)         Command-line interface (care-platform command)
```

---

## Data Flow: Action Lifecycle

When an agent attempts an action, the following pipeline executes:

```
1. Agent requests action
       |
       v
2. CONSTRAINT EVALUATION (constraint/envelope.py)
   Evaluate action against the agent's five-dimension constraint envelope.
   Result: ALLOWED | NEAR_BOUNDARY | DENIED
       |
       v
3. VERIFICATION GRADIENT (constraint/gradient.py)
   Classify the action based on envelope result + pattern rules.
   Result: AUTO_APPROVED | FLAGGED | HELD | BLOCKED
       |
       +-- BLOCKED --> reject, record audit anchor, return
       |
       +-- HELD --> queue in ApprovalQueue, await human decision
       |
       +-- FLAGGED / AUTO_APPROVED --> continue
       |
       v
4. TRUST VERIFICATION (trust/eatp_bridge.py)
   Verify the agent's trust chain via EATP SDK:
   - Chain integrity (genesis -> delegation -> attestation)
   - Capability check (agent has required capability)
   - Constraint check (EATP-level constraint validation)
   Result: VALID | INVALID
       |
       +-- INVALID --> reject, record audit anchor, return
       |
       v
5. EXECUTION
   Agent performs the action within its workspace context.
       |
       v
6. AUDIT RECORDING (audit/anchor.py, trust/eatp_bridge.py)
   Record a tamper-evident audit anchor:
   - SHA-256 content hash
   - Chain to previous anchor (hash linkage)
   - Agent ID, action, result, verification level, timestamp
```

---

## Verification Gradient Detail

The GradientEngine (`constraint/gradient.py`) classifies actions at three thoroughness levels:

| Thoroughness | Time  | What It Checks                                    |
| ------------ | ----- | ------------------------------------------------- |
| **QUICK**    | ~1ms  | Pattern matching only (glob rules)                |
| **STANDARD** | ~5ms  | Pattern matching + constraint envelope evaluation |
| **FULL**     | ~50ms | Pattern + envelope + full EATP chain verification |

Classification priority:

1. If envelope evaluation returns DENIED, action is BLOCKED
2. If envelope evaluation returns NEAR_BOUNDARY, action is FLAGGED
3. First matching gradient rule determines the level
4. If no rule matches, the configured default level applies (default: HELD)

---

## Trust Scoring

Trust scores (`trust/scoring.py`) are calculated from five weighted factors:

| Factor              | Weight | Scoring                                               |
| ------------------- | ------ | ----------------------------------------------------- |
| Chain completeness  | 30%    | Count of 5 EATP elements present (0.0 to 1.0)         |
| Delegation depth    | 15%    | Shorter chains score higher (inverse ratio)           |
| Constraint coverage | 25%    | Dimensions configured out of 5                        |
| Posture level       | 20%    | Pseudo-Agent=0.0 through Delegated=1.0                |
| Chain recency       | 10%    | Fresher attestations score higher (age vs 90-day max) |

Scores map to letter grades: A+ (>=0.95), A (>=0.85), B+ (>=0.75), B (>=0.65), C (>=0.50), D (>=0.35), F (<0.35).

---

## Storage Layer

The persistence layer (`persistence/store.py`) defines a `TrustStore` protocol with pluggable implementations:

| Implementation      | Use Case                    | Persistence               |
| ------------------- | --------------------------- | ------------------------- |
| **MemoryStore**     | Development, testing        | None (process lifetime)   |
| **FilesystemStore** | Single-instance deployments | JSON files on disk        |
| **DataFlowStore**   | Production (planned)        | Kailash DataFlow database |

The TrustStore interface covers four object types:

- **Envelopes** -- constraint envelope snapshots
- **Audit anchors** -- tamper-evident action records
- **Posture changes** -- trust posture transition history
- **Revocations** -- trust revocation records

---

## Cross-Functional Bridges

Bridges (`workspace/bridge.py`) enable controlled communication between agent teams:

| Bridge Type  | Duration     | Use Case                                              |
| ------------ | ------------ | ----------------------------------------------------- |
| **Standing** | Permanent    | Ongoing relationships (e.g., DM <-> Standards)        |
| **Scoped**   | Time-bounded | Temporary access (e.g., 7-day read access for review) |
| **Ad-Hoc**   | One-time     | Single request/response (e.g., governance review)     |

All bridges require:

- Dual-side approval (both source and target teams)
- Path-level access control (glob patterns for read/write)
- Complete audit log of every data access

---

## Integration with EATP SDK

The CARE Platform integrates with the EATP SDK (`eatp` package) through the EATPBridge (`trust/eatp_bridge.py`):

```
CARE Platform                    EATP SDK
--------------                   --------
GenesisConfig        --->        TrustOperations.establish()
AgentConfig          --->        TrustOperations.delegate()
ConstraintEnvelope   --->        EATP constraint strings
verify_action()      --->        TrustOperations.verify()
record_audit()       --->        TrustOperations.audit()
```

The bridge manages:

- **Authority registry** -- maps organizational authorities to EATP identities
- **Key manager** -- Ed25519 key pair generation and registration
- **Trust store** -- persists trust lineage chains (InMemoryTrustStore by default)
- **Constraint mapping** -- translates five-dimension CARE envelopes to EATP constraint strings

EATP constraint string format:

- Financial: `budget:500.0`, `approval_threshold:100.0`
- Operational: `allow:read`, `block:publish`, `rate_limit:50`
- Temporal: `time:09:00-18:00`
- Data Access: `read:briefs/*`, `write:drafts/*`
- Communication: `comm:internal_only`, `channel:slack`

---

## Extension Points

### Custom Constraint Dimensions

The five standard dimensions (Financial, Operational, Temporal, Data Access, Communication) can be extended by:

1. Adding new fields to the dimension config models in `config/schema.py`
2. Adding evaluation logic in `constraint/envelope.py` dimension evaluators
3. Adding constraint mapping in `trust/eatp_bridge.py`

### Custom Verification Rules

Add gradient rules in `VerificationGradientConfig`:

- Rules use glob patterns for action matching
- First matching rule wins (ordered evaluation)
- Rules can be defined at team level or agent level (agent overrides team)

### Custom Storage Backends

Implement the `TrustStore` protocol from `persistence/store.py`:

- `store_envelope()` / `get_envelope()` / `list_envelopes()`
- `store_audit_anchor()` / `get_audit_anchor()` / `query_anchors()`
- `store_posture_change()` / `get_posture_history()`
- `store_revocation()` / `get_revocations()`

### Custom LLM Backends

The execution layer (`execution/llm_backend.py`) abstracts LLM providers. Add new backends by implementing the backend interface and registering in `execution/registry.py`.
