# CARE Platform UI/UX Analysis

**Date**: 2026-03-15
**Author**: UI/UX Design Agent
**Status**: Complete
**Scope**: Full analysis of the CARE Platform web dashboard -- information architecture, persona mapping, user flows, visual hierarchy, gaps, and prioritized recommendations.

---

## Executive Summary

The CARE Platform web dashboard (`apps/web/`) is a bare Next.js 15 scaffold. It has a root `layout.tsx`, a `globals.css` with only Tailwind directives, and no pages, components, or routes. The backend API (`src/care_platform/api/`) is mature: 20+ endpoints covering teams, agents, approvals, trust chains, constraint envelopes, workspaces, bridges, verification stats, cost tracking, and real-time WebSocket events. The gap between backend capability and frontend existence is total.

This is not a critique -- it is an opportunity. Building the dashboard from scratch means every decision can be made correctly the first time, informed by the platform's domain model and its target personas.

**Top 5 priorities:**

1. **P0 -- Approval Queue page**: The primary human-in-the-loop interaction. Without it, HELD actions cannot be resolved by humans. This is the reason the dashboard exists.
2. **P0 -- Trust Overview dashboard**: The "at a glance" view showing trust health across all agents, teams, and bridges. The supervisor's landing page.
3. **P1 -- Agent Management page**: View agents, their posture levels, constraint envelopes, trust chain status, and attestation state.
4. **P1 -- Audit Trail page**: Queryable, filterable audit anchor history. The auditor's primary tool.
5. **P1 -- Navigation shell and layout**: The DashboardShell, Sidebar, and routing structure that everything else sits inside.

---

## 1. Current State Assessment

### What Exists

| File                          | Purpose         | Content                                         |
| ----------------------------- | --------------- | ----------------------------------------------- |
| `apps/web/app/layout.tsx`     | Root layout     | Bare HTML shell, metadata title "CARE Platform" |
| `apps/web/app/globals.css`    | Global styles   | Three Tailwind directives only                  |
| `apps/web/tailwind.config.js` | Tailwind config | Default, no custom theme                        |
| `apps/web/next.config.js`     | Next.js config  | `output: "standalone"`                          |
| `apps/web/package.json`       | Dependencies    | Next 15, React 19, Tailwind 3.4, Vitest         |

### What Does Not Exist

- No `page.tsx` (no landing page at all -- the app renders nothing)
- No route directories (`agents/`, `approvals/`, `audit/`, `bridges/`, `envelopes/`, `trust-chains/`, `verification/`, `workspaces/`)
- No `components/` directory (no Sidebar, no DashboardShell, no shared UI)
- No `lib/` directory (no API client, no types, no utilities)
- No design system tokens (colors, spacing, typography)
- No loading states, error boundaries, or empty states
- No WebSocket client for real-time events

### Backend API (Fully Implemented)

The FastAPI server exposes a comprehensive REST API with WebSocket support:

**Phase 1 endpoints (core operations):**

- `GET /api/v1/teams` -- List teams
- `GET /api/v1/teams/{team_id}/agents` -- List team agents
- `GET /api/v1/agents/{agent_id}/status` -- Agent status and posture
- `POST /api/v1/agents/{agent_id}/approve/{action_id}` -- Approve held action
- `POST /api/v1/agents/{agent_id}/reject/{action_id}` -- Reject held action
- `GET /api/v1/held-actions` -- Pending approvals
- `GET /api/v1/cost/report` -- Cost tracking

**Dashboard endpoints (M18):**

- `GET /api/v1/trust-chains` -- All trust chains
- `GET /api/v1/trust-chains/{agent_id}` -- Trust chain detail
- `GET /api/v1/envelopes/{envelope_id}` -- Constraint envelope detail
- `GET /api/v1/workspaces` -- All workspaces
- `GET /api/v1/bridges` -- All bridges
- `GET /api/v1/verification/stats` -- Verification gradient statistics

**Bridge management (M36):**

- `POST /api/v1/bridges` -- Create bridge
- `GET /api/v1/bridges/{bridge_id}` -- Bridge detail
- `PUT /api/v1/bridges/{bridge_id}/approve` -- Approve bridge
- `POST /api/v1/bridges/{bridge_id}/suspend` -- Suspend bridge
- `POST /api/v1/bridges/{bridge_id}/close` -- Close bridge
- `GET /api/v1/bridges/team/{team_id}` -- Bridges by team
- `GET /api/v1/bridges/{bridge_id}/audit` -- Bridge audit trail

**Real-time:**

- `WebSocket /ws` -- Event streaming (audit anchors, held actions, posture changes, bridge status, verification results, workspace transitions)

---

## 2. Persona Mapping

The CARE Platform serves the governance side of the trust model. Two primary personas are relevant:

### Persona A: Governance Supervisor (maps to Prof. D)

**Profile**: The Founder (or future board member/team lead) who supervises agent teams. Reviews held actions, monitors trust posture evolution, verifies that agents operate within their constraint envelopes.

**Primary tasks (daily):**

1. Review and resolve held actions (approve/reject) -- the approval queue
2. Monitor trust health across agents -- are any flagged, nearing constraint boundaries?
3. Track posture evolution -- which agents are ready for upgrade? Any incidents triggering downgrade?
4. Review cost reports -- are API spend budgets on track?

