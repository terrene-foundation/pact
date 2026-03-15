# CARE Platform API Reference

This document covers the public interfaces of the CARE Platform. For architecture context, see [architecture.md](architecture.md).

---

## Table of Contents

- [Configuration Models](#configuration-models)
- [EATPBridge](#eatpbridge)
- [GenesisManager](#genesismanager)
- [DelegationManager](#delegationmanager)
- [Constraint Envelopes](#constraint-envelopes)
- [Verification Gradient](#verification-gradient)
- [Trust Postures](#trust-postures)
- [Trust Scoring](#trust-scoring)
- [Capability Attestation](#capability-attestation)
- [Audit Chain](#audit-chain)
- [Storage](#storage)

---

## Configuration Models

**Module**: `care_platform.config.schema`

### PlatformConfig

Top-level configuration for the entire platform. Contains all organization structure: genesis, teams, agents, constraint envelopes, and workspaces.

```python
from care_platform.config.schema import PlatformConfig, GenesisConfig

config = PlatformConfig(
    name="My Organization",
    version="1.0",
    genesis=GenesisConfig(
        authority="my-org.example",
        authority_name="My Organization",
        policy_reference="https://my-org.example/policy",
    ),
    constraint_envelopes=[...],
    agents=[...],
    teams=[...],
    workspaces=[...],
)

# Lookup helpers
envelope = config.get_envelope("envelope-id")    # -> ConstraintEnvelopeConfig | None
agent = config.get_agent("agent-id")              # -> AgentConfig | None
team = config.get_team("team-id")                 # -> TeamConfig | None
workspace = config.get_workspace("workspace-id")  # -> WorkspaceConfig | None
```

### ConstraintEnvelopeConfig

Defines the five constraint dimensions governing an agent.

```python
from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    DataAccessConstraintConfig,
    CommunicationConstraintConfig,
)

envelope = ConstraintEnvelopeConfig(
    id="analyst-envelope",
    description="Constraints for research analysts",
    financial=FinancialConstraintConfig(
        max_spend_usd=500.0,
        api_cost_budget_usd=100.0,
        requires_approval_above_usd=50.0,
    ),
    operational=OperationalConstraintConfig(
        allowed_actions=["read", "analyze", "draft"],
        blocked_actions=["publish", "delete"],
        max_actions_per_day=100,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="09:00",
        active_hours_end="18:00",
        timezone="UTC",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["briefs/*", "reports/*"],
        write_paths=["drafts/*"],
        blocked_data_types=["pii", "financial_records"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        allowed_channels=["slack", "email"],
        external_requires_approval=True,
    ),
)
```

### The Five Constraint Dimensions

| Dimension     | Config Class                    | Key Fields                                                               |
| ------------- | ------------------------------- | ------------------------------------------------------------------------ |
| Financial     | `FinancialConstraintConfig`     | `max_spend_usd`, `api_cost_budget_usd`, `requires_approval_above_usd`    |
| Operational   | `OperationalConstraintConfig`   | `allowed_actions`, `blocked_actions`, `max_actions_per_day`              |
| Temporal      | `TemporalConstraintConfig`      | `active_hours_start`, `active_hours_end`, `timezone`, `blackout_periods` |
| Data Access   | `DataAccessConstraintConfig`    | `read_paths`, `write_paths`, `blocked_data_types`                        |
| Communication | `CommunicationConstraintConfig` | `internal_only`, `allowed_channels`, `external_requires_approval`        |

### TrustPostureLevel

```python
from care_platform.config.schema import TrustPostureLevel

TrustPostureLevel.PSEUDO_AGENT        # No autonomous action
TrustPostureLevel.SUPERVISED           # Every action requires approval (default)
TrustPostureLevel.SHARED_PLANNING      # Agent proposes, human approves plans
TrustPostureLevel.CONTINUOUS_INSIGHT   # Agent executes with oversight
TrustPostureLevel.DELEGATED            # Autonomous within constraints
```

### VerificationLevel

```python
from care_platform.config.schema import VerificationLevel

VerificationLevel.AUTO_APPROVED  # Execute and log
VerificationLevel.FLAGGED        # Execute but highlight for review
VerificationLevel.HELD           # Queue for human approval
VerificationLevel.BLOCKED        # Reject outright
```

### AgentConfig

```python
from care_platform.config.schema import AgentConfig

agent = AgentConfig(
    id="analyst-01",
    name="Research Analyst",
    role="Analyze data and produce reports",
    constraint_envelope="analyst-envelope",  # References ConstraintEnvelopeConfig.id
    initial_posture=TrustPostureLevel.SUPERVISED,
    capabilities=["read", "analyze", "draft"],
    llm_backend=None,  # Uses team default
)
```

### VerificationGradientConfig

```python
from care_platform.config.schema import VerificationGradientConfig, GradientRuleConfig

gradient = VerificationGradientConfig(
    rules=[
        GradientRuleConfig(
            pattern="read*",
            level=VerificationLevel.AUTO_APPROVED,
            reason="Read operations are low risk",
        ),
        GradientRuleConfig(
            pattern="publish*",
            level=VerificationLevel.HELD,
            reason="Publishing requires human approval",
        ),
        GradientRuleConfig(
            pattern="delete*",
            level=VerificationLevel.BLOCKED,
            reason="Deletion is not permitted",
        ),
    ],
    default_level=VerificationLevel.HELD,
)
```

---

## EATPBridge

**Module**: `care_platform.trust.eatp_bridge`

The central bridge between CARE Platform configuration models and the EATP SDK. Manages the full trust lifecycle: ESTABLISH, DELEGATE, VERIFY, AUDIT.

### Initialization

```python
from care_platform.trust.eatp_bridge import EATPBridge

bridge = EATPBridge()           # Uses InMemoryTrustStore by default
await bridge.initialize()       # Must be called before any operations
```

### establish_genesis

Create the root of trust for an organization.

```python
from care_platform.config.schema import GenesisConfig

genesis_config = GenesisConfig(
    authority="my-org.example",
    authority_name="My Organization",
    policy_reference="https://my-org.example/policy",
)

genesis_record = await bridge.establish_genesis(genesis_config)
# Returns: eatp.chain.GenesisRecord
# The genesis authority's agent_id is "authority:my-org.example"
```

### delegate

Delegate capabilities from one agent/authority to another, mapping CARE constraint envelopes to EATP constraints.

```python
delegation_record = await bridge.delegate(
    delegator_id="authority:my-org.example",
    delegate_agent_config=agent_config,      # AgentConfig
    envelope_config=envelope_config,          # ConstraintEnvelopeConfig
)
# Returns: eatp.chain.DelegationRecord
```

The constraint mapping translates five CARE dimensions to EATP constraint strings:

- Financial: `budget:500.0`, `approval_threshold:50.0`
- Operational: `allow:read`, `block:publish`, `rate_limit:100`
- Temporal: `time:09:00-18:00`
- Data Access: `read:briefs/*`, `write:drafts/*`
- Communication: `comm:internal_only`, `channel:slack`

### verify_action

Verify whether an agent is allowed to perform an action.

```python
result = await bridge.verify_action(
    agent_id="analyst-01",
    action="read",
    resource="briefs/quarterly-report.md",
    level="STANDARD",  # "QUICK", "STANDARD", or "FULL"
)
# Returns: eatp.chain.VerificationResult
# result.valid -> bool
# result.reason -> str
```

### record_audit

Record a tamper-evident audit anchor for a completed action.

```python
anchor = await bridge.record_audit(
    agent_id="analyst-01",
    action="read",
    resource="briefs/quarterly-report.md",
    result="SUCCESS",       # "SUCCESS", "FAILURE", "DENIED", "PARTIAL"
    reasoning="Accessed quarterly report for analysis task",
)
# Returns: eatp.chain.AuditAnchor
```

### Helper Methods

```python
# Get an agent's full trust lineage chain
chain = await bridge.get_trust_chain("analyst-01")
# Returns: eatp.chain.TrustLineageChain | None

# Check if a signing key exists
bridge.has_signing_key("analyst-01")  # -> bool

# Get delegation depth from genesis
bridge.get_transitive_depth("analyst-01")  # -> int (0 = genesis)

# Get ancestor chain back to genesis
bridge.get_delegation_ancestors("analyst-01")  # -> list[str]
```

---

## GenesisManager

**Module**: `care_platform.trust.genesis`

Higher-level operations around genesis records: creation, validation, and renewal.

```python
from care_platform.trust.genesis import GenesisManager

genesis_mgr = GenesisManager(bridge)
```

### create_genesis

```python
genesis_record = await genesis_mgr.create_genesis(genesis_config)
# Returns: eatp.chain.GenesisRecord
```

### validate_genesis

```python
is_valid, message = await genesis_mgr.validate_genesis("authority:my-org.example")
# Returns: tuple[bool, str]
# Example: (True, "Genesis record for agent 'authority:my-org.example' is valid")
```

### renew_genesis

Renew an expired or soon-to-expire genesis record.

```python
new_genesis = await genesis_mgr.renew_genesis(
    authority_id="my-org.example",
    new_signing_key=None,  # Auto-generates new Ed25519 key pair
)
# Returns: eatp.chain.GenesisRecord
# Raises: ValueError if no prior genesis exists
```

---

## DelegationManager

**Module**: `care_platform.trust.delegation`

Manages delegation chains with monotonic tightening validation and chain walking.

```python
from care_platform.trust.delegation import DelegationManager

delegation_mgr = DelegationManager(bridge)
```

### create_delegation

```python
delegation_record = await delegation_mgr.create_delegation(
    delegator_id="authority:my-org.example",
    delegate_config=agent_config,
    envelope_config=envelope_config,
)
# Returns: eatp.chain.DelegationRecord
```

### validate_tightening

Validate that a child envelope is a valid monotonic tightening of a parent envelope.

```python
is_valid, violations = delegation_mgr.validate_tightening(
    parent_envelope=parent_config,
    child_envelope=child_config,
)
# Returns: tuple[bool, list[str]]
# violations example: ["Financial: child budget $1000 exceeds parent budget $500"]
```

Tightening rules:

- Financial: child budget <= parent budget
- Operational: child allowed_actions must be subset of parent; child must include all parent blocked_actions
- Operational: child rate limit <= parent rate limit
- Communication: child cannot remove internal_only or external_requires_approval restrictions

### walk_chain

Walk the trust chain from an agent back to genesis.

```python
from care_platform.trust.delegation import ChainWalkResult, ChainStatus

result = await delegation_mgr.walk_chain("analyst-01")
# Returns: ChainWalkResult
# result.status -> ChainStatus (VALID, BROKEN, EXPIRED, REVOKED)
# result.chain -> list (genesis + delegation records)
# result.depth -> int (delegation depth)
# result.errors -> list[str]
```

---

## Constraint Envelopes

**Module**: `care_platform.constraint.envelope`

### ConstraintEnvelope

Runtime wrapper around `ConstraintEnvelopeConfig` with evaluation logic, versioning, and expiry.

```python
from care_platform.constraint.envelope import ConstraintEnvelope

envelope = ConstraintEnvelope(config=envelope_config)
# Default expiry: 90 days from creation
```

### evaluate_action

Evaluate an agent action against all five constraint dimensions.

```python
from care_platform.constraint.envelope import EvaluationResult

evaluation = envelope.evaluate_action(
    action="draft",
    agent_id="analyst-01",
    spend_amount=25.0,           # For financial dimension
    current_action_count=45,      # For operational rate limit
    data_paths=["briefs/q4.md"],  # For data access dimension
    is_external=False,            # For communication dimension
)
# Returns: EnvelopeEvaluation
# evaluation.overall_result -> EvaluationResult (ALLOWED, NEAR_BOUNDARY, DENIED)
# evaluation.is_allowed -> bool
# evaluation.dimensions -> list[DimensionEvaluation]
```

The overall result is the most restrictive across all five dimensions. Each dimension evaluation includes:

- `dimension` -- which dimension ("financial", "operational", "temporal", "data_access", "communication")
- `result` -- ALLOWED, NEAR_BOUNDARY, or DENIED
- `reason` -- human-readable explanation
- `utilization` -- 0.0 to 1.0 (how close to the limit)

### is_tighter_than

Verify monotonic tightening against a parent envelope.

```python
is_valid = child_envelope.is_tighter_than(parent_envelope)
# Returns: bool
```

### Other Properties

```python
envelope.id                # -> str (from config.id)
envelope.is_expired        # -> bool (checks against 90-day expiry)
envelope.content_hash()    # -> str (SHA-256 of envelope content)
```

---

## Verification Gradient

**Module**: `care_platform.constraint.gradient`

### GradientEngine

Classifies agent actions into verification levels using pattern matching and envelope evaluation.

```python
from care_platform.constraint.gradient import GradientEngine, VerificationThoroughness

engine = GradientEngine(gradient_config)

result = engine.classify(
    action="publish_report",
    agent_id="analyst-01",
    thoroughness=VerificationThoroughness.STANDARD,
    envelope_evaluation=evaluation,  # Optional, from ConstraintEnvelope.evaluate_action
)
# Returns: VerificationResult
# result.level -> VerificationLevel (AUTO_APPROVED, FLAGGED, HELD, BLOCKED)
# result.requires_human_approval -> bool (True if HELD)
# result.is_blocked -> bool (True if BLOCKED)
# result.is_auto_approved -> bool (True if AUTO_APPROVED)
# result.matched_rule -> str | None (the glob pattern that matched)
# result.reason -> str
# result.duration_ms -> float
```

### VerificationThoroughness

```python
VerificationThoroughness.QUICK      # ~1ms, pattern match only
VerificationThoroughness.STANDARD   # ~5ms, pattern match + envelope check
VerificationThoroughness.FULL       # ~50ms, pattern + envelope + chain verification
```

---

## Trust Postures

**Module**: `care_platform.trust.posture`

### TrustPosture

Manages the evolutionary trust lifecycle for an agent.

```python
from care_platform.trust.posture import TrustPosture, PostureEvidence

posture = TrustPosture(
    agent_id="analyst-01",
    current_level=TrustPostureLevel.SUPERVISED,
)
```

### Upgrade Check

```python
evidence = PostureEvidence(
    successful_operations=150,
    total_operations=155,
    days_at_current_posture=95,
    shadow_enforcer_pass_rate=0.92,
    incidents=0,
)

can_upgrade, reason = posture.can_upgrade(evidence)
# Returns: tuple[bool, str]
```

Upgrade requirements:

| Target Level       | Min Days | Min Success Rate | Min Operations | Shadow Pass Rate |
| ------------------ | -------- | ---------------- | -------------- | ---------------- |
| Shared Planning    | 90       | 95%              | 100            | 90%              |
| Continuous Insight | 180      | 98%              | 500            | 95%              |
| Delegated          | 365      | 99%              | 1,000          | 98%              |

### Upgrade and Downgrade

```python
# Upgrade (gradual, evidence-based)
change = posture.upgrade(evidence, reason="Performance criteria met")
# Returns: PostureChange
# Raises: ValueError if not eligible

# Downgrade (instant, on any incident)
change = posture.downgrade(
    reason="Security incident detected",
    to_level=TrustPostureLevel.SUPERVISED,  # Optional, defaults to SUPERVISED
)
# Returns: PostureChange
# Raises: ValueError if target is not below current level
```

### Never-Delegated Actions

Certain actions are always HELD regardless of posture level:

```python
posture.is_action_always_held("financial_decisions")  # -> True
posture.is_action_always_held("read")                 # -> False
```

Never-delegated actions: `content_strategy`, `novel_outreach`, `crisis_response`, `financial_decisions`, `modify_constraints`, `modify_governance`, `external_publication`.

---

## Trust Scoring

**Module**: `care_platform.trust.scoring`

### calculate_trust_score

```python
from care_platform.trust.scoring import TrustFactors, calculate_trust_score

factors = TrustFactors(
    has_genesis=True,
    has_delegation=True,
    has_envelope=True,
    has_attestation=True,
    has_audit_anchor=True,
    delegation_depth=1,
    dimensions_configured=5,
    posture_level=TrustPostureLevel.SHARED_PLANNING,
    newest_attestation_age_days=10,
)

score = calculate_trust_score("analyst-01", factors)
# Returns: TrustScore
# score.overall_score -> float (0.0 to 1.0)
# score.grade -> TrustGrade (A+, A, B+, B, C, D, F)
# score.factors -> dict[str, float] (per-factor breakdown)
```

### Factor Weights

| Factor                | Weight | Description                             |
| --------------------- | ------ | --------------------------------------- |
| `chain_completeness`  | 30%    | Count of 5 EATP elements present        |
| `delegation_depth`    | 15%    | Shorter chains score higher             |
| `constraint_coverage` | 25%    | Dimensions configured out of 5          |
| `posture_level`       | 20%    | Current trust posture level             |
| `chain_recency`       | 10%    | Age of newest attestation vs 90-day max |

---

## Capability Attestation

**Module**: `care_platform.trust.attestation`

### CapabilityAttestation

EATP Element 4 -- a signed declaration of what an agent is authorized to do.

```python
from care_platform.trust.attestation import CapabilityAttestation

attestation = CapabilityAttestation(
    attestation_id="att-001",
    agent_id="analyst-01",
    delegation_id="del-001",
    constraint_envelope_id="analyst-envelope",
    capabilities=["read", "analyze", "draft"],
    issuer_id="authority:my-org.example",
)
# Default expiry: 90 days from issuance
```

### Key Properties and Methods

```python
attestation.is_valid       # -> bool (not revoked and not expired)
attestation.is_expired     # -> bool
attestation.has_capability("read")   # -> bool

# Integrity verification
attestation.content_hash()  # -> str (SHA-256)

# Revocation
attestation.revoke("Security incident")

# Consistency check against envelope
is_consistent, drift = attestation.verify_consistency(
    envelope_capabilities=["read", "analyze", "draft"]
)
# drift contains capabilities in attestation but not in envelope
```

---

## Audit Chain

**Module**: `care_platform.audit.anchor`

### AuditAnchor

A single tamper-evident record. Each anchor contains a SHA-256 hash of its content plus the hash of the previous anchor, forming an integrity chain.

```python
from care_platform.audit.anchor import AuditAnchor, AuditChain
from care_platform.config.schema import VerificationLevel

anchor = AuditAnchor(
    anchor_id="chain-001-0",
    sequence=0,
    previous_hash=None,  # None for genesis anchor
    agent_id="analyst-01",
    action="read",
    verification_level=VerificationLevel.AUTO_APPROVED,
    envelope_id="analyst-envelope",
    result="success",
)
anchor.seal()              # Compute and store SHA-256 content hash
anchor.is_sealed           # -> True
anchor.verify_integrity()  # -> True (hash matches content)
```

### AuditChain

An ordered chain of audit anchors with integrity verification.

```python
chain = AuditChain(chain_id="chain-001")

# Append creates a sealed anchor linked to the previous
anchor = chain.append(
    agent_id="analyst-01",
    action="read",
    verification_level=VerificationLevel.AUTO_APPROVED,
    envelope_id="analyst-envelope",
    result="success",
    metadata={"resource": "briefs/q4.md"},
)

# Chain properties
chain.length   # -> int
chain.latest   # -> AuditAnchor | None

# Integrity verification (walks entire chain)
is_valid, errors = chain.verify_chain_integrity()
# Checks: sequence numbers, content hashes, chain linkage

# Filtering
chain.filter_by_agent("analyst-01")                  # -> list[AuditAnchor]
chain.filter_by_level(VerificationLevel.HELD)        # -> list[AuditAnchor]

# Export for external audit
records = chain.export(agent_id="analyst-01", since=some_datetime)
# -> list[dict] (JSON-serializable)
```

---

## Storage

**Module**: `care_platform.persistence.store`

### TrustStore Protocol

Abstract interface for trust object persistence. Implement this protocol to add custom storage backends.

```python
from care_platform.persistence.store import TrustStore

class MyStore:
    """Custom storage implementation."""

    def store_envelope(self, envelope_id: str, data: dict) -> None: ...
    def get_envelope(self, envelope_id: str) -> dict | None: ...
    def list_envelopes(self, agent_id: str | None = None) -> list[dict]: ...

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None: ...
    def get_audit_anchor(self, anchor_id: str) -> dict | None: ...
    def query_anchors(
        self, *, agent_id=None, action=None, since=None, until=None,
        verification_level=None, limit=100,
    ) -> list[dict]: ...

    def store_posture_change(self, agent_id: str, data: dict) -> None: ...
    def get_posture_history(self, agent_id: str) -> list[dict]: ...

    def store_revocation(self, revocation_id: str, data: dict) -> None: ...
    def get_revocations(self, agent_id: str | None = None) -> list[dict]: ...
```

### Built-in Implementations

```python
from care_platform.persistence.store import MemoryStore, FilesystemStore

# In-memory (development/testing)
store = MemoryStore()

# JSON file-based (single-instance deployments)
store = FilesystemStore("/path/to/trust-data")
# Creates subdirectories: envelopes/, anchors/, posture/, revocations/
```

### Query Anchors

```python
from datetime import datetime, UTC

anchors = store.query_anchors(
    agent_id="analyst-01",
    action="read",
    since=datetime(2026, 1, 1, tzinfo=UTC),
    until=datetime(2026, 3, 1, tzinfo=UTC),
    verification_level="AUTO_APPROVED",
    limit=50,
)
# Returns: list[dict]
```
