# Getting Started with the CARE Platform

This guide walks you through setting up the CARE Platform from scratch -- from
installation to running your first governed agent team with trust verification and
audit trails.

## Prerequisites

- **Python 3.11 or later** (3.12 and 3.13 are also supported)
- **pip** (included with Python)
- **Git** (for cloning the repository)

Verify your Python version:

```bash
python3 --version
# Python 3.11.x or later
```

## 1. Install the CARE Platform

Clone the repository and install in editable mode:

```bash
git clone https://github.com/terrene-foundation/care.git
cd care
pip install -e .
```

This installs the `care_platform` package along with all dependencies (Kailash SDK,
EATP SDK, cryptography libraries, and CLI tools).

For development (testing, linting, type checking):

```bash
pip install -e ".[dev]"
```

## 2. Configure Your Environment

Copy the environment template and fill in your settings:

```bash
cp .env.example .env
```

Open `.env` in your editor. At minimum, configure one LLM provider:

```bash
# Pick one provider and uncomment its lines:
ANTHROPIC_API_KEY=sk-ant-your-key-here
# or
OPENAI_API_KEY=sk-your-key-here
```

The CARE Platform reads all API keys and model names from `.env` -- nothing is
hardcoded. The root `conftest.py` auto-loads this file for testing as well.

## 3. Define Your Organization in YAML

Every CARE Platform deployment starts with a YAML configuration that describes your
organization structure: the genesis authority (root of trust), constraint envelopes,
agents, teams, and workspaces.

Start with the minimal configuration at `examples/minimal-config.yaml`:

```yaml
name: "My Organization"

genesis:
  authority: "my-org.example"
  authority_name: "My Organization"
```

This is the smallest valid configuration. It establishes the genesis record (the root
of your trust chain) but defines no agents or teams yet.

For a full example with agents, constraint envelopes, and teams, see
`examples/care-config.yaml`.

## 4. Establish the Genesis Authority

The genesis record is the root of trust for your entire organization. It declares
who has ultimate authority over agent delegation. In code, this maps to
`PlatformConfig.genesis`:

```python
from care_platform import PlatformConfig

config = PlatformConfig(
    name="My Organization",
    genesis={
        "authority": "my-org.example",
        "authority_name": "My Organization",
    },
)

print(f"Genesis authority: {config.genesis.authority}")
print(f"Authority name: {config.genesis.authority_name}")
```

The genesis authority is the starting point for all delegation chains. Every agent's
trust traces back to this record.

### Key concept: Trust Lineage

EATP (Enterprise Agent Trust Protocol) defines five elements that form a trust chain:

1. **Genesis Record** -- the root of trust (your organization)
2. **Delegation Record** -- who authorized whom
3. **Constraint Envelope** -- what an agent is allowed to do (five dimensions)
4. **Capability Attestation** -- signed proof of authorized capabilities
5. **Audit Anchor** -- tamper-evident record of every action

## 5. Define Agents with Constraint Envelopes

Agents operate within constraint envelopes that limit their behavior across five
dimensions: Financial, Operational, Temporal, Data Access, and Communication.

Here is an example that defines an agent who can collect metrics and generate
reports, but cannot publish externally:

```python
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
    id="analytics-envelope",
    description="Analytics agent -- read-only metrics, no publishing",
    financial=FinancialConstraintConfig(max_spend_usd=0.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["collect_metrics", "generate_report"],
        blocked_actions=["publish_external", "send_email"],
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
```

### Key concept: Five Constraint Dimensions

Every constraint envelope covers five dimensions:

- **Financial** -- spending limits (e.g., max API cost per billing period)
- **Operational** -- which actions are allowed or blocked, rate limits
- **Temporal** -- when the agent can operate (active hours, blackout periods)
- **Data Access** -- which paths/resources the agent can read or write
- **Communication** -- internal-only vs. external, approval requirements

### Key concept: Monotonic Tightening

When authority is delegated from a parent to a child, the child's constraint
envelope can only be equal to or tighter than the parent's. A child can never expand
its own permissions beyond what the parent granted. This is enforced by
`ConstraintEnvelope.is_tighter_than(parent)`.

## 6. Evaluate Agent Actions

Once you have a constraint envelope, evaluate whether an action is allowed:

