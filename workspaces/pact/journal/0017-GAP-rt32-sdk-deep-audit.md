---
type: GAP
date: 2026-04-05
created_at: 2026-04-05T11:00:00+08:00
author: agent
session_turn: 25
project: pact
topic: RT32 deep audit of kailash-py 0.7.0 and kailash-rs PACT modules
phase: redteam
tags: [kailash-py, kailash-rs, pact-engine, cross-sdk, security, RT32]
---

# RT32: SDK Deep Audit — kailash-py 0.7.0 + kailash-rs

## Context

After migrating SupervisorOrchestrator to compose PactEngine 0.7.0 (which resolved all 8 RT31 issues), a deep audit was conducted on both SDKs to find remaining gaps.

## kailash-py Findings (5 issues filed)

| ID   | Classification | Issue                                                                                                                                               | GitHub         |
| ---- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| F1.2 | **BUG**        | `_ReadOnlyGovernanceView` missing 4 mutation methods in blocklist (`create_ksp`, `designate_acting_occupant`, `reject_bridge`, `set_task_envelope`) | kailash-py#276 |
| F8.1 | **BUG**        | `GovernanceContext.from_dict()` allows forged context with arbitrary permissions                                                                    | kailash-py#277 |
| F8.2 | **BUG**        | Engine uses `posixpath.normpath` instead of `normalize_resource_path` in `_evaluate_against_envelope`                                               | kailash-py#278 |
| F2.4 | **GAP**        | Rate limits (`max_actions_per_day/hour`) not evaluated in `verify_action` — dead config                                                             | kailash-py#279 |
| F6.1 | **GAP**        | `EnvelopeSpec` missing `gradient_thresholds` in YAML loader                                                                                         | kailash-py#280 |

## kailash-rs Findings (4 gaps filed)

| Gap                          | Severity | Description                                         | GitHub         |
| ---------------------------- | -------- | --------------------------------------------------- | -------------- |
| Per-node governance callback | HIGH     | No node-level verify_action during graph traversal  | kailash-rs#184 |
| HeldActionCallback trait     | MEDIUM   | No trait for external approval integration          | kailash-rs#184 |
| ReadOnlyGovernanceView       | MEDIUM   | No read/write separation on engine access           | kailash-rs#184 |
| Fresh budget per submit      | MEDIUM   | Shared budget tracker across supervisor invocations | kailash-rs#184 |

## Verified Correct (22 checks passed)

Thread safety, fail-closed, NaN guards, compilation limits, D/T/R grammar, MCP default-deny, MCP rate limiting, frozen envelopes, tightening validation, degenerate detection, gradient dereliction, yaml.safe_load, enforcement mode env guard, fresh supervisor per submit, WorkResult NaN guard, CostTracker NaN guard, DISABLED mode protection, DataFlowEngine builder, health_check.

## For Discussion

1. The `_ReadOnlyGovernanceView` blocklist approach (explicit deny list) is fragile — every new mutation method must be manually added. Would a whitelist approach (explicit allow list of read-only methods) be more secure?
2. `GovernanceContext.from_dict()` exists for serialization across process boundaries (e.g., multi-worker deployments). If removed, how should governance context be transmitted between processes?
3. The rate limit gap (F2.4) requires the engine to either become stateful (per-role counters) or require callers to inject call counts. Which approach aligns better with the engine's current stateless-per-call design?
