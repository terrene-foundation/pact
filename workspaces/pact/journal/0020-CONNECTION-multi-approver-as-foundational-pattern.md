---
type: CONNECTION
date: 2026-04-06
created_at: 2026-04-06T14:40:00+08:00
author: agent
session_id: gh-issues-analysis
session_turn: 15
project: pact
topic: Multi-approver (#25) is foundational infrastructure for vetting (#22) and emergency bypass
phase: analyze
tags:
  [
    multi-approver,
    vetting,
    emergency-bypass,
    shared-infrastructure,
    dependencies,
  ]
---

# Multi-Approver as Foundational Pattern

## Connection

Issues #22 and #25 both require multi-approver functionality but at different scopes:

- **#25** (general): Any governance decision (HELD verdict) can require N approvals
- **#22** (specific): Clearance grants at SECRET require 2 approvers, TOP_SECRET requires 3

The connection: #22's clearance-specific multi-approver is a parametric instance of #25's general mechanism. Building #25 first provides the infrastructure that #22 consumes.

Additionally, the existing emergency bypass router could adopt multi-approver for dual-control bypass at higher tiers (Tier 2+), extending the pattern further.

## Architecture

```
MultiApproverService (generic)
    |
    |-- AgenticDecision (governance holds) ← #25
    |-- ClearanceVetting (clearance grants) ← #22
    |-- EmergencyBypass (bypass records)    ← existing, could adopt
    |
ApprovalConfig (per-operation-type thresholds)
ApprovalRecord (individual approver votes)
```

## Build Order Implication

#25 must be implemented before #22. The multi-approver service, ApprovalRecord model, and ApprovalConfig model are shared infrastructure.

A second shared component — ExpiryScheduler — serves #23 (bootstrap), #24 (task envelopes), and #25 (decision timeout). Both shared components should be built in Session 1 before any issue-specific work begins.

## For Discussion

1. The existing emergency bypass router uses a simpler approval model (single `approved_by` field with authority level validation). If multi-approver is adopted for bypass, is the migration from single-approver to multi-approver backward-compatible, or does it require a data migration for existing bypass records?

2. The multi-approver service needs to validate that each approver has sufficient authority for the operation type. For clearance vetting (#22), this means checking the approver's own clearance level. For governance holds (#25), it means checking the approver's role in the org hierarchy. Should authority validation be pluggable (strategy pattern), or is a single approach sufficient?

3. If a 3-of-3 multi-approver decision has 2 approvals and 1 rejection, what happens? Does the entire decision fail (strict consensus), or does it need 3 approvals regardless of rejections (quorum-only)? The issue doesn't specify.
