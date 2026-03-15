# M20-T04: Agent status and posture dashboard

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M20 — Frontend Dashboard Views
**Dependencies**: 1804, 1805

## What

Overview of all agents: current posture (PSEUDO_AGENT through DELEGATED), health status, last action, shadow enforcer metrics. Detail view shows posture history and upgrade eligibility.

## Where

- `apps/web/app/agents/page.tsx`
- `apps/web/app/agents/[id]/page.tsx`
- `apps/web/components/agents/PostureBadge.tsx`

## Evidence

- Agent cards show posture; detail view shows history
