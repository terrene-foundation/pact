# Todo 2806: Agent Status and Posture Dashboard View

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802

## What

Implement the Agent Status view that lists all agents with their current trust posture level, number of active tasks, count of recent actions (last 24 hours), and posture upgrade progress (percentage of required evidence collected toward the next posture level). Each posture level is displayed as a labelled badge using the canonical EATP names (PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED). Clicking an agent row navigates to an agent detail page showing: full trust record, complete action history, constraint envelope summary, and posture upgrade evidence breakdown. Fetch data from the API via the typed client.

## Where

- `apps/web/src/app/agents/`

## Evidence

- [ ] Agent list displays all registered agents with posture badge, active tasks, recent action count, and upgrade progress
- [ ] Posture badges use the canonical EATP names (no synonyms or abbreviations)
- [ ] Clicking an agent row navigates to the agent detail page
- [ ] Agent detail page shows trust record, action history, constraint summary, and upgrade evidence
- [ ] Data is fetched from the API via the typed client
- [ ] Component tests confirm list rendering, posture badge labels, and navigation to detail page
