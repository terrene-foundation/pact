# Red Team Finding 1004: Solo Founder Approval Bottleneck

**Finding ID**: H-4
**Severity**: High
**Status**: RESOLVED -- mitigations implemented and documented
**Date**: 2026-03-12

---

## Finding

With a solo founder operating 4+ agent teams, every HELD action requires human approval. If the verification gradient produces more HELD items per week than one person can review, the approval queue becomes a bottleneck that stalls agent operations.

## Risk/Impact

**High**. If the founder cannot keep up with the approval queue, one of two outcomes occurs:

1. Agents stall waiting for approval (operations grind to a halt)
2. The founder rubber-stamps approvals to clear the queue (governance becomes theater)

Both outcomes undermine the CARE Platform's core promise: meaningful human governance of AI agents.

## Analysis

### Estimated HELD Volume Per Team

| Team         | Weekly HELD Items                               | Type              |
| ------------ | ----------------------------------------------- | ----------------- |
| DM/Media     | 5-10 external publications, 2-3 outreach emails | Content review    |
| Standards    | 1-2 publication reviews                         | Technical review  |
| Governance   | 1-2 compliance reviews                          | Governance review |
| Partnerships | 2-3 engagement reviews                          | Strategic review  |
| **Total**    | **10-20 items/week**                            | Mixed             |

### Sustainable Review Capacity

| Review Type                                              | Time Per Item | Weekly Volume   |
| -------------------------------------------------------- | ------------- | --------------- |
| Routine (template-based content, standard reports)       | 2-5 minutes   | High            |
| Complex (novel outreach, strategy decisions, compliance) | 15-30 minutes | Low             |
| **Sustainable weekly budget**                            | **2-3 hours** | **20-30 items** |

At current team scale (4 teams), the estimated 10-20 HELD items/week fits within the sustainable capacity of 20-30 items/week. The bottleneck risk increases when additional teams come online or existing teams increase output volume.

### Implemented Mitigations

#### 1. Approval Queue with Urgency and Batch Support

**Location**: `care_platform/execution/approval.py`
**Tests**: `tests/unit/execution/test_approval.py`

The `ApprovalQueue` implements:

- **Urgency-based sorting**: IMMEDIATE items surface first, STANDARD items next, BATCH items last. The founder sees the most time-sensitive items at the top.
- **Batch approval**: `batch_approve()` allows approving multiple similar items in one operation. Routine items (e.g., weekly analytics reports) can be approved as a batch rather than one-by-one.
- **Capacity metrics**: `get_capacity_metrics()` tracks pending count, resolved count, and average resolution time -- providing early warning when the queue is growing faster than it is being cleared.
- **Expiry**: `expire_old()` automatically expires items older than a configurable threshold (default 48 hours), preventing stale items from accumulating indefinitely.

#### 2. Trust Posture Model with DELEGATED Level

**Location**: `care_platform/trust/posture.py`

The trust posture lifecycle provides the structural solution to the bottleneck:

- **SUPERVISED** (Month 1-3): All external actions HELD. Maximum founder load.
- **SHARED_PLANNING** (Month 3-6): Routine actions auto-approved. Founder reviews only novel or boundary-crossing actions.
- **CONTINUOUS_INSIGHT** (Month 6-12): Most actions auto-approved. Founder reviews only flagged items.
- **DELEGATED** (Month 12+, select tasks only): Agent handles routine tasks autonomously. Founder reviews only exceptions.

As agents demonstrate trustworthiness (tracked by ShadowEnforcer metrics), their posture upgrades naturally reduce the approval volume. The bottleneck is worst at the beginning and diminishes over time as the system builds evidence.

**Critical safety**: Certain actions (external publication, crisis response, financial decisions, governance modifications) remain in the `NEVER_DELEGATED_ACTIONS` set and always require human approval regardless of posture level.

#### 3. ShadowEnforcer Evidence for Threshold Tuning

**Location**: `care_platform/trust/shadow_enforcer.py`

The ShadowEnforcer provides empirical data on what percentage of actions would be HELD vs AUTO_APPROVED at different constraint thresholds. This allows the founder to:

- Identify which constraint dimensions trigger HELD most often
- Tune thresholds to reduce false-positive holds (items that always get approved anyway)
- Make evidence-based posture upgrade decisions that safely reduce approval volume

#### 4. Constitutional Governance Expansion

The Terrene Foundation constitution provides for phased governance expansion:

- **Phase 2** (10 Members): Trusted Members can be granted review delegation for specific teams or action types
- **Phase 3** (30+ Members): Full committee-based review with domain expertise

This means the single-founder bottleneck is temporary by design. As the Foundation grows, review capacity scales with membership.

### Overflow Strategy

If HELD volume exceeds capacity before governance expansion:

1. **Priority queue**: External-facing items first (reputation risk), internal items second
2. **Batch approval for patterns**: Items that match previously-approved patterns can be batch-approved
3. **Threshold adjustment**: If a category of items is approved 100% of the time over 30 days, adjust the constraint threshold to auto-approve that category
4. **Emergency delegation**: In Phase 2, a trusted Member can be delegated review authority for specific domains

## Conclusion

The founder bottleneck is a real but manageable risk. At current scale (4 teams, 10-20 HELD items/week), it fits within sustainable capacity. The trust posture lifecycle naturally reduces the load over time. The approval queue implementation provides the tooling for urgency-based triage, batch operations, and capacity monitoring. Constitutional governance expansion provides the structural long-term solution.
