# CARE Platform Cookbook

Working examples for common CARE Platform operations. Each recipe is self-contained
and can be run directly. For the full runnable quickstart, see `examples/quickstart.py`.

---

## Example 1: Setting Up a Minimal Organization

Load a YAML configuration and inspect the resulting platform structure.

```python
from care_platform import PlatformConfig
from care_platform.config.schema import GenesisConfig

# Option A: Build configuration in Python
config = PlatformConfig(
    name="My Organization",
    genesis=GenesisConfig(
        authority="my-org.example",
        authority_name="My Organization",
    ),
)

print(f"Organization: {config.name}")
print(f"Genesis authority: {config.genesis.authority}")
print(f"Teams defined: {len(config.teams)}")
print(f"Agents defined: {len(config.agents)}")
print(f"Constraint envelopes: {len(config.constraint_envelopes)}")
```

```python
# Option B: Load from YAML file
import yaml
from care_platform import PlatformConfig

with open("examples/care-config.yaml") as f:
    raw = yaml.safe_load(f)

config = PlatformConfig(**raw)

print(f"Organization: {config.name}")
print(f"Genesis: {config.genesis.authority}")
print(f"Teams: {[t.id for t in config.teams]}")
print(f"Agents: {[a.id for a in config.agents]}")
```

---

## Example 2: Creating a Delegation Chain

Demonstrate authority flowing from genesis to a team lead to a specialist agent.
Each level has a constraint envelope, and each child envelope must be a monotonic
tightening of the parent.

```python
from care_platform import ConstraintEnvelope
from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)

# Genesis-level envelope: broad permissions for the team lead
team_lead_config = ConstraintEnvelopeConfig(
    id="team-lead-envelope",
    description="Team lead -- coordinates team, reviews drafts",
    financial=FinancialConstraintConfig(max_spend_usd=100.0),
    operational=OperationalConstraintConfig(
        allowed_actions=[
            "coordinate_team",
            "review_drafts",
            "collect_metrics",
            "generate_report",
        ],
        blocked_actions=["publish_external"],
        max_actions_per_day=100,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="08:00",
        active_hours_end="20:00",
        timezone="UTC",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/team/"],
        write_paths=["workspaces/team/drafts/"],
        blocked_data_types=["pii"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

# Specialist envelope: narrower permissions delegated from team lead
specialist_config = ConstraintEnvelopeConfig(
    id="specialist-envelope",
    description="Specialist -- only metrics collection, tighter limits",
    financial=FinancialConstraintConfig(max_spend_usd=0.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["collect_metrics", "generate_report"],
        blocked_actions=["publish_external", "coordinate_team"],
        max_actions_per_day=20,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="09:00",
        active_hours_end="18:00",
        timezone="UTC",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/team/analytics/"],
        write_paths=["workspaces/team/drafts/reports/"],
        blocked_data_types=["pii"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

parent = ConstraintEnvelope(config=team_lead_config)
child = ConstraintEnvelope(config=specialist_config)

# Verify the delegation is valid (child is tighter than parent)
is_valid = child.is_tighter_than(parent)
print(f"Delegation chain valid (monotonic tightening): {is_valid}")
# Output: Delegation chain valid (monotonic tightening): True
```

The delegation chain works because the specialist envelope:

- Has a lower spending limit (0.0 vs 100.0)
- Has fewer allowed actions (subset of parent)
- Has more blocked actions (superset of parent)
- Has narrower active hours (09:00-18:00 vs 08:00-20:00)
- Maintains the same communication restrictions

---

## Example 3: Verifying an Agent Action

Evaluate an action against a constraint envelope and inspect the per-dimension
results.

```python
from datetime import UTC, datetime

from care_platform import ConstraintEnvelope, EvaluationResult
from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)

envelope_config = ConstraintEnvelopeConfig(
    id="verifier-demo",
    description="Demo envelope for action verification",
    financial=FinancialConstraintConfig(max_spend_usd=50.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["collect_metrics", "generate_report"],
        blocked_actions=["publish_external"],
        max_actions_per_day=20,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="09:00",
        active_hours_end="18:00",
        timezone="UTC",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/analytics/"],
        write_paths=["workspaces/reports/"],
        blocked_data_types=["pii"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

envelope = ConstraintEnvelope(config=envelope_config)

# Evaluate an allowed action during active hours
result = envelope.evaluate_action(
    "collect_metrics",
    "analytics-agent",
    spend_amount=5.0,
    current_time=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
)

print(f"Action: {result.action}")
print(f"Overall result: {result.overall_result.value}")
print(f"Allowed: {result.is_allowed}")
print()

# Inspect each dimension
for dim in result.dimensions:
    print(f"  {dim.dimension}: {dim.result.value}"
          + (f" -- {dim.reason}" if dim.reason else ""))
```

The evaluation checks all five dimensions and returns the most restrictive result.
If any dimension returns DENIED, the overall result is DENIED.

---

## Example 4: Monotonic Tightening Validation

Demonstrate the rule that child envelopes can never expand permissions beyond
the parent.

