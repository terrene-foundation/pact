# Todo 2703: ShadowEnforcer Live Mode

**Milestone**: M27 — Agent Execution Runtime
**Priority**: Medium
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2701

## What

Enable ShadowEnforcer in live observation mode so it runs alongside the real enforcement pipeline on every action. In this mode ShadowEnforcer must not block, delay, or alter execution — it is a pure observer. For each action it records: what the real enforcer decided, what ShadowEnforcer would have decided if it were in charge, and whether the two decisions agree. Collect these observations as metrics (agreement rate, divergence count by posture) to provide evidence for future posture upgrade decisions. The live mode is toggled via a configuration flag (`CARE_SHADOW_ENFORCER_LIVE=true` in `.env`).

## Where

- `src/care_platform/trust/shadow_enforcer.py`
- `src/care_platform/execution/runtime.py`

## Evidence

- [ ] When `CARE_SHADOW_ENFORCER_LIVE=true`, ShadowEnforcer runs on every action alongside the real enforcer
- [ ] ShadowEnforcer observations are logged (real decision, shadow decision, agreement flag) for each action
- [ ] ShadowEnforcer never blocks, delays, or alters the actual execution outcome
- [ ] Agreement rate metric is accumulated across all observed actions
- [ ] Divergence count per posture level is accumulated and retrievable
- [ ] When `CARE_SHADOW_ENFORCER_LIVE` is absent or false, ShadowEnforcer does not run (no overhead)
- [ ] Unit tests confirm the observer does not affect execution outcomes
- [ ] Unit tests confirm metrics accumulate correctly from sample observations
