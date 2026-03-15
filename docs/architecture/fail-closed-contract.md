# Fail-Closed Contract

## Requirement

Every error path in the CARE Platform's trust and constraint layers must **deny, block, or restrict** — never silently allow. This is the fail-closed contract.

## What Fail-Closed Means

| Scenario                           | Required Behavior                 |
| ---------------------------------- | --------------------------------- |
| Exception during verification      | BLOCKED (not approved)            |
| Missing agent_id                   | BLOCKED (not ignored)             |
| Service unavailable                | BLOCKED (not bypassed)            |
| Unknown posture                    | PSEUDO_AGENT (most restrictive)   |
| Exception in constraint evaluation | DENIED (not allowed)              |
| Timeout during trust chain lookup  | BLOCKED (not cached stale result) |

## Scope

All `.py` files under:

- `src/care_platform/trust/`
- `src/care_platform/constraint/`
- `src/care_platform/audit/`
- `src/care_platform/persistence/`

## Exemptions

**ShadowEnforcer** (`shadow_enforcer.py`, `shadow_enforcer_live.py`) is exempt from the blocking requirement. The ShadowEnforcer is observational by design — it never blocks, holds, or modifies actions. It only records what WOULD happen. This is the fundamental contract of shadow enforcement.

**Trust decorators** (`decorators.py`) contain shadow mode wrappers that are intentionally fail-open for observation purposes.

## How to Write Compliant Code

### Do

```python
try:
    result = verify_agent(agent_id)
except Exception:
    logger.error("Verification failed for agent %s", agent_id)
    raise  # Or return BLOCKED/DENIED
```

### Don't

```python
try:
    result = verify_agent(agent_id)
except Exception:
    pass  # VIOLATION: silently allows on error

try:
    result = verify_agent(agent_id)
except Exception:
    return True  # VIOLATION: allows on error

try:
    result = verify_agent(agent_id)
except Exception:
    return None  # VIOLATION: caller may interpret None as allowed
```

## CI Enforcement

The `scripts/lint_fail_closed.py` script enforces this contract:

```bash
python scripts/lint_fail_closed.py
```

It scans all files in scope for:

- Bare `except: pass` (silently swallows errors)
- `return True` in except blocks (allows on error)

The script automatically exempts ShadowEnforcer files.

**`return None` in except blocks** is a manual review item. The lint does not flag it because `return None` has legitimate uses in query/utility functions (e.g., "chain not found", "unparseable timestamp"). For trust decision functions, `return None` should be avoided — use an explicit deny or re-raise instead. Code reviewers should flag `return None` in except blocks within verification, authorization, and enforcement code paths.

## Audit History

- **2026-03-15**: Initial audit — 43 files scanned, 1 violation found and fixed (timezone fallback in envelope.py replaced bare pass with logged warning)