**What they need to see immediately upon login:**

- Number of pending approvals (with urgency levels)
- Trust health summary (all green? any agents flagged/blocked?)
- Recent posture changes (upgrades and downgrades)
- Cost burn rate against budget

**Key characteristic**: This person manages the platform daily. Efficiency matters more than aesthetics. They need to approve 5-20 held actions per day and should be able to do so without navigating to individual agent pages.

### Persona B: External Auditor

**Profile**: An ethics board member, regulator, or compliance officer reviewing the organization's AI governance posture. No ongoing relationship with the platform -- arrives periodically, needs to verify trust integrity.

**Primary tasks (periodic):**

1. Verify trust chain integrity -- are all chains valid? Any gaps?
2. Review audit trail -- chronological record of all agent actions
3. Inspect constraint envelopes -- what boundaries exist? Are they enforced?
4. Examine bridge audit trails -- how do teams share data?

**What they need:**

- Read-only views with export capability
- Chronological timeline of all governance events
- Trust chain verification status (integrity check results)
- Filterable audit trail (by agent, team, date range, verification level)
- Constraint envelope inspection (all five CARE dimensions visible)

**Key characteristic**: This person visits infrequently and must quickly orient themselves. Information density should be high but progressive -- overview first, detail on demand.

### Persona C: Platform Administrator (implicit)

**Profile**: The person who configures the platform -- defining teams, agents, constraint envelopes, and workspace structures. In the current solo-founder context, this is the same person as Persona A.

**Primary tasks:**

1. Create and configure teams and agents (via YAML currently, future UI)
2. Set up constraint envelopes for new agents
3. Manage bridge creation and approval
4. Monitor system health (API connectivity, WebSocket status)

---

## 3. Information Architecture

### Proposed Navigation Structure

Based on the API surface, domain model, and persona needs, the navigation should be organized around the user's mental model of "governing an organization with AI agents":

```
+--------------------------------------------------+
|  CARE Platform                                    |
+--------------------------------------------------+
|                                                   |
|  SIDEBAR (persistent)                             |
|                                                   |
|  [Overview]       <-- Landing/dashboard           |
|                                                   |
|  GOVERNANCE                                       |
|  [Approvals]      <-- Held actions queue (P0)     |
|  [Agents]         <-- Agent list + status         |
|  [Teams]          <-- Team overview               |
|                                                   |
|  TRUST                                            |
|  [Trust Chains]   <-- Chain integrity view        |
|  [Envelopes]      <-- Constraint envelopes        |
|  [Verification]   <-- Gradient stats              |
|                                                   |
|  COLLABORATION                                    |
|  [Bridges]        <-- Cross-functional bridges    |
|  [Workspaces]     <-- Workspace-as-knowledge-base |
|                                                   |
|  OPERATIONS                                       |
|  [Audit Trail]    <-- Audit anchor history        |
|  [Cost Tracking]  <-- API spend and budgets       |
|                                                   |
+--------------------------------------------------+
```

**Rationale for grouping:**

- **Governance** groups the daily workflow: approvals (the primary action), agents (the things being governed), teams (the organizational structure).
- **Trust** groups the cryptographic trust infrastructure: chains (integrity), envelopes (boundaries), verification (classification).
- **Collaboration** groups inter-team mechanisms: bridges and workspaces.
- **Operations** groups monitoring and compliance: audit trail and cost tracking.

### Page Hierarchy

```
/                           --> Overview dashboard
/approvals                  --> Approval queue (list + batch actions)
/approvals/{action_id}      --> Single approval detail (rarely needed)
/agents                     --> Agent list (all agents, grouped by team)
/agents/{agent_id}          --> Agent detail (posture, envelope, chain, history)
/teams                      --> Team list with health summary
/teams/{team_id}            --> Team detail (members, bridges, audit)
/trust-chains               --> Trust chain list with integrity status
/trust-chains/{agent_id}    --> Trust chain detail (genesis -> delegations -> agent)
/envelopes                  --> Constraint envelope list
/envelopes/{envelope_id}    --> Envelope detail (5 CARE dimensions)
/verification               --> Verification gradient statistics
/bridges                    --> Bridge list with lifecycle status
/bridges/{bridge_id}        --> Bridge detail (permissions, approval state, audit)
/workspaces                 --> Workspace list with state and phase
/workspaces/{workspace_id}  --> Workspace detail (agents, bridges, knowledge)
/audit                      --> Audit trail (filterable, paginated)
/cost                       --> Cost tracking dashboard
```

---

## 4. Page-by-Page Design Specifications

### 4.1 Overview Dashboard (/)

**Purpose**: The Governance Supervisor's daily starting point. Show trust health at a glance and surface anything requiring attention.

**Layout (top-down):**

