# Red Team Finding 1003: Define ShadowEnforcer

**Finding ID**: H-3
**Severity**: Medium
**Status**: RESOLVED -- fully implemented
**Date**: 2026-03-12

---

## Finding

The original red team finding noted that ShadowEnforcer was referenced throughout analysis documents but never fully defined in the CARE Platform context. It was described as an EATP concept requiring SDK Phase 2+.

## Resolution

The ShadowEnforcer is now fully implemented in the CARE Platform codebase with comprehensive tests.

### Implementation

**Location**: `care_platform/trust/shadow_enforcer.py`
**Tests**: `tests/unit/trust/test_shadow_enforcer.py`

The ShadowEnforcer provides parallel trust evaluation that observes without enforcing. It runs verification gradient evaluation alongside normal agent operations, collecting metrics that provide empirical evidence for trust posture upgrades.

### Key Design Decisions

1. **Never blocks, holds, or modifies actions** -- The ShadowEnforcer only records what WOULD have happened under the current constraint configuration. This is critical for safe deployment: you can run it in production without affecting agent operations.

2. **Three data models**:
   - `ShadowResult` -- Result of a single shadow evaluation (action, agent, what would happen, which dimensions triggered)
   - `ShadowMetrics` -- Rolling metrics per agent (total evaluations, pass/block/hold/flag counts, dimension breakdowns)
   - `ShadowReport` -- Human-readable report for posture upgrade decisions (rates, eligibility, blockers, recommendation)

3. **Integration with trust posture lifecycle** -- The `to_posture_evidence()` method converts shadow metrics into `PostureEvidence` that `TrustPosture.can_upgrade()` expects. This is the bridge between shadow observation and trust posture decisions.

4. **Three-phase rollout pattern**:
   - Phase 1: Deploy ShadowEnforcer alongside current operations (2-4 weeks)
   - Phase 2: Tune constraint thresholds based on shadow metrics
   - Phase 3: Switch to StrictEnforcer with evidence-backed confidence

### How It Works

```
Agent performs action
    |
    v
ShadowEnforcer.evaluate(action, agent_id)
    |
    +--> Evaluates through ConstraintEnvelope (5 dimensions)
    +--> Classifies through GradientEngine (AUTO_APPROVED/FLAGGED/HELD/BLOCKED)
    +--> Records ShadowResult
    +--> Updates rolling ShadowMetrics
    |
    v
Action proceeds normally (shadow never blocks)
```

### Metrics Provided

- **Pass rate**: Percentage of actions that would be auto-approved
- **Block rate**: Percentage that would be blocked
- **Hold rate**: Percentage that would require human approval
- **Flag rate**: Percentage that would be flagged for review
- **Dimension breakdown**: Which constraint dimensions trigger most often
- **Upgrade eligibility**: Whether metrics meet SHARED_PLANNING upgrade requirements (90% shadow pass rate, 100+ evaluations, zero blocked actions)

This finding is fully resolved. The implementation exists, is tested, and integrates with the trust posture lifecycle.