```python
from datetime import UTC, datetime

result = envelope.evaluate_action(
    "collect_metrics",
    "analytics-agent",
    current_time=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
)

print(f"Action: collect_metrics")
print(f"Result: {result.overall_result.value}")  # "allowed"
print(f"Allowed: {result.is_allowed}")            # True

# Try a blocked action
blocked = envelope.evaluate_action(
    "publish_external",
    "analytics-agent",
    current_time=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
)

print(f"Action: publish_external")
print(f"Result: {blocked.overall_result.value}")  # "denied"
print(f"Allowed: {blocked.is_allowed}")            # False
```

Each evaluation checks all five dimensions and returns the most restrictive result.

### Key concept: Verification Gradient

The verification gradient classifies every action into one of four levels:

- **AUTO_APPROVED** -- execute immediately and log
- **FLAGGED** -- execute but highlight for review
- **HELD** -- queue for human approval before executing
- **BLOCKED** -- reject outright

## 7. Run Verification

Calculate a trust score that summarizes how well an agent's trust chain is
established:

```python
from care_platform import TrustScore, calculate_trust_score
from care_platform.config.schema import TrustPostureLevel
from care_platform.trust.scoring import TrustFactors

factors = TrustFactors(
    has_genesis=True,
    has_delegation=True,
    has_envelope=True,
    has_attestation=True,
    has_audit_anchor=True,
    delegation_depth=1,
    dimensions_configured=5,
    posture_level=TrustPostureLevel.SUPERVISED,
    newest_attestation_age_days=7,
)

score: TrustScore = calculate_trust_score("analytics-agent", factors)

print(f"Agent: {score.agent_id}")
print(f"Overall Score: {score.overall_score:.2f}")
print(f"Grade: {score.grade.value}")
```

Trust scores are weighted across five factors:

1. **Chain completeness (30%)** -- are all five EATP elements present?
2. **Delegation depth (15%)** -- shorter chains score higher
3. **Constraint coverage (25%)** -- how many of the five dimensions are configured?
4. **Posture level (20%)** -- higher posture (earned through evidence) scores higher
5. **Chain recency (10%)** -- fresher attestations score higher

## 8. Record an Audit Trail

Every agent action should produce an audit anchor -- a tamper-evident record that
chains to the previous record for integrity verification:

```python
from care_platform import AuditChain
from care_platform.config.schema import VerificationLevel

chain = AuditChain(chain_id="analytics-team-chain")

chain.append(
    agent_id="analytics-agent",
    action="collect_metrics",
    verification_level=VerificationLevel.AUTO_APPROVED,
    result="success",
)

chain.append(
    agent_id="analytics-agent",
    action="generate_report",
    verification_level=VerificationLevel.AUTO_APPROVED,
    result="success",
)

# Verify the entire chain is intact
is_valid, errors = chain.verify_chain_integrity()
print(f"Chain length: {chain.length}")        # 2
print(f"Chain valid: {is_valid}")              # True
```

If any record in the chain is tampered with, `verify_chain_integrity()` will detect
it and return the specific errors.

## Troubleshooting

### "My constraint envelope blocks everything"

Check that `allowed_actions` includes the actions your agent needs to perform. If
`allowed_actions` is non-empty, only listed actions are permitted -- everything else
is denied. Also verify that the action is not in `blocked_actions`, which takes
precedence.

### "Actions are denied outside active hours"

The temporal dimension enforces `active_hours_start` and `active_hours_end`. If your
agent operates across time zones, verify the `timezone` setting in the temporal
constraint matches your expectation. Note that evaluation uses the `current_time`
parameter, which should be timezone-aware.

### "Trust score is low despite a complete chain"

Trust scoring weights multiple factors. A low score may come from:

- High delegation depth (deeply nested chains score lower)
- Old attestations (attestations older than 90 days reduce the recency factor)
- Low posture level (agents start at SUPERVISED, which scores 0.25 out of 1.0)
- Incomplete constraint coverage (configure all five dimensions for full score)

### "Audit chain verification fails"

Chain integrity verification checks three things for each anchor:

1. The sequence number is correct (no gaps)
2. The content hash matches the anchor's data (no tampering)
3. The `previous_hash` links to the prior anchor's hash (no reordering)

If verification fails, the error messages will tell you exactly which anchor has the
problem and what type of issue was detected.

## Next Steps

- See `docs/cookbook.md` for complete working examples
- See `examples/quickstart.py` for a runnable script demonstrating all three concepts
- See `examples/care-config.yaml` for a full organization configuration
- Read about the CARE, EATP, and CO standards at [terrene.dev](https://terrene.dev)

## License

The CARE Platform is Apache 2.0 licensed, owned by the Terrene Foundation.