```
+-------------------------------------------------------------+
| HEADER BAR                                                   |
| CARE Platform            [Status: Connected] [User]          |
+-------------------------------------------------------------+
|                                                               |
|  ATTENTION BANNER (conditional)                               |
|  [!] 3 actions awaiting approval (1 IMMEDIATE)    [Review]   |
|                                                               |
|  +-------------------+  +-------------------+                 |
|  | Pending Approvals |  | Trust Health      |                 |
|  | 3 held            |  | 12 agents         |                 |
|  | 1 immediate       |  | 11 healthy        |                 |
|  | 2 standard        |  | 1 flagged         |                 |
|  | 0 expired         |  | 0 blocked         |                 |
|  +-------------------+  +-------------------+                 |
|                                                               |
|  +-------------------+  +-------------------+                 |
|  | Posture Summary   |  | Cost (30 days)    |                 |
|  | 2 SUPERVISED      |  | $147.23 / $500    |                 |
|  | 5 SHARED_PLANNING |  | DM Team: $98.40   |                 |
|  | 4 CONT_INSIGHT    |  | Platform: $48.83  |                 |
|  | 1 DELEGATED       |  | 29% of budget     |                 |
|  +-------------------+  +-------------------+                 |
|                                                               |
|  RECENT ACTIVITY (real-time via WebSocket)                    |
|  +-----------------------------------------------------+     |
|  | 14:23  dm-content-creator  HELD  publish_post        |     |
|  | 14:15  dm-analytics        AUTO  collect_metrics     |     |
|  | 14:02  dm-scheduler        AUTO  schedule_post       |     |
|  | 13:45  dm-outreach         HELD  send_email          |     |
|  | 13:30  platform-agent      FLAGGED deploy_config     |     |
|  +-----------------------------------------------------+     |
|                                                               |
|  VERIFICATION DISTRIBUTION (bar chart)                        |
|  AUTO_APPROVED  ████████████████████████  78%                 |
|  FLAGGED        ████                      12%                 |
|  HELD           ██                         7%                 |
|  BLOCKED        █                          3%                 |
|                                                               |
+-------------------------------------------------------------+
```

**Key design decisions:**

- **Attention banner**: Only appears when there are pending approvals. Uses urgency color: red for IMMEDIATE, amber for STANDARD. Links directly to the approval queue. This is the single most important UI element on the page.
- **Metric cards**: 4 cards in a 2x2 grid. Each shows the single most important number large, with supporting details below. Color-coded: green = healthy, amber = needs attention, red = action required.
- **Recent Activity**: Real-time feed from the WebSocket. Shows the last 10-20 events. Each event shows time, agent, verification level (color-coded badge), and action name. Clicking an event navigates to the relevant detail page.
- **Verification Distribution**: Simple horizontal bar chart showing the gradient breakdown. Provides an instant read on how much autonomy agents are exercising vs. how much human oversight is occurring.

### 4.2 Approval Queue (/approvals)

**Purpose**: The primary human-in-the-loop interaction. This is the most critical page in the entire dashboard.

**Layout:**

```
+-------------------------------------------------------------+
| Approvals                          [Approve Selected] [...]  |
+-------------------------------------------------------------+
|                                                               |
| Filters: [All urgencies v] [All teams v] [All agents v]     |
|                                                               |
| IMMEDIATE (1)                                                 |
| +-----------------------------------------------------------+|
| | [x] dm-outreach  send_email                                ||
| |     Reason: External communication exceeds posture level   ||
| |     Submitted: 2 hours ago    Expires in: 4 hours          ||
| |     [View Details]  [Approve]  [Reject]                    ||
| +-----------------------------------------------------------+|
|                                                               |
| STANDARD (2)                                                  |
| +-----------------------------------------------------------+|
| | [ ] dm-content-creator  publish_post                       ||
| |     Reason: Publication action held for human review       ||
| |     Submitted: 45 minutes ago    Expires in: 23 hours      ||
| |     [View Details]  [Approve]  [Reject]                    ||
| +-----------------------------------------------------------+|
| | [ ] dm-content-creator  publish_post                       ||
| |     Reason: Publication action held for human review       ||
| |     Submitted: 30 minutes ago    Expires in: 23.5 hours    ||
| |     [View Details]  [Approve]  [Reject]                    ||
| +-----------------------------------------------------------+|
|                                                               |
| BATCH (0)                                                     |
| (No batch items pending)                                      |
|                                                               |
+-------------------------------------------------------------+
```

**Key design decisions:**

- **Grouped by urgency**: IMMEDIATE items at top, visually distinct (red accent border). STANDARD in the middle. BATCH at bottom.
- **Checkboxes for batch operations**: Select multiple items and approve/reject in one action. Critical for the daily workflow when 5-20 items accumulate.
- **Inline actions**: Approve and Reject buttons directly on each item. No need to navigate to a detail page for the common case. The supervisor should resolve most items in 1 click.
- **Time pressure visible**: Both "submitted" and "expires in" shown. Expiring-soon items should show amber/red time indicators.
- **Reason always visible**: The "why was this held" text is never hidden behind a click. It is the information the supervisor needs to make a decision.
- **Rejection requires reason**: Clicking Reject should open an inline text field for the rejection reason. Approval is one-click (with optional reason).
- **Empty state**: When the queue is empty, show a clear "All caught up" message with trust health summary. This is the positive reinforcement state.

### 4.3 Agent Management (/agents)

**Purpose**: View all agents, their posture levels, health, and constraint status.

**Layout:**