```python
from care_platform import ConstraintEnvelope
from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
)

parent_config = ConstraintEnvelopeConfig(
    id="parent",
    financial=FinancialConstraintConfig(max_spend_usd=100.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["read", "write", "delete"],
        blocked_actions=["admin"],
        max_actions_per_day=50,
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

# Valid child: tighter than parent
valid_child_config = ConstraintEnvelopeConfig(
    id="valid-child",
    financial=FinancialConstraintConfig(max_spend_usd=50.0),  # tighter
    operational=OperationalConstraintConfig(
        allowed_actions=["read", "write"],  # subset of parent
        blocked_actions=["admin", "delete"],  # superset of parent
        max_actions_per_day=25,  # tighter
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

# Invalid child: tries to expand permissions
invalid_child_config = ConstraintEnvelopeConfig(
    id="invalid-child",
    financial=FinancialConstraintConfig(max_spend_usd=200.0),  # WIDER than parent
    operational=OperationalConstraintConfig(
        allowed_actions=["read", "write", "delete", "admin"],  # adds "admin"
        blocked_actions=[],  # removes parent blocks
    ),
    communication=CommunicationConstraintConfig(
        internal_only=False,  # relaxes restriction
        external_requires_approval=False,
    ),
)

parent = ConstraintEnvelope(config=parent_config)
valid = ConstraintEnvelope(config=valid_child_config)
invalid = ConstraintEnvelope(config=invalid_child_config)

print(f"Valid child is tighter than parent: {valid.is_tighter_than(parent)}")
# Output: True

print(f"Invalid child is tighter than parent: {invalid.is_tighter_than(parent)}")
# Output: False
```

This is a core EATP invariant: delegation can only narrow authority, never expand
it. The `is_tighter_than` method checks financial limits, allowed/blocked actions,
rate limits, and communication restrictions.

---

## Example 5: Walking a Trust Chain

Build an audit chain, append actions, then walk the chain to verify integrity.

```python
from care_platform import AuditAnchor, AuditChain
from care_platform.config.schema import VerificationLevel

# Create a new chain
chain = AuditChain(chain_id="content-team-2026-03")

# Record several agent actions
chain.append(
    agent_id="content-creator",
    action="draft_linkedin_post",
    verification_level=VerificationLevel.AUTO_APPROVED,
    result="success",
    metadata={"topic": "EATP trust model overview"},
)

chain.append(
    agent_id="content-creator",
    action="format_content",
    verification_level=VerificationLevel.AUTO_APPROVED,
    result="success",
)

chain.append(
    agent_id="content-creator",
    action="publish_external",
    verification_level=VerificationLevel.BLOCKED,
    result="denied",
    metadata={"reason": "Action blocked by constraint envelope"},
)

# Walk the chain and verify integrity
is_valid, errors = chain.verify_chain_integrity()

print(f"Chain ID: {chain.chain_id}")
print(f"Chain length: {chain.length}")
print(f"Integrity valid: {is_valid}")
print()

# Walk each anchor
for anchor in chain.anchors:
    print(f"  [{anchor.sequence}] {anchor.agent_id}: {anchor.action} "
          f"-> {anchor.verification_level.value} ({anchor.result})")
    print(f"       Hash: {anchor.content_hash[:16]}...")
    if anchor.previous_hash:
        print(f"       Prev: {anchor.previous_hash[:16]}...")
    else:
        print(f"       Prev: (genesis)")
print()

# Filter by verification level
blocked = chain.filter_by_level(VerificationLevel.BLOCKED)
print(f"Blocked actions: {len(blocked)}")
for a in blocked:
    print(f"  {a.action} by {a.agent_id}")
```

Each anchor in the chain contains a SHA-256 hash of its content plus a reference to
the previous anchor's hash. This forms a tamper-evident chain: if any record is
modified, the hash chain breaks and `verify_chain_integrity()` reports the exact
point of tampering.

---

## Example 6: Audit Trail Recording

Record a complete audit trail for a work session, then export it for review.

```python
from datetime import UTC, datetime

from care_platform import AuditChain
from care_platform.config.schema import VerificationLevel

chain = AuditChain(chain_id="dm-team-session-001")

# Morning: analytics agent collects metrics (auto-approved)
chain.append(
    agent_id="dm-analytics",
    action="collect_metrics",
    verification_level=VerificationLevel.AUTO_APPROVED,
    result="success",
    metadata={"source": "linkedin", "metrics_count": 42},
)

# Content creator drafts a post (auto-approved)
chain.append(
    agent_id="dm-content-creator",
    action="draft_linkedin_post",
    verification_level=VerificationLevel.AUTO_APPROVED,
    result="success",
    metadata={"topic": "weekly insights"},
)

# Content creator attempts external publication (blocked by envelope)
chain.append(
    agent_id="dm-content-creator",
    action="publish_external",
    verification_level=VerificationLevel.BLOCKED,
    result="denied",
    metadata={"reason": "Blocked action in constraint envelope"},
)

# Team lead reviews draft (auto-approved)
chain.append(
    agent_id="dm-team-lead",
    action="review_drafts",
    verification_level=VerificationLevel.AUTO_APPROVED,
    result="approved",
)

# Verify chain integrity before export
is_valid, errors = chain.verify_chain_integrity()
assert is_valid, f"Chain integrity failed: {errors}"

# Export full chain for audit review
full_export = chain.export()
print(f"Full chain export: {len(full_export)} records")

# Export filtered by agent
analytics_export = chain.export(agent_id="dm-analytics")
print(f"Analytics agent records: {len(analytics_export)}")

# Export filtered by time (records since a specific timestamp)
since_time = datetime(2026, 3, 12, 0, 0, tzinfo=UTC)
recent_export = chain.export(since=since_time)
print(f"Records since {since_time.date()}: {len(recent_export)}")

# Each exported record includes all fields for regulatory review
if full_export:
    sample = full_export[0]
    print(f"\nSample record fields: {list(sample.keys())}")
```

The export produces a list of dictionaries, each containing the complete anchor
data in JSON-serializable form. This is suitable for regulatory review,
compliance reporting, or external audit tools.

---

## Further Reading

- `docs/getting-started.md` -- step-by-step installation and setup guide
- `examples/quickstart.py` -- runnable script combining envelope, trust, and audit
- `examples/care-config.yaml` -- full Terrene Foundation organization configuration
- `examples/minimal-config.yaml` -- smallest valid configuration
