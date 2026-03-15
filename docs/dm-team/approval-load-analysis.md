# DM Team Approval Load Analysis (H-4 Mitigation)

**Task**: 608
**Red Team Finding**: H-4 (Solo founder approval bottleneck)
**Date**: 2026-03-12
**Status**: Complete

## Executive Summary

At SUPERVISED posture, the DM team's approval workload is manageable for a solo human operator. Most internal operations (reading, drafting, analyzing) auto-approve. Only external-facing actions (publishing, outreach) require human review. The projected daily approval load is 15-20 actions, requiring approximately 20-30 minutes of review time.

## 1. Daily Action Volume Estimate

### Per-Agent Action Estimates (SUPERVISED Posture)

| Agent | Estimated Daily Actions | Auto-Approved | Flagged | HELD | Blocked |
|-------|------------------------|---------------|---------|------|---------|
| DM Team Lead | 15-20 | 8-10 (draft_strategy, analyze_metrics) | 5-7 (coordinate_team, schedule_content, review_content) | 2-3 (approve_publication) | 0 |
| Content Creator | 15-25 | 12-20 (draft_post, edit_content, research_topic) | 2-4 (suggest_hashtags) | 0 (publish actions blocked by envelope) | 0-1 |
| Analytics Agent | 30-50 | 28-48 (read_metrics, analyze_trends, track_engagement) | 1-2 (generate_report) | 0 | 0 |
| Community Manager | 10-15 | 6-10 (draft_response) | 3-4 (moderate_content, flag_issues, track_community) | 0 (external comms blocked by envelope) | 0 |
| SEO Specialist | 8-12 | 6-10 (analyze_keywords, research_topics) | 2-3 (suggest_structure, audit_seo) | 0 | 0 |

### Total Daily Estimates

| Category | Count | Percentage |
|----------|-------|------------|
| **Total actions/day** | 78-122 | 100% |
| Auto-approved (internal, safe) | 60-98 | ~77% |
| Flagged (review optional) | 13-20 | ~16% |
| **HELD (requires human approval)** | **2-3** | **~3%** |
| Blocked (rejected automatically) | 0-1 | <1% |

## 2. Expected HELD Actions Per Day

At SUPERVISED posture, the only actions that reach HELD status are those that:

1. **Are in the agent's allowed_actions list** (envelope allows them), AND
2. **Match a HELD gradient pattern** (approve_\*, publish_\*, external_\*)

In practice, for the DM team:

- **approve_publication** (Team Lead only): 2-3 per day
  - The team lead reviews and approves content for publication
  - Each approval is a discrete decision point

- **publish_\* and external_\*** actions are in every agent's `blocked_actions` list, so the envelope DENIES them before the gradient can classify them as HELD. They are effectively BLOCKED, not HELD.

**Result: 2-3 HELD actions per day, all from the Team Lead's approve_publication action.**

This is well within a solo operator's capacity. The approval bottleneck identified in H-4 does not materialize at SUPERVISED posture because the constraint envelopes prevent most external actions from even reaching the approval queue.

## 3. Conclusion

At SUPERVISED posture, most internal actions auto-approve. Human reviews are limited to content publication approvals (2-3 per day). The design is intentionally conservative:

- **Internal operations** (read, draft, analyze): Auto-approved, no human involvement needed
- **Coordination operations** (schedule, coordinate, moderate): Flagged for optional review, no blocking
- **External publication**: Only reachable through the Team Lead's approve_publication, which is HELD
- **Destructive operations** (delete, modify constraints): Blocked outright, never reach the queue

## 4. Mitigation Strategy

### Approval Queue with Urgency Levels

The ApprovalQueue already supports three urgency levels:

| Urgency | Use Case | Expected Volume |
|---------|----------|----------------|
| IMMEDIATE | Crisis content, time-sensitive corrections | <1 per week |
| STANDARD | Regular content approvals | 2-3 per day |
| BATCH | Routine templated content | Grouped weekly |

### Batch Approval Support

For routine content that follows approved templates:

- `care-platform approve-batch <action-id-1> <action-id-2> ...` approves multiple items at once
- Routine items (templated content within approved categories) can be batch-approved at the start of each week
- Non-routine items (crisis content, regulatory topics, novel outreach) require individual review

### Rapid Triage Interface (5 Lines per Item)

Each pending action displays:
```
[STANDARD] dm-team-lead | approve_publication
  Preview: "LinkedIn post: EATP SDK v1.0 release announcement..."
  Reason: Approval actions have governance implications
  Action ID: pa-a1b2c3d4
```

### Workload Projection Per Posture Level

| Posture | Daily HELD Actions | Approval Time/Day | Notes |
|---------|-------------------|-------------------|-------|
| **SUPERVISED** (current) | 2-3 | 20-30 min | All external actions require approval |
| SHARED_PLANNING | 1-2 | 10-15 min | Batch approval for routine content |
| CONTINUOUS_INSIGHT | 0-1 | 5 min | Dashboard review only, most actions auto-approved |
| DELEGATED | 0 | 0 min | Full delegation (except never-delegated actions) |

### Escalation Path

If the Founder is unavailable for more than 48 hours:
- HELD actions expire automatically (configurable, default 48h)
- Future governance: backup approver role (requires constitutional mechanism)
- No action proceeds without explicit approval -- safety over speed

## 5. H-4 Resolution

The H-4 finding ("Solo founder approval bottleneck could be unsustainable") is addressed:

1. **At SUPERVISED posture**: Only 2-3 approvals per day. Sustainable for a solo operator.
2. **Posture evolution reduces load**: As agents demonstrate trustworthiness, fewer actions require approval.
3. **Batch approval reduces per-item time**: Routine items can be reviewed in bulk.
4. **48-hour expiry prevents stale queues**: Unapproved actions expire rather than accumulating.
5. **Urgency levels enable triage**: Critical items surface first.

The bottleneck concern is valid at scale (many teams, many agents), but for a single DM team at SUPERVISED posture, the workload is well within the capacity of one person.