```
+-------------------------------------------------------------+
| Agents                                         [Filter v]    |
+-------------------------------------------------------------+
|                                                               |
| DM TEAM                                                       |
| +-----------------------------------------------------------+|
| | Agent             Posture           Status     Actions     ||
| |-----------------------------------------------------------|
| | dm-team-lead      SHARED_PLANNING   Healthy    [View]     ||
| | dm-content        SUPERVISED        Healthy    [View]     ||
| | dm-analytics      SHARED_PLANNING   Healthy    [View]     ||
| | dm-scheduler      CONT_INSIGHT      Healthy    [View]     ||
| | dm-outreach       SUPERVISED        1 Held     [View]     ||
| | dm-podcast        SUPERVISED        Healthy    [View]     ||
| +-----------------------------------------------------------+|
|                                                               |
| PLATFORM TEAM                                                 |
| +-----------------------------------------------------------+|
| | Agent             Posture           Status     Actions     ||
| |-----------------------------------------------------------|
| | platform-lead     CONT_INSIGHT      Healthy    [View]     ||
| | platform-impl     SHARED_PLANNING   Flagged    [View]     ||
| +-----------------------------------------------------------+|
|                                                               |
+-------------------------------------------------------------+
```

**Agent detail page (/agents/{agent_id}):**

```
+-------------------------------------------------------------+
| < Back to Agents                                              |
| dm-content-creator                      [Revoke Access]       |
+-------------------------------------------------------------+
|                                                               |
| POSTURE                                                       |
| +----------------------------+                                |
| | SUPERVISED (Level 2 of 5)  |                                |
| | Since: 2026-01-15          |                                |
| | Next upgrade eligible:     |                                |
| |   45 days (need 90 days    |                                |
| |   at 95%+ success rate)    |                                |
| | Success rate: 97.3%        |                                |
| | Total operations: 1,247    |                                |
| | Incidents: 0               |                                |
| +----------------------------+                                |
|                                                               |
| CONSTRAINT ENVELOPE                                           |
| +-----------------------------------------------------------+|
| | Financial       $0/day, $0/month (no financial authority)  ||
| | Operational     create_draft, edit_draft, format_content   ||
| | Temporal        Mon-Fri, 06:00-22:00 SGT                  ||
| | Data Access     workspaces/media/content/** (read/write)   ||
| |                 workspaces/media/analytics/** (read only)   ||
| | Communication   Internal only (no external publication)    ||
| +-----------------------------------------------------------+|
|                                                               |
| TRUST CHAIN                                                   |
| +-----------------------------------------------------------+|
| | Genesis: Terrene Foundation (2026-01-01)                   ||
| |   -> Delegation: DM Team Lead (2026-01-15)                ||
| |     -> Delegation: dm-content-creator (2026-01-15)         ||
| | Chain status: VALID (verified 14:00 today)                 ||
| +-----------------------------------------------------------+|
|                                                               |
| RECENT ACTIONS (last 50)                                      |
| +-----------------------------------------------------------+|
| | Time    Action           Level          Result             ||
| | 14:15   create_draft     AUTO_APPROVED  SUCCESS            ||
| | 13:45   edit_draft       AUTO_APPROVED  SUCCESS            ||
| | 13:00   publish_post     HELD           PENDING            ||
| +-----------------------------------------------------------+|
|                                                               |
+-------------------------------------------------------------+
```

**Key design decisions:**

- **Grouped by team**: Agents are always shown in team context. The mental model is "team -> agent," not flat list.
- **Posture as visual indicator**: The posture level should use color and a progress-bar-like indicator showing where the agent is on the PSEUDO_AGENT to DELEGATED spectrum.
- **Constraint envelope shows all 5 CARE dimensions**: Financial, Operational, Temporal, Data Access, Communication. Each dimension on its own row with the constraint values visible without clicking.
- **Trust chain as visual tree**: Indented tree showing genesis -> delegations -> agent. Valid chains show a green checkmark; broken chains show a red alert.
- **Upgrade eligibility is surfaced**: Do not make the supervisor go looking for whether an agent is ready for posture upgrade. Show it prominently on the detail page.

### 4.4 Audit Trail (/audit)

**Purpose**: Chronological record of all audited actions. The auditor's primary tool.

**Layout:**

```
+-------------------------------------------------------------+
| Audit Trail                                    [Export CSV]   |
+-------------------------------------------------------------+
|                                                               |
| Filters:                                                      |
| [Date range: Last 7 days v] [Team: All v] [Agent: All v]    |
| [Level: All v] [Search action name...]                        |
|                                                               |
| +-----------------------------------------------------------+|
| | Time         Agent              Action        Level  Sig  ||
| |-----------------------------------------------------------|
| | 14:23:01     dm-content         publish_post  HELD   Yes  ||
| | 14:15:32     dm-analytics       collect_data  AUTO   Yes  ||
| | 14:02:17     dm-scheduler       schedule      AUTO   Yes  ||
| | 13:45:44     dm-outreach        send_email    HELD   Yes  ||
| | 13:30:12     platform-impl      deploy_cfg    FLAG   Yes  ||
| | 13:15:00     dm-content         edit_draft    AUTO   Yes  ||
| | ...                                                        ||
| +-----------------------------------------------------------+|
|                                                               |
| Showing 1-50 of 12,847     [<] [1] [2] [3] ... [257] [>]    |
|                                                               |
+-------------------------------------------------------------+
```

