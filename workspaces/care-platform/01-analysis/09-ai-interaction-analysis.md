# AI Interaction Pattern Analysis: CARE Platform Dashboard

**Date**: 2026-03-15
**Status**: Complete
**Scope**: Analysis of AI-specific UX patterns in the CARE Platform governance dashboard

---

## Executive Summary

The CARE Platform is not a typical AI interface where users prompt and receive outputs. It is a **trust governance interface** where humans supervise autonomous AI agents operating within cryptographic constraint envelopes. This inverts the standard AI UX paradigm: rather than "human directs AI," the pattern is "AI acts autonomously; human monitors, constrains, and intervenes."

This distinction demands AI interaction patterns different from those in conversational AI, generative AI, or copilot interfaces. The core user question is not "what should I ask the AI?" but "what is the AI doing, can I trust it, and should I let it continue?"

The current implementation provides a solid structural foundation -- 10 navigation sections, real-time WebSocket events, verification gradient visualization, constraint envelope gauges, and approval queue mechanics. But the analysis identifies six critical gaps where AI-specific interaction patterns are needed to transform the dashboard from an information display into a trust governance instrument.

---

## Interaction Context

**AI interaction type**: Agentic (primary) + Analytical (secondary)

The CARE Platform represents the most demanding AI UX category: autonomous agents executing real actions with real consequences, governed by cryptographic trust infrastructure. Users are not generating content or having conversations -- they are exercising governance authority over AI agents that are already operating.

**Trust requirements**: Critical

This is enterprise governance over AI systems. Decisions made in this interface (approve/reject actions, adjust trust postures, modify constraints) have irreversible operational consequences. Every interaction must be backed by verifiable evidence and cryptographic proof.

**User expertise**: Mixed

Governance officers may understand trust policy deeply but not technical details of constraint envelopes. Technical operators may understand the system architecture but not governance implications. The interface must serve both.

**Compute/cost impact**: Medium-High

Agent actions consume real resources (API calls, data operations, external communications). Cost transparency is already partially addressed via the Cost Report page, but needs tighter integration with the approval flow.

---

## Analysis by Dimension

### 1. Trust and Transparency

**Pattern assessment**: The current codebase has the right structural elements but lacks the interpretive layer that transforms raw data into trust signals.

**What exists and works well:**

- `PostureBadge` component with five distinct color-coded posture levels and descriptions
- `StatusBadge` component covering verification levels, trust postures, bridge status, and agent status
- `TrustChainGraph` showing genesis-to-delegation hierarchy grouped by team
- `GradientChart` with four-level verification distribution (AUTO_APPROVED, FLAGGED, HELD, BLOCKED)
- `ConstraintGauge` with green/yellow/red utilization thresholds (0-60%, 61-80%, 81%+)
- All five EATP Trust Lineage Chain elements represented in the type system

**What is missing:**

**Gap 1.1 -- No trend communication.** The verification gradient shows current counts but not trajectory. A governance officer cannot tell whether HELD actions are increasing (agent is pushing boundaries, possible drift) or decreasing (agent is learning, trust is well-calibrated). Without trend data, the numbers are snapshots, not governance intelligence.

- **Pattern needed**: Stream of Thought applied to system health -- show the trust trajectory, not just the current state. A sparkline or directional indicator next to each verification level count would communicate whether the system is stable, improving, or deteriorating.

**Gap 1.2 -- No trust posture explanation in context.** The `PostureBadge` uses `title` attribute for descriptions ("Minimal autonomy, maximum oversight"), but this information is only visible on hover and is not actionable. When a governance officer sees an agent at SHARED_PLANNING, they need to immediately understand: what can this agent do without asking? What requires approval? What is completely off-limits?

- **Pattern needed**: Disclosure + Caveat pattern. Each posture badge, when in a detail view, should expand to show the concrete operational implications: "This agent can publish content to internal channels without approval. External publishing requires your sign-off. Financial commitments above $500 are blocked."

