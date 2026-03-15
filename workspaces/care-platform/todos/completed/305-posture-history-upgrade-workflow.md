# 305: Persisted Posture History and Upgrade Workflow

**Milestone**: 3 — Persistence Layer
**Priority**: Medium
**Estimated effort**: Medium
**Depends on**: 301, 302, 105
**Completed**: 2026-03-12
**Verified by**: PostureHistoryStore + PostureChangeRecord + PostureEligibilityChecker + EligibilityResult in `care_platform/persistence/posture_history.py`; 23 unit tests pass in `tests/unit/persistence/test_posture_history.py`

## Description

Implement the persisted posture history log and the upgrade/downgrade workflow. Trust posture (Pseudo-Agent, Supervised, Shared Planning, Continuous Insight, Delegated) can only change through a governed process — not unilaterally. Every posture change is recorded in an append-only log. Upgrades require evidence from the ShadowEnforcer. Downgrades can be immediate (on incident) or scheduled (periodic review).

## Tasks

- [ ] Implement `PostureChangeRecord` model:
  - agent_id, from_posture, to_posture, changed_at, changed_by, evidence_ref, reason
  - direction: UPGRADE or DOWNGRADE
  - trigger: INCIDENT, REVIEW, SCHEDULED, CASCADE_REVOCATION
  - evidence_ref: pointer to ShadowEnforcer report or audit query result
- [ ] Implement `PostureHistoryStore`:
  - `PostureHistoryStore.record_change(agent_id, change)` — append only, never update or delete
  - `PostureHistoryStore.get_history(agent_id) -> list[PostureChangeRecord]`
  - `PostureHistoryStore.current_posture(agent_id) -> TrustPosture` — derived from latest record
  - `PostureHistoryStore.get_duration_at_posture(agent_id, posture) -> timedelta` — days at a given level
- [ ] Implement upgrade workflow:
  - `PostureUpgradeRequest`: submitted by human operator, references ShadowEnforcer evidence
  - Validation: evidence must meet configured thresholds (from posture-plan.yaml, see 604)
  - On approval: `PostureHistoryStore.record_change(...)` with direction=UPGRADE
  - Audit anchor created for the posture change
- [ ] Implement downgrade workflow:
  - Immediate downgrade (incident trigger): no evidence required, human decision
  - Scheduled downgrade (review): same evidence-based flow as upgrade but direction=DOWNGRADE
  - On any downgrade: audit anchor created; active sessions re-verified at new posture
- [ ] Implement posture eligibility check:
  - `PostureEligibilityChecker.check(agent_id, target_posture) -> EligibilityResult`
  - EligibilityResult: ELIGIBLE, NOT_YET (with days_remaining), BLOCKED (with reason)
  - Reads posture history for duration; reads ShadowEnforcer reports for pass rate
- [ ] Write integration tests:
  - Upgrade workflow: submit request, validate evidence, record change
  - Downgrade workflow: incident trigger, immediate downgrade recorded
  - Eligibility check: agent not yet eligible returns correct days_remaining
  - History is append-only: verify no records can be modified

## Acceptance Criteria

- Posture changes recorded in append-only log (no updates, no deletes)
- Upgrade workflow validates evidence before accepting change
- Downgrade on incident is immediate with no evidence requirement
- Eligibility check correctly evaluates duration and ShadowEnforcer thresholds
- Integration tests passing, including append-only enforcement

## Dependencies

- 301: DataFlow schema (posture history table)
- 302: Trust object persistence
- 105: Trust posture model (5 levels)
- 208: ShadowEnforcer (evidence source for upgrades)

## References

- Trust posture model: `care_platform/models/posture.py` (from 105)
- Posture evolution plan: defined per-team in posture-plan.yaml (see 604 for DM team)