**Key design decisions:**

- **Table format**: Audit data is inherently tabular. Use a proper data table with sortable columns, not cards.
- **Filterable and searchable**: Date range, team, agent, verification level. Full-text search on action names.
- **Signature status column**: Shows whether the audit anchor is signed and verifiable. The auditor needs to see this at a glance.
- **Pagination**: Audit trails can have thousands of entries. Server-side pagination with page controls.
- **Export**: CSV export button for offline analysis. The auditor may need to bring data into their own tools.
- **Expandable rows**: Clicking a row expands to show full anchor details (envelope_id, metadata, content_hash, previous_hash).

### 4.5 Trust Chains (/trust-chains)

**Purpose**: Visualize the cryptographic trust lineage from genesis to each agent.

**Layout:**

```
+-------------------------------------------------------------+
| Trust Chains                                   [Verify All]  |
+-------------------------------------------------------------+
|                                                               |
| CHAIN INTEGRITY SUMMARY                                       |
| +-----------------------------------------------------------+|
| | Total chains: 12  |  Valid: 12  |  Broken: 0  |  Expired: 0|
| +-----------------------------------------------------------+|
|                                                               |
| GENESIS: Terrene Foundation                                   |
| Created: 2026-01-01  |  Status: ACTIVE  |  [Inspect]         |
|                                                               |
|   +-- DM Team Lead  (SHARED_PLANNING)  VALID                 |
|   |     +-- dm-content-creator  (SUPERVISED)  VALID           |
|   |     +-- dm-analytics  (SHARED_PLANNING)  VALID            |
|   |     +-- dm-scheduler  (CONT_INSIGHT)  VALID               |
|   |     +-- dm-outreach  (SUPERVISED)  VALID                  |
|   |     +-- dm-podcast  (SUPERVISED)  VALID                   |
|   |                                                           |
|   +-- Platform Lead  (CONT_INSIGHT)  VALID                    |
|         +-- platform-impl  (SHARED_PLANNING)  VALID           |
|                                                               |
+-------------------------------------------------------------+
```

**Key design decisions:**

- **Tree visualization**: Trust chains are inherently hierarchical. Show them as an indented tree, not a flat list.
- **Integrity summary at top**: The auditor's first question is "are all chains valid?" Answer that immediately with a summary bar.
- **Color-coded validity**: Green = valid, red = broken, amber = expired/expiring soon.
- **Verify All button**: Triggers chain integrity verification across all chains. Shows results inline.
- **Clicking any node**: Opens a detail panel showing the full delegation record, constraint envelope, and signature data.

### 4.6 Bridges (/bridges)

**Purpose**: Manage Cross-Functional Bridges between agent teams.

The bridge lifecycle (PENDING -> NEGOTIATING -> ACTIVE -> SUSPENDED/CLOSED/EXPIRED/REVOKED) maps to a Kanban-like view:

```
+-------------------------------------------------------------+
| Bridges                                    [Create Bridge]    |
+-------------------------------------------------------------+
|                                                               |
| PENDING (2)         ACTIVE (3)          SUSPENDED (0)         |
| +-----------+       +-----------+       +-----------+         |
| | DM <> Gov |       | DM <> Std |       | (none)    |         |
| | Scoped    |       | Standing  |       |           |         |
| | [Approve] |       | Since 1/1 |       |           |         |
| +-----------+       +-----------+       +-----------+         |
| | Plt <> DM |       | DM <> Cmm |       |                    |
| | Ad-Hoc    |       | Standing  |       |                    |
| | [Approve] |       | Since 2/1 |       |                    |
| +-----------+       +-----------+       |                    |
|                     | Gov <> Std |       |                    |
|                     | Standing   |       |                    |
|                     | Since 1/1  |       |                    |
|                     +-----------+       |                    |
|                                                               |
+-------------------------------------------------------------+
```

### 4.7 Remaining Pages (Brief Specs)

**Verification Stats (/verification):**

- Distribution chart (bar or donut) of AUTO_APPROVED / FLAGGED / HELD / BLOCKED
- Trend over time (line chart: 7/30/90 day view)
- Per-agent breakdown table
- Proximity alerts (actions near constraint boundaries)

**Workspaces (/workspaces):**

- Card grid showing each workspace with state (PROVISIONING / ACTIVE / ARCHIVED) and CO phase (ANALYZE / PLAN / IMPLEMENT / VALIDATE)
- Click through to workspace detail with agent team, bridges, and knowledge base structure

**Envelopes (/envelopes):**

- Table of all constraint envelopes with the 5 CARE dimension summaries
- Click through to full envelope detail with all dimension values, expiry, and signing info
- Visual comparison tool for parent vs. child envelopes (monotonic tightening verification)

**Cost Tracking (/cost):**

- Total spend vs. budget (progress bar)
- Per-team breakdown (table or stacked bar)
- Per-agent breakdown within teams
- 30-day trend line
- Budget alert thresholds

---

## 5. Design System Requirements

### Typography

Use the system font stack, not a web font. This avoids AI-slop tell (Inter/Roboto default):