**Gap 1.3 -- No ShadowEnforcer surface.** The brief identifies the ShadowEnforcer Dashboard as a key interaction pattern, but it has no component or page in the current codebase. The ShadowEnforcer concept -- showing what agents WOULD do versus what they actually do -- is a critical trust-building pattern. Without it, humans cannot calibrate whether constraint boundaries are set correctly.

- **Pattern needed**: A Variations-style comparison view showing "what the agent attempted" versus "what the system permitted." This is the single most important trust-building feature for governance because it answers: "Are my constraints actually working? Are they too tight? Too loose?"

**Gap 1.4 -- Trust chain verification is passive.** The `TrustChainGraph` displays the chain hierarchy but does not expose the cryptographic verification that makes it meaningful. Users see a tree of agents grouped by team with status dots, but cannot verify chain integrity -- the thing that distinguishes EATP governance from a simple admin panel.

- **Pattern needed**: Citations and References pattern. Each node in the trust chain should link to its Genesis Record, Delegation Record, and most recent Audit Anchor. A "Verify Chain" action should perform cryptographic verification and display the result prominently, similar to the TrustLog verification bundle concept from the persona analysis.

---

### 2. Human-in-the-Loop (Approval Queue)

**Pattern assessment**: The approval queue has correct mechanics but is not designed for time-sensitive governance decisions under pressure.

**What exists and works well:**

- `ApprovalCard` with action description, agent link, team, reason, urgency, and timestamp
- `ApprovalActions` with approve/reject buttons, processing state, and error handling
- `URGENCY_COLORS` mapping (low/medium/high/critical) with appropriate color semantics
- Relative time formatting ("Just now", "5m ago", "2h ago")
- Summary bar showing pending count and resolved-this-session count
- Grid layout (responsive: 1/2/3 columns)

**What is missing:**

**Gap 2.1 -- No urgency-based sorting or visual hierarchy.** All approval cards render in the same grid with equal visual weight. A critical action that has been waiting for 2 hours looks identical in layout terms to a low-priority action submitted just now. Urgency badges exist but do not drive layout or ordering.

- **Pattern needed**: Action Plan pattern with urgency triage. Critical items should be visually separated (top of page, larger card, distinct border treatment) or the queue should be sortable/groupable by urgency. The "critical" urgency color (red) already exists in `URGENCY_COLORS` but has no structural elevation.

**Gap 2.2 -- No decision context for the approver.** The card shows `action`, `reason`, and `agent_id`, but a governance officer approving an action needs more: What is the agent's current constraint utilization? What is the agent's track record? What happens if this is approved versus rejected? What is the cost?

- **Pattern needed**: Action Plan (advisory mode). Before approving, the officer should see a compact summary: constraint utilization for the relevant dimension (e.g., "This agent has used $340 of $500 financial budget"), the agent's recent approval history (e.g., "3 of last 5 HELD actions approved"), and the consequence of approval (e.g., "Approving will publish content to the external Twitter channel").

**Gap 2.3 -- No conditional approval.** The current flow is binary: approve or reject. But governance often requires nuance: "Approve this, but reduce the agent's daily action limit." "Approve this once, but flag it for review if it happens again." "Approve this, but add a caveat to the output."

- **Pattern needed**: Tuners within the approval flow. After clicking approve, offer a lightweight panel: "Approve as-is" / "Approve with conditions" (attach a note, adjust a constraint, add a temporary override).

**Gap 2.4 -- No SLA visibility.** Some HELD actions may have time sensitivity -- an agent needs to publish content during a specific window, or a financial transaction has a deadline. There is no indication of how long the action has been held or whether there is a deadline.

- **Pattern needed**: Controls pattern (time-awareness). Show elapsed time since submission prominently. If the action has a temporal constraint (from the Temporal dimension of the constraint envelope), show the deadline. Alert visually when an action is approaching staleness.

