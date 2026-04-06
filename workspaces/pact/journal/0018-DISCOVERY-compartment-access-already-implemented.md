---
type: DISCOVERY
date: 2026-04-06
created_at: 2026-04-06T14:30:00+08:00
author: agent
session_id: gh-issues-analysis
session_turn: 15
project: pact
topic: Compartment-based access control already fully implemented at L1 and L3
phase: analyze
tags: [compartments, clearance, access-control, kailash-pact, stale-issue]
---

# Compartment-Based Access Already Implemented

## Finding

GitHub issue #21 requests compartment-based access control for SECRET/TOP_SECRET knowledge. Analysis of L1 source code reveals this is **already fully implemented**:

- **L1 `can_access()` Step 3** (kailash.trust.pact.access.py): Enforces `item.compartments - role_clearance.compartments` check for SECRET and TOP_SECRET items. Produces structured denial with missing compartment details.
- **L1 `RoleClearance`**: Has `compartments: frozenset[str]` field (frozen, immutable).
- **L1 `KnowledgeItem`**: Has `compartments: frozenset[str]` field.
- **L3 clearance router**: Already passes `compartments=frozenset(compartments)` on grant.
- **L3 access router**: Already passes `compartments=frozenset(compartments)` on check.
- **L1 `explain_access()`**: Already includes compartment check results in step-by-step trace.

The issue was filed based on comparison with Aegis, but the capability was already upstreamed to kailash-pact and wired into pact-platform.

## Impact

The issue should be re-scoped from "implement compartment access" to "add KnowledgeRecord persistence model + integration test coverage." This reduces the scope from a multi-session feature to a ~half-session task.

## For Discussion

1. Given that `can_access()` already enforces compartments at Step 3 with full denial reason detail, what specific gap did the issue author observe that led to filing? Was it the absence of a persistent KnowledgeRecord model at L3 (items are currently ephemeral, constructed inline per access check)?

2. If the compartment enforcement had NOT been present in L1 when this issue was filed, would the correct implementation location have been L1 (specification layer) or L3 (platform convenience)? The fact that it was in L1 validates the PACT spec's 5-step algorithm design.

3. How many other Aegis-derived issues might be similarly stale due to upstream migration that already happened? Should we audit all open issues against current L1 API surface before planning implementation?