```css
font-family:
  -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial,
  sans-serif;
```

Type scale (modular, 1.25 ratio):

- Display: 30px / 600 weight -- page titles
- Heading: 24px / 600 weight -- section headings
- Title: 20px / 500 weight -- card titles
- Body: 16px / 400 weight -- primary text
- Label: 14px / 500 weight -- labels, metadata
- Caption: 12px / 400 weight -- timestamps, secondary info

### Color Palette

Enterprise-appropriate, not trendy. CARE Platform is a governance tool -- it should feel authoritative and trustworthy, not playful.

**Primary**: Slate/neutral grays for structure

- Background: `#FFFFFF` (content), `#F8FAFC` (page background), `#F1F5F9` (sidebar)
- Text: `#0F172A` (primary), `#475569` (secondary), `#94A3B8` (tertiary)
- Border: `#E2E8F0`

**Semantic colors** (verification gradient aligned):

- AUTO_APPROVED: `#059669` (green-600) -- healthy, approved
- FLAGGED: `#D97706` (amber-600) -- attention needed
- HELD: `#DC2626` (red-600) -- action required
- BLOCKED: `#7C3AED` (violet-600) -- hard stop

**Trust posture colors** (spectrum from constrained to autonomous):

- PSEUDO_AGENT: `#94A3B8` (slate-400) -- minimal
- SUPERVISED: `#3B82F6` (blue-500) -- guided
- SHARED_PLANNING: `#8B5CF6` (violet-500) -- collaborative
- CONTINUOUS_INSIGHT: `#059669` (green-600) -- trusted
- DELEGATED: `#0D9488` (teal-600) -- autonomous

### Spacing Scale

4px base: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80

### Component Library Consideration

The current `package.json` has no component library. Two options:

1. **shadcn/ui + Radix primitives**: Unstyled, composable, accessible. Best fit for a custom enterprise design. Copy-paste components, full control.
2. **Tailwind only**: No library. Build everything from Tailwind classes. Maximum control, maximum effort.

**Recommendation**: shadcn/ui. It provides accessible primitives (dialog, dropdown, tooltip, data table) without imposing a visual style. The governance domain requires complex components (data tables with sorting/pagination, multi-select, confirmation dialogs) that are expensive to build from scratch.

---

## 6. User Flow Analysis

### Flow 1: Supervisor resolves a held action (most common daily task)

**Current state**: Impossible. No UI exists.

**Target flow** (2 clicks):

1. Supervisor opens dashboard. Attention banner shows "3 actions awaiting approval."
2. Clicks "Review" on the banner (or clicks "Approvals" in sidebar). Arrives at approval queue.
3. Reads the reason for the first item. Clicks "Approve." Done.
4. For batch: selects multiple checkboxes, clicks "Approve Selected." Done.

**Critical requirement**: The entire approve/reject flow must work without leaving the Approvals page. No navigation to agent detail pages required for the common case.

### Flow 2: Auditor verifies trust chain integrity (periodic task)

**Target flow** (3 clicks):

1. Auditor opens dashboard. Sees trust health summary card showing "12 chains, all valid."
2. Clicks "Trust Chains" in sidebar. Sees the tree view with all chains.
3. Clicks "Verify All." System re-verifies all chains. Results update inline.
4. Optionally clicks any node to inspect delegation details.

### Flow 3: Supervisor checks if an agent is ready for posture upgrade

**Target flow** (2 clicks):

1. Supervisor clicks "Agents" in sidebar.
2. Finds the agent. The posture column shows the current level and a visual indicator of upgrade progress (e.g., "87% to next level").
3. Clicks "View" to see full detail: days at current posture, success rate, operations count, incidents.

### Flow 4: Auditor reviews all actions by a specific agent in the last 30 days

**Target flow** (3 clicks):

1. Clicks "Audit Trail" in sidebar.
2. Selects the agent from the dropdown filter. Date range defaults to 30 days.
3. Reviews the filtered table. Exports to CSV if needed.

---

## 7. AI Slop Detection (Preemptive)

Since the dashboard will be built largely by AI agents, these guardrails prevent common AI-generated design patterns:

**AVOID:**

- Purple-to-blue gradients on headers or cards
- Glassmorphism (frosted glass effects)
- `rounded-2xl` on every element (use `rounded-md` or `rounded-lg` selectively)
- `shadow-lg` on every card (use `shadow-sm` for cards, `shadow-md` for elevated elements only)
- Identical card layouts for everything (use tables for tabular data, trees for hierarchies)
- `transition-all 300ms` on everything (animate only what gives feedback)
- Gratuitous gradient text
- Bounce/elastic easing

**PREFER:**

- Flat surfaces with subtle 1px borders (`border-slate-200`)
- Sharp, functional typography (no decorative fonts)
- Dense, information-rich layouts (this is a governance tool, not a landing page)
- Consistent but minimal shadow usage
- Motion only on interactive elements (hover, focus, state changes)
- System font stack

---

## 8. Gap Analysis

### Critical Gaps (blocks core functionality)