**Gap 2.5 -- No batch operations.** When multiple routine actions from the same agent or team are held, the officer must approve each individually. For organizations with many agents, this does not scale.

- **Pattern needed**: Chained Actions pattern. Allow "Approve all from [agent] today" or "Approve all [low urgency] actions" with a single confirmation gate.

---

### 3. AI State Communication

**Pattern assessment**: The dashboard shows what agents exist and their static properties, but not what they are actively doing.

**What exists and works well:**

- Agent list page with status counts (active/suspended/revoked)
- Agent detail page with posture, capabilities, and posture history
- WebSocket connection status indicator in the Header component
- Real-time event types defined: `audit_anchor`, `held_action`, `posture_change`, `bridge_status`, `verification_result`, `workspace_transition`
- Overview page with summary stat cards (active agents, pending approvals, workspaces, total verifications)

**What is missing:**

**Gap 3.1 -- No real-time activity feed.** The WebSocket infrastructure exists (`useWebSocket` hook, `PlatformEvent` type, six event types) but there is no visible activity feed component. The WebSocket state is shown as a connection dot in the header, but events themselves are not rendered anywhere. This is the most significant state communication gap: agents are operating in real time, but the dashboard shows only periodic snapshots.

- **Pattern needed**: Stream of Thought pattern adapted for multi-agent governance. A live activity feed showing agent actions as they happen: "[Content Strategist] Published blog post to internal review (AUTO_APPROVED)" / "[Social Media Agent] Attempted external post -- HELD for approval" / "[Analytics Agent] Accessed workspace data (AUTO_APPROVED)". This feed is the heartbeat of the governance interface.

**Gap 3.2 -- No agent activity state.** The agent card shows `status` (active/suspended/revoked) and `posture`, but not what the agent is currently doing. An "active" agent could be idle, executing a task, waiting for approval, or in error state. There is no runtime state communication.

- **Pattern needed**: AI State Communication. Each agent card should show current activity: "Idle" / "Executing: content generation" / "Waiting: approval for external publish" / "Error: API rate limit exceeded". This is the difference between a roster and an operations dashboard.

**Gap 3.3 -- No constraint utilization on the overview.** The overview page shows total agents, pending approvals, workspaces, and total verifications. But it does not show constraint health -- are any agents approaching their financial limits? Are any near their daily action caps? This is the governance equivalent of monitoring CPU/memory -- without it, problems are discovered only after they become HELD or BLOCKED actions.

- **Pattern needed**: Aggregate constraint health dashboard. Show the top 3-5 agents closest to any constraint boundary, with their utilization percentage. This creates early warning before actions start getting HELD.

---

### 4. Wayfinding

**Pattern assessment**: Navigation structure is comprehensive but uniform. The sidebar lists 10 sections with equal visual weight, and there is no guidance for incident-driven workflows.

**What exists and works well:**

- `Sidebar` with 10 clearly labeled navigation items, each with distinct icons
- `DashboardShell` providing consistent layout across all pages
- Breadcrumb navigation on every page
- Quick Navigation section on the overview page with descriptions
- WebSocket connection status visible in the header

**What is missing:**

**Gap 4.1 -- No urgency-driven wayfinding.** When an incident occurs (agent BLOCKED, critical HELD action, constraint breach), the governance officer arrives at the dashboard and sees the same neutral layout as during normal operations. There is no visual alarm, no highlighted path to the problem, no triage guidance.

- **Pattern needed**: Nudges pattern applied to governance. When there are critical HELD actions, the Approvals nav item should show a badge count. When a constraint is at 80%+ utilization, the relevant agent or envelope should surface on the overview. When an agent is BLOCKED, the overview should show an alert banner with a direct link.

**Gap 4.2 -- No cross-page context linking.** The pages are relatively siloed. The approval card shows an `agent_id` link, and the agent detail shows an `envelope_id` link, but there is no flowing path: "This HELD action was triggered because this agent hit this constraint boundary in this envelope." The user must manually navigate between pages to assemble the full picture.

