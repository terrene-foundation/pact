# User Flow: Governance Supervisor (Daily Operations)

## Persona

Head of AI Operations who monitors agents, approves actions, and ensures governance compliance. Uses the dashboard multiple times per day.

## Flow 1: Morning Review

1. Open dashboard → See overview with key metrics (active agents, pending approvals, verification stats, cost today)
2. Glance at **real-time activity feed** → See what agents have been doing overnight
3. Notice 3 pending approvals (badge on sidebar) → Click to approval queue
4. Review first held action → See agent name, action, reason, constraint utilization, agent track record, estimated cost
5. Approve with note → Action proceeds, audit anchor created
6. Reject second action → Agent notified, reason recorded
7. Escalate third action → Reassign to team lead for review

## Flow 2: Incident Response

1. Alert notification → Agent "content-writer-03" triggered BLOCKED on financial constraint
2. Click agent in activity feed → Jump to agent detail
3. See constraint envelope utilization → Financial at 98%, approaching limit
4. Click "Adjust Constraints" → Modify financial ceiling or suspend agent
5. Review audit trail for this agent → See last 24 hours of actions
6. Decision: Suspend agent → Click suspend, enter reason, cryptographic record created
7. Notify team lead → Bridge to team workspace

## Flow 3: Posture Upgrade Review

1. ShadowEnforcer report shows agent eligible for upgrade (SUPERVISED → SHARED_PLANNING)
2. Review shadow metrics → 95% pass rate over 90 days, 150+ operations, 0 blocks
3. Review recommendations → System suggests upgrade based on evidence
4. Approve posture upgrade → New trust level takes effect, audit anchor created
5. Updated constraint envelope auto-adjusts → Agent gets broader operational boundaries

## Flow 4: Compliance Check

1. Auditor requests proof of governance → Navigate to Audit Trail
2. Filter by date range and team → Server-side paginated results
3. Export audit trail as signed PDF → Cryptographic chain of custody preserved
4. Verify specific trust chain → Click to see genesis → delegation → attestation chain
5. Download verification proof → Ed25519 signatures, hash chain, timestamps
