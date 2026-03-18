# Verification Gradient

The verification gradient is the classification engine that determines how each agent action is handled. It sits between constraint envelope evaluation and action execution, mapping evaluation results into one of four levels: AUTO_APPROVED, FLAGGED, HELD, or BLOCKED.

---

## Four Verification Levels

| Level             | Meaning                                                | What Happens                                 |
| ----------------- | ------------------------------------------------------ | -------------------------------------------- |
| **AUTO_APPROVED** | Action is within all constraint boundaries             | Execute immediately, record audit anchor     |
| **FLAGGED**       | Action is near a boundary or matches a flagged pattern | Execute but highlight for operator review    |
| **HELD**          | Action exceeds a soft limit or matches a held pattern  | Queue in ApprovalQueue, await human decision |
| **BLOCKED**       | Action violates a hard constraint                      | Reject outright, record audit anchor         |

These levels are strictly ordered: BLOCKED > HELD > FLAGGED > AUTO_APPROVED. Escalation (moving up this order) is always allowed; downgrading is restricted by thoroughness and proximity rules.

---

## GradientEngine Classification

The `GradientEngine` class (`trust/constraint/gradient.py`) classifies actions through a three-step pipeline:

### Step 1: Envelope Evaluation

If a pre-computed `EnvelopeEvaluation` is provided:

- **DENIED** result -> immediately BLOCKED (no further checks)
- **NEAR_BOUNDARY** result -> start at FLAGGED (may be adjusted by thoroughness)
- **ALLOWED** result -> proceed to step 2

### Step 2: Pattern Matching

Gradient rules are matched against the action name using glob patterns. Rules are evaluated in order -- first match wins.

```yaml
# Example gradient rules
rules:
  - pattern: "publish:*"
    level: HELD
    reason: "Publishing requires human approval"
  - pattern: "read:*"
    level: AUTO_APPROVED
    reason: "Read operations are auto-approved"
  - pattern: "external:*"
    level: FLAGGED
    reason: "External actions are flagged for review"
```

### Step 3: Default Level

If no rule matches and no envelope evaluation determined the level, the configured default level applies. The default is typically HELD (fail-closed: unknown actions require human approval).

### Classification Output

The engine returns a `VerificationResult` containing:

- `level` -- the determined verification level
- `action` -- the action that was classified
- `agent_id` -- the agent attempting the action
- `thoroughness` -- which thoroughness level was used
- `matched_rule` -- which glob pattern matched (if any)
- `reason` -- human-readable explanation
- `envelope_evaluation` -- the full envelope evaluation (if provided)
- `duration_ms` -- classification time in milliseconds
- `proximity_alerts` -- alerts from ProximityScanner (if configured)
- `recommendations` -- actionable recommendations for the operator

---

## Verification Thoroughness

The GradientEngine supports three thoroughness levels that adjust classification strictness:

| Thoroughness | Typical Time | What It Checks                                    | When Used                                                         |
| ------------ | ------------ | ------------------------------------------------- | ----------------------------------------------------------------- |
| **QUICK**    | ~1ms         | Pattern matching only                             | Cache hits on routine, non-cross-team actions                     |
| **STANDARD** | ~5ms         | Pattern matching + constraint envelope evaluation | Default for most actions                                          |
| **FULL**     | ~50ms        | Pattern + envelope + full EATP chain verification | Cross-team actions, first action in session, sensitive operations |

### Thoroughness Adjustment Rules

Thoroughness adjusts the determined level with two rules:

- **FULL** is stricter: AUTO_APPROVED is bumped to FLAGGED
- **QUICK** is more permissive: FLAGGED is relaxed to AUTO_APPROVED

Two levels are never adjusted by thoroughness:

- **BLOCKED** -- hard safety boundary, always preserved
- **HELD** -- human approval requirement, always preserved

This means thoroughness can only affect the boundary between AUTO_APPROVED and FLAGGED, never the boundary between HELD/BLOCKED and lower levels.

---

## ProximityScanner Integration

When a `ProximityScanner` (from the EATP SDK) is configured on the GradientEngine, envelope dimension evaluations are fed through the scanner to detect constraint utilization near thresholds.

### How It Works

1. The GradientEngine converts CARE `DimensionEvaluation` results to EATP `ConstraintCheckResult` objects
2. The ProximityScanner scans for dimensions where utilization is approaching limits
3. If alerts are generated, they are attached to the `VerificationResult` as `proximity_alerts`
4. The scanner may escalate the verification level (monotonic -- proximity never downgrades)

### Monotonic Escalation

Proximity alerts can only escalate a level, never downgrade:

```
AUTO_APPROVED -> FLAGGED    (possible via proximity)
FLAGGED -> HELD             (possible via proximity)
HELD -> BLOCKED             (possible via proximity)
BLOCKED -> anything lower   (never -- hard boundary)
```

### Fault Tolerance

Proximity scanning is advisory. If the ProximityScanner raises an exception, classification proceeds without proximity data. A warning is logged, but the action is not blocked. This is an intentional exception to the fail-closed contract -- proximity scanning is observational enhancement, not a safety gate.

---

## Mapping to Human-on-the-Loop

The verification gradient directly implements the CARE Human-on-the-Loop model, where human involvement scales with action risk:

```
                   Human Involvement
                         ^
                         |
          BLOCKED  ------+------ Action rejected, human notified
                         |
          HELD     ------+------ Human must approve before action proceeds
                         |
          FLAGGED  ------+------ Action proceeds, human reviews after
                         |
          AUTO_APPROVED --+----- Action proceeds, logged for audit
                         |
                         +---------------------------------> Agent Autonomy
```

### How Each Level Maps to Human Interaction

| Level         | Human Role               | Timing                             | Agent Experience                             |
| ------------- | ------------------------ | ---------------------------------- | -------------------------------------------- |
| AUTO_APPROVED | Audit reviewer           | After the fact                     | No delay                                     |
| FLAGGED       | Review queue reader      | After execution, before next cycle | No delay, but flagged in dashboard           |
| HELD          | Approver                 | Before execution                   | Agent waits for approval via `ApprovalQueue` |
| BLOCKED       | Notified (for awareness) | Immediate                          | Action rejected with reason                  |

### Trust Posture Influence

The agent's trust posture indirectly affects verification through the constraint envelope and gradient rules. Higher-posture agents typically have wider envelopes and fewer HELD rules, but the posture itself does not bypass the gradient engine. Every action still passes through the full classification pipeline regardless of posture.

The one exception is `NEVER_DELEGATED_ACTIONS` -- actions in this set are always HELD regardless of posture or gradient rules (see [Trust Model](trust-model.md)).

---

## Recommendations Engine

The GradientEngine generates actionable recommendations alongside each classification:

- **BLOCKED**: "Action violates hard constraint on [dimension]. Cannot proceed."
- **HELD**: "Action exceeds soft limit on [dimension]. Requires human approval."
- **FLAGGED**: "Action near operational boundary. Review before proceeding."
- **Proximity alerts**: "[dimension] usage at [X]%. Consider reviewing resource consumption."

These recommendations appear in the verification result and are surfaced through the API and dashboard.

---

## Further Reading

- [Constraint Envelopes](constraint-envelopes.md) -- the five-dimension evaluation model that feeds the gradient
- [Trust Model](trust-model.md) -- overall trust architecture including postures and ShadowEnforcer
- [Fail-Closed Contract](fail-closed-contract.md) -- error path enforcement policy