- **Pattern needed**: Contextual wayfinding. Each entity (agent, envelope, action, bridge) should show its relationships inline. The approval card should show a compact constraint summary. The agent detail should show recent HELD/BLOCKED actions. The envelope detail should show which agents are bound to it and their utilization.

**Gap 4.3 -- No incident workflow.** For a governance officer responding to a problem, the natural workflow is: (1) See the alert. (2) Understand the context. (3) Make a decision. (4) Verify the outcome. The dashboard supports step 3 (approval queue) but does not guide through the sequence.

- **Pattern needed**: Suggestions pattern for governance. When viewing a HELD action, suggest next steps: "View this agent's constraint envelope" / "Check this agent's recent history" / "See similar actions from other agents." This reduces cognitive load during time-sensitive decisions.

---

### 5. Control Granularity

**Pattern assessment**: Controls exist for the approval binary (approve/reject) and constraint envelopes are visible, but there is no mechanism for humans to adjust constraints or postures through the UI.

**What exists and works well:**

- Five-dimension constraint envelope display with gauges (Financial, Operational, Temporal, Data Access, Communication)
- Trust posture display with full history timeline
- Approve/reject controls on held actions
- Bridge creation wizard (bridges/create page)

**What is missing:**

**Gap 5.1 -- No posture adjustment control.** The agent detail page shows posture and posture history (who changed it, when, and why) but provides no mechanism to change the posture. This is a critical governance function -- upgrading an agent from SUPERVISED to SHARED_PLANNING after it demonstrates reliability, or downgrading an agent from CONTINUOUS_INSIGHT to SUPERVISED after an incident. The data model supports it (`PostureChange` type has `changed_by` and `reason`), but there is no UI control.

- **Pattern needed**: Verification + Tuners pattern. A "Change Posture" action with: (a) dropdown to select new posture, (b) required reason text field, (c) impact preview ("This will allow the agent to execute content publishing without per-action approval"), (d) confirmation gate. The action should create a signed posture change record in the audit trail.

**Gap 5.2 -- No constraint envelope editing.** The envelope detail page (`envelopes/[id]`) shows five dimension gauges as read-only displays. There is no mechanism to adjust constraint boundaries -- changing the financial cap, adding a blocked action, modifying the temporal window. These are the governance levers that define the trust boundary.

- **Pattern needed**: Parameters pattern with Verification gates. Editable constraint fields with clear before/after comparison, impact preview ("Increasing the daily action limit from 50 to 100 will double this agent's autonomous capacity"), and mandatory justification before committing. Changes should produce audit anchors.

**Gap 5.3 -- No agent suspension/revocation control.** The agent detail page shows status but provides no mechanism to suspend or revoke an agent. During an incident, the governance officer needs an emergency stop.

- **Pattern needed**: Controls pattern (stop/pause). A prominent "Suspend Agent" action with confirmation and mandatory reason. For critical situations, a "Revoke" action with stronger confirmation. Both should produce immediate effect and audit trail entries.

**Gap 5.4 -- No delegation creation.** The trust chain page shows existing delegations but provides no mechanism to create new ones. Establishing a new agent delegation is a governance act that should flow through the UI with appropriate ceremony -- selecting the team, defining capabilities, setting initial posture, attaching a constraint envelope.

- **Pattern needed**: Action Plan (contractual mode). A multi-step delegation wizard: (1) Select team and define agent role. (2) Declare capabilities. (3) Attach or create constraint envelope. (4) Set initial trust posture with justification. (5) Review and confirm. Each step should preview the trust implications.

---

### 6. Proof and Verification

**Pattern assessment**: The audit trail captures the right data (anchor ID, agent, action, verification level, timestamp) but does not expose the cryptographic properties that make EATP auditing meaningful.

**What exists and works well:**