| Gap                    | Impact                      | Effort | API Ready?         |
| ---------------------- | --------------------------- | ------ | ------------------ |
| No pages exist at all  | Dashboard is non-functional | Large  | Yes                |
| No API client library  | Cannot fetch data           | Small  | N/A                |
| No WebSocket client    | No real-time updates        | Small  | Yes                |
| No authentication UI   | Cannot authenticate to API  | Small  | Yes (bearer token) |
| No approval queue page | Human-in-the-loop is broken | Medium | Yes                |
| No dashboard overview  | No trust health visibility  | Medium | Yes                |

### Important Gaps (reduces daily productivity)

| Gap                           | Impact                           | Effort | API Ready? |
| ----------------------------- | -------------------------------- | ------ | ---------- |
| No agent management page      | Cannot inspect agent state       | Medium | Yes        |
| No audit trail page           | Cannot review governance history | Medium | Yes        |
| No trust chain visualization  | Cannot verify chain integrity    | Medium | Yes        |
| No bridge management page     | Cannot manage inter-team bridges | Medium | Yes        |
| No loading/error/empty states | Poor UX on data fetch            | Small  | N/A        |
| No responsive design          | Mobile/tablet unusable           | Medium | N/A        |

### Nice-to-Have Gaps (polish and efficiency)

| Gap                         | Impact                         | Effort | API Ready? |
| --------------------------- | ------------------------------ | ------ | ---------- |
| No design system tokens     | Inconsistent styling           | Small  | N/A        |
| No keyboard shortcuts       | Power users slower             | Small  | N/A        |
| No dark mode                | Preference accessibility       | Medium | N/A        |
| No notification preferences | Cannot customize alerts        | Medium | No         |
| No bulk posture management  | Must upgrade agents one by one | Medium | No         |

---

## 9. Prioritized Recommendations

### Phase 1: Foundation (must build first)

**1.1 -- DashboardShell + Sidebar + Routing** (P0, 4-6 hours)

- Create the navigation shell with persistent sidebar
- Implement the route structure (all pages as stubs initially)
- Set up the Tailwind design tokens (colors, spacing, typography)
- Add shadcn/ui for primitive components

**1.2 -- API Client Library** (P0, 2-3 hours)

- Create `lib/api.ts` with typed fetch wrappers for all endpoints
- Create `lib/types.ts` with TypeScript interfaces matching API response shapes
- Handle authentication (bearer token from environment or local storage)
- Error handling and retry logic

**1.3 -- WebSocket Client** (P0, 2-3 hours)

- Create `lib/websocket.ts` for the `/ws` connection
- Auto-reconnect with exponential backoff
- Event type routing to UI state
- Authentication via Sec-WebSocket-Protocol header

### Phase 2: Core Governance (the reason the dashboard exists)

**2.1 -- Approval Queue** (P0, 6-8 hours)

- List view grouped by urgency (IMMEDIATE / STANDARD / BATCH)
- Inline approve/reject with one click
- Batch selection and batch approve/reject
- Rejection reason text field
- Real-time updates via WebSocket (new held actions appear automatically)
- Empty state: "All caught up" with trust health summary
- Filters by team, agent, urgency

**2.2 -- Overview Dashboard** (P0, 6-8 hours)

- Attention banner for pending approvals
- 4 metric cards (pending approvals, trust health, posture summary, cost)
- Recent activity feed (WebSocket-powered)
- Verification distribution chart
- Links to relevant detail pages

### Phase 3: Trust Visibility

**3.1 -- Agent List + Detail** (P1, 8-10 hours)

- List page grouped by team with posture indicators
- Detail page with posture evolution, constraint envelope (5 dimensions), trust chain, recent actions
- Posture upgrade eligibility indicator

**3.2 -- Audit Trail** (P1, 6-8 hours)

- Filterable, sortable data table
- Server-side pagination
- Date range, team, agent, verification level filters
- Full-text search
- CSV export
- Expandable row detail

**3.3 -- Trust Chain Visualization** (P1, 4-6 hours)

- Tree view of genesis -> delegations -> agents
- Integrity summary bar
- Verify All button with inline results
- Click-through to delegation/envelope detail

### Phase 4: Collaboration and Operations

**4.1 -- Bridge Management** (P2, 6-8 hours)

- List view with lifecycle status (Kanban-style or table)
- Bridge detail with permissions, approval state, audit trail
- Create bridge form
- Approve/suspend/close actions

**4.2 -- Workspace Overview** (P2, 4-6 hours)

- Card grid with workspace state and CO phase
- Workspace detail with agent team and bridges

**4.3 -- Constraint Envelope Inspector** (P2, 4-6 hours)

- Table of all envelopes with 5-dimension summaries
- Full detail view per envelope
- Parent/child comparison for monotonic tightening

**4.4 -- Cost Tracking** (P2, 4-6 hours)

- Spend vs. budget visualization
- Per-team and per-agent breakdown
- Trend line

**4.5 -- Verification Stats** (P2, 3-4 hours)

- Distribution chart
- Trend over time
- Per-agent breakdown

### Phase 5: Polish

**5.1 -- Loading, Error, and Empty States** (P2, 3-4 hours)

- Skeleton loading for all pages
- Error boundaries with retry
- Empty states with contextual guidance

**5.2 -- Keyboard Shortcuts** (P3, 2-3 hours)

