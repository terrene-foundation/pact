# Todo 3304: KaizenBridge Cross-Team Routing

**Milestone**: M33 — Cross-Team Execution
**Priority**: High
**Effort**: Large
**Source**: Phase 4 plan
**Dependencies**: 3101, 3103, 3104, 3301

## What

Extend `KaizenBridge.execute_task()` to handle tasks whose `team_id` differs from the executing agent's team. Cross-team tasks must travel through the bridge trust layer before reaching the LLM backend.

When `task.team_id` differs from the agent's team, the method must:

1. Look up the ACTIVE bridge between the two teams via `BridgeManager`
2. Create a `BridgeDelegation` record for this specific task (scoped to the task's action type)
3. Compute the effective constraint envelope and effective posture using the helpers from 3201 and 3103
4. Apply the bridge verification pipeline from 3301 — if the result is not AUTO_APPROVED or FLAGGED, do not proceed to LLM execution
5. Execute via the LLM backend with bridge context injected into the system prompt
6. Create dual audit anchors (from 3104) — one recorded in the source team's audit chain, one in the target team's audit chain
7. Return the result with bridge metadata: `bridge_id`, `effective_posture`, and `effective_envelope_hash`

The system prompt for cross-team tasks must include the following context block, populated with the actual team names and a plain-language summary of the effective envelope:

```
You are operating under a Cross-Functional Bridge between [source_team] and [target_team].
Your actions are constrained to: [effective_envelope_summary].
```

This prompt injection ensures the LLM is explicitly aware of its operating context and constraint scope during cross-team execution.

## Where

- `src/care_platform/execution/kaizen_bridge.py` (extend)

## Evidence

- [ ] `execute_task()` detects cross-team tasks via `task.team_id` comparison
- [ ] Active bridge looked up for the team pair; missing bridge raises an appropriate error
- [ ] `BridgeDelegation` record created for the specific task before execution
- [ ] Effective envelope computed and used (not the raw agent envelope)
- [ ] Effective posture computed and used (not the raw agent posture)
- [ ] Bridge verification pipeline (3301) applied; non-approved results do not reach LLM
- [ ] System prompt includes bridge context block with team names and envelope summary
- [ ] Dual audit anchors created: one in source team chain, one in target team chain
- [ ] Result includes `bridge_id`, `effective_posture`, and `effective_envelope_hash`
- [ ] Same-team tasks are unaffected by this change (no regression)
- [ ] All unit tests pass