- `AuditTable` with sortable columns: Time, Agent, Action, Level, Anchor ID
- `AuditFilters` with agent search, verification level dropdown, and date range
- Anchor IDs shown (truncated to 12 characters)
- Verification level badges on each row
- Client-side filtering and result count

**What is missing:**

**Gap 6.1 -- No cryptographic verification.** The audit trail shows anchor IDs but does not verify them. In EATP, each Audit Anchor contains the hash of the previous anchor, forming a tamper-evident chain. The dashboard should verify this chain and communicate the result -- "Chain integrity verified: all 847 anchors form an unbroken sequence" or "Chain break detected at anchor 523."

- **Pattern needed**: Citations and References + Verification pattern. Each anchor row should have a "Verify" action or status indicator. The page should have a "Verify Full Chain" action with progress indication and clear pass/fail result. This is what distinguishes the CARE Platform from a standard log viewer.

**Gap 6.2 -- No anchor detail view.** Clicking an anchor ID does nothing. The truncated ID suggests there is more to see, but there is no detail view showing the full anchor content: parent anchor reference, content hash, signature, constraint state at time of anchoring.

- **Pattern needed**: Each anchor should expand or link to a detail view showing: (a) full anchor ID and parent anchor ID, (b) hash chain linkage visualization, (c) constraint envelope state at time of action, (d) the verification level reasoning (why was this FLAGGED rather than AUTO_APPROVED?), (e) cryptographic signature verification status.

**Gap 6.3 -- No audit export.** The persona analysis identifies the External Auditor persona -- someone who needs to independently verify the trust chain without accessing the live dashboard. The current audit page has no export mechanism for generating verification bundles.

- **Pattern needed**: An "Export Audit Report" action producing a self-contained verification bundle: chain data, embedded verification logic, human-readable summary. This matches the `VerificationBundle` concept from the TrustLog persona analysis.

**Gap 6.4 -- No cost audit integration.** The sidebar includes "Cost Report" but no corresponding page or component exists in the codebase. Financial constraint utilization is visible per-envelope but there is no aggregate cost view across agents and teams. For enterprise governance, cost accountability is non-negotiable.

- **Pattern needed**: Cost Estimates pattern applied to audit. Show cumulative cost by agent, by team, by time period. Flag agents approaching financial constraint limits. Connect cost spikes to specific audit anchors and actions.

---

## What Makes This Different from a Generic Dashboard

The analysis above identifies AI-specific patterns needed, but the deeper insight is that the CARE Platform dashboard operates under a fundamentally different UX contract than typical AI interfaces or standard enterprise dashboards.

**Standard AI interface**: "The user is in control. The AI waits for instruction."
**CARE Platform**: "The AI agents are already operating. The human is monitoring, constraining, and intervening."

This inversion has three UX implications:

### Implication A: The default state is autonomous operation

Most of the time, the dashboard should communicate "everything is operating within boundaries." The verification gradient (mostly green AUTO_APPROVED) is the normal state. The design must make normal operation feel calm and legible, while making deviations (FLAGGED, HELD, BLOCKED) immediately visible without creating alert fatigue.

The current codebase handles the calm state well (green empty-state messages, clean summary cards). It does not yet handle the deviation state -- there is no visual escalation when things require attention.

### Implication B: Trust is earned over time, not granted

The trust posture system (PSEUDO_AGENT through DELEGATED) represents a governance journey. The posture history on the agent detail page captures this journey, but the interface does not support the governance officer's decision-making about posture changes. The officer needs evidence: "This agent has operated at SUPERVISED for 30 days with zero HELD actions and zero BLOCKED actions. It is a candidate for upgrade to SHARED_PLANNING."

No current component synthesizes operational history into trust evidence for posture decisions.

### Implication C: Cryptographic proof is the value proposition

The CARE Platform's differentiator is not that it shows agent status (any admin panel does that). It is that every action, every delegation, every constraint boundary is cryptographically anchored. The audit trail is not a log -- it is a chain of mathematical proofs.