- `a` for approve, `r` for reject on approval queue
- `/` for search
- `g + a` for go to agents, `g + p` for approvals, etc.

**5.3 -- Responsive Design** (P3, 4-6 hours)

- Collapsible sidebar on mobile
- Stacked metric cards
- Responsive tables (horizontal scroll or card view)

---

## 10. Technical Architecture Recommendations

### State Management

Use React Server Components (Next.js 15 app router) for initial data loading and client components only where interactivity is needed (approval buttons, filters, WebSocket-powered feeds).

Do not add a global state library (Redux, Zustand) unless state complexity demands it later. For now, React Server Components + `fetch` + URL search params for filters is sufficient.

### Data Fetching Pattern

```
// Server Component (default)
async function AgentsPage() {
  const agents = await fetchAgents();  // Server-side fetch
  return <AgentTable agents={agents} />;
}

// Client Component (for interactive elements)
"use client";
function ApprovalQueue() {
  // Uses SWR or React Query for real-time refetching
  const { data, mutate } = useSWR('/api/v1/held-actions');
  // WebSocket updates trigger mutate()
}
```

### File Structure

```
apps/web/
  app/
    layout.tsx           -- Root layout with DashboardShell
    page.tsx             -- Overview dashboard
    approvals/
      page.tsx           -- Approval queue
    agents/
      page.tsx           -- Agent list
      [agentId]/
        page.tsx         -- Agent detail
    teams/
      page.tsx           -- Team list
      [teamId]/
        page.tsx         -- Team detail
    trust-chains/
      page.tsx           -- Trust chain list
      [agentId]/
        page.tsx         -- Trust chain detail
    envelopes/
      page.tsx           -- Envelope list
      [envelopeId]/
        page.tsx         -- Envelope detail
    bridges/
      page.tsx           -- Bridge list
      [bridgeId]/
        page.tsx         -- Bridge detail
    workspaces/
      page.tsx           -- Workspace list
      [workspaceId]/
        page.tsx         -- Workspace detail
    audit/
      page.tsx           -- Audit trail
    verification/
      page.tsx           -- Verification stats
    cost/
      page.tsx           -- Cost tracking
  components/
    layout/
      DashboardShell.tsx -- Main layout with sidebar
      Sidebar.tsx        -- Persistent navigation
      Header.tsx         -- Top bar with status and user
    dashboard/
      AttentionBanner.tsx
      MetricCard.tsx
      ActivityFeed.tsx
      VerificationChart.tsx
    approvals/
      ApprovalList.tsx
      ApprovalItem.tsx
      BatchActions.tsx
    agents/
      AgentTable.tsx
      PostureIndicator.tsx
      EnvelopeView.tsx
      TrustChainTree.tsx
    audit/
      AuditTable.tsx
      AuditFilters.tsx
      AuditExport.tsx
    bridges/
      BridgeList.tsx
      BridgeDetail.tsx
      BridgeForm.tsx
    shared/
      StatusBadge.tsx    -- Verification level badges
      PostureBadge.tsx   -- Trust posture badges
      EmptyState.tsx
      LoadingSkeleton.tsx
      ErrorBoundary.tsx
      DataTable.tsx      -- Reusable sortable/filterable table
      Pagination.tsx
  lib/
    api.ts               -- API client with typed methods
    types.ts             -- TypeScript interfaces
    websocket.ts         -- WebSocket client with reconnect
    utils.ts             -- Date formatting, color helpers
    constants.ts         -- Verification levels, posture levels, colors
  public/
    (static assets)
```

---

## 11. Effort Summary

| Phase     | Description                                                                     | Effort Estimate | Priority |
| --------- | ------------------------------------------------------------------------------- | --------------- | -------- |
| Phase 1   | Foundation (shell, API, WebSocket)                                              | 8-12 hours      | P0       |
| Phase 2   | Core Governance (approvals, overview)                                           | 12-16 hours     | P0       |
| Phase 3   | Trust Visibility (agents, audit, chains)                                        | 18-24 hours     | P1       |
| Phase 4   | Collaboration + Operations (bridges, workspaces, cost, envelopes, verification) | 20-28 hours     | P2       |
| Phase 5   | Polish (states, shortcuts, responsive)                                          | 9-13 hours      | P2-P3    |
| **Total** |                                                                                 | **67-93 hours** |          |

The first two phases (P0) deliver a functional governance dashboard in approximately 20-28 hours of implementation effort. This covers the approval queue (the reason the dashboard exists) and the overview (the supervisor's daily starting point).

---

## 12. Success Criteria

The dashboard is successful when:

1. A Governance Supervisor can review and resolve all pending approvals without leaving the Approvals page (1-2 clicks per item).
2. The Overview page answers "is everything healthy?" within 5 seconds of loading.
3. An External Auditor can verify all trust chains with a single "Verify All" click.
4. The Audit Trail page can filter 10,000+ records to a specific agent's actions in the last 7 days within 3 clicks.
5. Real-time events (new held actions, posture changes) appear in the UI within 2 seconds of occurrence.
6. All verification gradient levels and trust posture levels use consistent, semantically meaningful colors across every page.
7. The design passes the AI Slop Detection check (fewer than 3 fingerprints).
