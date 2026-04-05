---
type: DECISION
date: 2026-04-02
created_at: 2026-04-02T16:50:00+08:00
author: agent
session_turn: 8
project: pact
topic: Gradient thresholds wired L1→L3 via re-export + API + CLI + example
phase: implement
tags: [gradient, thresholds, L1-wiring, kailash-pact-0.6.0, envelopes]
---

# Gradient Thresholds Wired from L1 to L3

## Context

kailash-pact 0.6.0 added `RoleEnvelope.gradient_thresholds: GradientThresholdsConfig | None` with per-dimension thresholds (financial only in v0.6.0). The L3 platform constructed `RoleEnvelope` in 3 places (CLI, org router, envelope router) without passing `gradient_thresholds`, and the L1 `EnvelopeSpec` YAML parser does not yet have the field.

## Decision

Wire gradient thresholds at L3 by:

1. **Re-export** `DimensionThresholds` + `GradientThresholdsConfig` from `pact_platform.build.config.schema`
2. **API endpoint** (`set_role_envelope`): Parse `gradient_thresholds` from request body, validate via `_validate_envelope_numerics()`, construct typed objects, pass to `RoleEnvelope`
3. **CLI + org router**: Use `getattr(spec, "gradient_thresholds", None)` for forward-compatibility when L1 adds the field to `EnvelopeSpec`
4. **University example**: Add thresholds to CS Chair envelope ($500 auto-approve, $2K flag, $5K hold)

## Alternatives Considered

- **Wait for L1 EnvelopeSpec to add the field**: Would block L3 API consumers from using gradient thresholds until upstream releases. Rejected — API should accept thresholds now.
- **Define a separate L3 config type**: Would create a parallel type hierarchy. Rejected — L1 types are canonical.

## Consequences

- API consumers can set per-dimension gradient thresholds via `PUT /api/v1/governance/envelopes/{role_address}/role`
- YAML-loaded orgs cannot specify gradient thresholds until L1 adds the field to `EnvelopeSpec` (tracked as upstream gap)
- `DimensionThresholds` validates ordering (auto <= flag <= hold) and finiteness (NaN/Inf rejected) at L1 construction time

## For Discussion

1. Given that `GradientThresholdsConfig` currently only has a `financial` field, should L3 validation warn when non-financial dimensions are attempted, or silently ignore them until L1 adds more dimensions?
2. If the L1 `EnvelopeSpec` had been a Pydantic model with `model_config = ConfigDict(extra="allow")`, the `getattr` workaround would have been unnecessary — does this suggest an upstream design pattern change?
3. What is the migration path when L1 adds `temporal`, `operational`, etc. dimensions to `GradientThresholdsConfig` — will L3 need code changes or just re-export updates?