The current audit page presents this chain as a sortable table. The cryptographic verification -- the feature that justifies the entire EATP trust infrastructure -- is not exposed in the UI. This is the highest-priority gap: without verification, the dashboard is a log viewer with extra colors.

---

## Priority Recommendations

Ordered by impact on the core governance experience:

| Priority | Gap | Pattern                                   | Rationale                                                                                                             |
| -------- | --- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1        | 3.1 | Real-time activity feed                   | Without this, agents operate invisibly. The governance officer has no heartbeat.                                      |
| 2        | 6.1 | Cryptographic chain verification          | Without this, the audit trail is a log, not a proof system. The EATP value proposition is invisible.                  |
| 3        | 2.2 | Decision context on approval cards        | Without this, approvers decide blindly. The approval queue is a button, not a governance instrument.                  |
| 4        | 5.1 | Posture adjustment controls               | Without this, the most important governance lever (trust calibration) cannot be exercised through the UI.             |
| 5        | 4.1 | Urgency-driven wayfinding                 | Without this, incidents and normal operations look the same. Response time degrades.                                  |
| 6        | 1.3 | ShadowEnforcer dashboard                  | Without this, governance officers cannot calibrate constraints. They fly blind on whether boundaries are right-sized. |
| 7        | 5.2 | Constraint envelope editing               | Without this, constraint changes require backend access, bypassing the governance ceremony.                           |
| 8        | 5.3 | Agent suspension/revocation controls      | Without this, emergency stops require backend access -- unacceptable during incidents.                                |
| 9        | 1.1 | Trend indicators on verification gradient | Without this, governance is reactive (responding to HELD actions) not proactive (anticipating boundary pressure).     |
| 10       | 6.2 | Anchor detail view                        | Without this, auditors cannot drill into specific events for investigation.                                           |

---

## Anti-Pattern Check

Verification that the current implementation avoids known AI UX anti-patterns:

| Anti-Pattern                        | Status                                                                                                                                                                                              | Notes                                                                                                                                                                                                                                                                                                        |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Anthropomorphism without disclosure | Not applicable                                                                                                                                                                                      | Agents are clearly labeled as AI agents throughout. PostureBadge, StatusBadge, and all page descriptions explicitly identify agents as AI.                                                                                                                                                                   |
| Sycophancy                          | Not applicable                                                                                                                                                                                      | No conversational AI; agents act, humans govern.                                                                                                                                                                                                                                                             |
| Caveat blindness                    | **At risk**                                                                                                                                                                                         | The page descriptions include appropriate caveats ("Actions that exceeded a soft constraint limit"), but there is no contextual caveat on individual decisions. An approver should see: "This action was HELD because the agent's financial spend would exceed $500. The current budget utilization is 68%." |
| Black-box memory                    | **Not applicable yet**                                                                                                                                                                              | No memory/context system exists. If agent memory is added, it must have user-visible, user-controllable storage.                                                                                                                                                                                             |
| Silent downgrades                   | Not applicable                                                                                                                                                                                      | No model management in the governance layer.                                                                                                                                                                                                                                                                 |
| Overwriting without confirmation    | **Clean**                                                                                                                                                                                           | Approve/reject have distinct states and cannot be undone accidentally. Bridge creation is a multi-step wizard.                                                                                                                                                                                               |
| Photorealistic avatars for text AI  | **Clean**                                                                                                                                                                                           | No avatars. Agents are represented by name, role, and posture badge -- appropriate for enterprise governance.                                                                                                                                                                                                |
| Compute-heavy without draft mode    | **At risk**                                                                                                                                                                                         | Agent actions may be compute-heavy, but there is no preview/draft mechanism before approval grants execution permission.                                                                                                                                                                                     |
| Dead-end conversations              | Not applicable to governance flow, but **at risk** in a related sense: after approving an action, there is no "what happened next?" follow-up. The approver clicks approve and the card disappears. |
| Scattered controls                  | **Clean**                                                                                                                                                                                           | Approve/reject buttons are consistently placed in ApprovalActions. Page actions are consistently in the header right side.                                                                                                                                                                                   |

---

## Component Inventory and Pattern Mapping

Mapping existing components to AI interaction patterns for implementation planning:

| Component           | Current Purpose             | AI Pattern Applied        | Pattern Gaps                                       |
| ------------------- | --------------------------- | ------------------------- | -------------------------------------------------- |
| `ApprovalCard`      | Display HELD action         | Action Plan (advisory)    | Missing context, missing conditional approval      |
| `ApprovalActions`   | Approve/reject buttons      | Controls (binary)         | Missing conditional approval, missing batch        |
| `PostureBadge`      | Display trust posture       | Disclosure                | Missing operational implications                   |
| `TrustChainGraph`   | Display delegation tree     | Citations                 | Missing verification, missing anchor links         |
| `GradientChart`     | Verification distribution   | (Informational)           | Missing trends, missing drill-down                 |
| `ConstraintGauge`   | Dimension utilization bar   | (Informational)           | Read-only, no editing, no threshold alerts         |
| `DimensionGauge`    | Dimension card with details | (Informational)           | Read-only, missing alert state                     |
| `AuditTable`        | Audit anchor list           | (Table)                   | Missing verification, missing detail view          |
| `AuditFilters`      | Filter controls             | (Filter)                  | Complete for current scope                         |
| `StatusBadge`       | Generic status display      | Disclosure                | Complete for current scope                         |
| `WorkspaceCard`     | Workspace state/phase       | (Informational)           | Missing agent activity summary                     |
| `BridgeConnections` | Bridge visualization        | (Informational)           | Missing data flow indicators                       |
| `Header`            | Page title and status       | (Layout)                  | Has WebSocket status; could host alert banner      |
| `Sidebar`           | Navigation                  | (Navigation)              | Missing badge counts for attention items           |
| `DashboardShell`    | Page layout wrapper         | (Layout)                  | Complete for current scope                         |
| (Missing)           | Real-time activity feed     | Stream of Thought         | Does not exist; WebSocket infrastructure ready     |
| (Missing)           | ShadowEnforcer view         | Variations                | Does not exist; concept from brief not implemented |
| (Missing)           | Chain verification          | Verification              | Does not exist; critical EATP gap                  |
| (Missing)           | Cost report                 | Cost Estimates            | Sidebar link exists; page does not                 |
| (Missing)           | Posture change control      | Tuners + Verification     | Read-only display exists; no write controls        |
| (Missing)           | Constraint editing          | Parameters + Verification | Read-only display exists; no write controls        |
| (Missing)           | Agent suspend/revoke        | Controls (stop)           | Status display exists; no write controls           |

---

## Conclusion

The CARE Platform dashboard has a well-structured foundation: correct navigation hierarchy, appropriate type system mirroring the Python models, responsive layout, consistent component patterns, and real-time infrastructure via WebSocket. The verification gradient, constraint envelopes, trust postures, and audit trail are all represented as display components.

The gaps cluster around three themes:

1. **From display to governance instrument**: Components show data but do not enable governance actions (posture changes, constraint edits, agent controls, chain verification). The dashboard reads like a report when it needs to function like a control panel.

2. **From snapshots to real-time awareness**: The WebSocket infrastructure exists but has no visible feed. Agents operate between page loads, invisible to the governance officer. The real-time activity feed is the single most impactful addition.

3. **From data to trust evidence**: The audit trail stores the right data but does not expose the cryptographic properties that distinguish EATP governance from standard logging. Without chain verification, the platform's core differentiator is invisible.

Addressing these three themes -- in the priority order specified above -- will transform the dashboard from an AI agent admin panel into the trust governance interface that the CARE philosophy requires.
