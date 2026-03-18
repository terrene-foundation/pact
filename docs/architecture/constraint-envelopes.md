# Constraint Envelopes

A constraint envelope defines the five-dimensional boundary within which an agent may act. Every agent in the CARE Platform is assigned a constraint envelope that governs its Financial, Operational, Temporal, Data Access, and Communication dimensions. The envelope is frozen after construction, signed with Ed25519, and enforced at runtime via the [Verification Gradient](verification-gradient.md).

---

## Five Constraint Dimensions

Each dimension evaluates an agent action and returns one of three results:

- **ALLOWED** -- action is within the constraint boundary
- **NEAR_BOUNDARY** -- action is approaching a limit (triggers FLAGGED or HELD)
- **DENIED** -- action violates a hard constraint (triggers BLOCKED)

The overall envelope evaluation uses the most restrictive dimension result: if any dimension returns DENIED, the overall result is DENIED.

### 1. Financial

Controls spending limits for agent actions.

| Parameter                     | Description                                               |
| ----------------------------- | --------------------------------------------------------- |
| `max_spend_usd`               | Maximum per-action spend (hard limit)                     |
| `requires_approval_above_usd` | Soft limit -- actions above this amount are NEAR_BOUNDARY |
| `api_cost_budget_usd`         | Cumulative API budget ceiling                             |

**Evaluation logic**: Cumulative budget is checked first. Then per-action spend is compared against `max_spend_usd`. If spend exceeds `requires_approval_above_usd`, the result is NEAR_BOUNDARY. If utilization exceeds 80% of `max_spend_usd`, the result is also NEAR_BOUNDARY.

Financial configuration is optional. When `financial` is `None`, the agent has no spending capability -- the tightest possible financial constraint.

### 2. Operational

Controls which actions an agent may perform and at what rate.

| Parameter             | Description                                                     |
| --------------------- | --------------------------------------------------------------- |
| `allowed_actions`     | Whitelist of permitted actions (if set, action must be in list) |
| `blocked_actions`     | Blacklist of prohibited actions (always enforced)               |
| `max_actions_per_day` | Rate limit (hard limit)                                         |

**Evaluation logic**: Blocked actions are checked first, then the allowed list. If rate limit utilization exceeds 80%, the result is NEAR_BOUNDARY.

### 3. Temporal

Controls when an agent may act.

| Parameter            | Description                                                     |
| -------------------- | --------------------------------------------------------------- |
| `active_hours_start` | Start of active window (HH:MM format)                           |
| `active_hours_end`   | End of active window (HH:MM format)                             |
| `blackout_periods`   | List of dates when no actions are allowed (YYYY-MM-DD or MM-DD) |
| `timezone`           | Timezone for temporal evaluation (default: UTC)                 |

**Evaluation logic**: Blackout periods are checked first (they take precedence). Then the active hours window is evaluated. Overnight windows (where start > end, e.g., 22:00-06:00) are supported. Invalid timezone configuration falls back to UTC with a logged warning (fail-closed: evaluation still runs).

### 4. Data Access

Controls which data paths an agent may read or write.

| Parameter            | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `read_paths`         | Glob-pattern list of allowed read paths               |
| `write_paths`        | Glob-pattern list of allowed write paths              |
| `blocked_data_types` | Data types that are always blocked regardless of path |

**Evaluation logic**: Blocked data types are checked first. Then read or write paths are validated against the configured path lists using both prefix matching and glob pattern matching.

### 5. Communication

Controls how an agent communicates externally.

| Parameter                    | Description                                                            |
| ---------------------------- | ---------------------------------------------------------------------- |
| `internal_only`              | When true, all external communication is DENIED                        |
| `external_requires_approval` | When true, external communication is NEAR_BOUNDARY (requires approval) |
| `allowed_channels`           | List of permitted communication channels                               |

**Evaluation logic**: `internal_only` is checked first. Then `external_requires_approval` gates external actions as NEAR_BOUNDARY.

### Additional Dimensions

Two supplemental dimensions extend the core five:

- **Confidentiality clearance** -- compares data classification (PUBLIC through TOP_SECRET) against the envelope's clearance level. Data above the agent's clearance is DENIED.
- **Reasoning required** -- when any dimension has `reasoning_required=True`, the agent must provide a reasoning trace. Missing traces result in NEAR_BOUNDARY (HELD for human review).

---

## Monotonic Tightening

When trust is delegated from a parent authority to a child agent, the child's constraint envelope must be a monotonic tightening of the parent's. The child can only narrow constraints, never widen them.

The `is_tighter_than()` method on `ConstraintEnvelope` validates this rule across all dimensions:

| Dimension        | Tightening Rule                                                                                                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Financial        | Child `max_spend_usd` must be <= parent. Child with financial when parent has None is rejected (parent disallows all spending).                                                                          |
| Operational      | Child `allowed_actions` must be a subset of parent. Child must include all parent `blocked_actions`. Child `max_actions_per_day` must be <= parent. Child cannot remove a rate limit the parent imposes. |
| Temporal         | Child active hours must be within parent active hours (minute-based comparison handles overnight windows). Child must include all parent blackout periods.                                               |
| Data Access      | Child `read_paths` must be covered by parent `read_paths` (glob prefix matching). Same for `write_paths`. Child must include all parent `blocked_data_types`.                                            |
| Communication    | If parent is `internal_only`, child must also be. If parent requires approval for external, child must too.                                                                                              |
| Confidentiality  | Child clearance cannot exceed parent clearance.                                                                                                                                                          |
| Reasoning        | Child cannot remove `reasoning_required` set by parent.                                                                                                                                                  |
| Delegation depth | Child `max_delegation_depth` cannot exceed parent.                                                                                                                                                       |

This monotonic property is fundamental to the trust model: it guarantees that trust can only be narrowed as it flows through the delegation chain, never widened.

---

## Envelope Signing (Ed25519)

Constraint envelopes are cryptographically signed to prevent agents from modifying their assigned constraints. The signing module (`trust/constraint/signing.py`) provides:

### SignedEnvelope

A `SignedEnvelope` wraps a `ConstraintEnvelope` with:

- **Ed25519 signature** -- covers all five constraint dimensions plus signer identity and version number
- **Signer identity** -- who signed the envelope (authority or admin)
- **Timestamp** -- when the envelope was signed
- **Version number** -- for version chain tracking
- **Previous version hash** -- SHA-256 link to the previous version
- **Canonical version** -- serialization format identifier (`jcs-rfc8785` -- RFC 8785 JSON Canonicalization Scheme)

### Signing Process

```
1. Serialize constraint config using JCS (RFC 8785) for deterministic output
2. Include signer_id and version in the signable payload
3. Sign the payload with Ed25519 private key
4. Store the hex-encoded signature
5. Delete the private key reference after signing (RT11-L5)
```

### Verification

```python
signed_envelope.verify_signature(public_key_bytes)
# Returns True if the signature is valid for the current content
# Returns False (with warning log) if tampered or key mismatch
```

Verification failures are logged at warning level so operators are alerted to potential tampering.

### Version History

The `EnvelopeVersionHistory` class maintains an ordered list of signed envelope versions. Each new version is linked to the previous via its content hash, forming a verifiable version chain. Adding a new version requires re-signing (since the version number and previous_version_hash change).

### Expiry

Signed envelopes expire after 90 days from signing. Expired envelopes are rejected during evaluation (fail-closed).

---

## Constraint Intersection Formula

When evaluating an action, the overall constraint result is computed by intersecting all dimension results:

```
overall = most_restrictive(dim_1, dim_2, ..., dim_n)

where:
  DENIED > NEAR_BOUNDARY > ALLOWED
```

In code:

```python
if any(d.result == DENIED for d in dimensions):
    overall = DENIED
elif any(d.result == NEAR_BOUNDARY for d in dimensions):
    overall = NEAR_BOUNDARY
else:
    overall = ALLOWED
```

This intersection guarantees that a single violated dimension blocks the entire action. There is no "majority vote" -- all dimensions must pass.

---

## Verification Cache

The `VerificationCache` (`trust/constraint/cache.py`) is an LRU cache with per-entry TTL eviction that stores recent verification results.

### Cache Key

```
(agent_id, action, envelope_content_hash)
```

The content hash ensures that cache entries are automatically invalidated when an envelope's constraints change.

### Cache Behavior

- **LRU eviction** -- when the cache exceeds `max_size`, the least recently used entry is evicted
- **TTL expiry** -- each entry has a time-to-live; expired entries are removed on access
- **Agent invalidation** -- `invalidate(agent_id)` removes all cached entries for a specific agent (used when envelopes or postures change)
- **Thread-safe** -- all operations are protected by a lock

### Cache and Verification Thoroughness

The cache integrates with the [verification gradient's thoroughness levels](verification-gradient.md). Cache hits on routine, non-cross-team actions may use QUICK thoroughness (~1ms), while cache misses trigger STANDARD or FULL verification.

---

## Frozen Envelopes

The `ConstraintEnvelope` model uses Pydantic's `frozen=True` configuration:

```python
class ConstraintEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
```

This prevents post-creation modification of any constraint field. Code that needs to update an envelope must create a new instance, which then requires a new signature. This design prevents accidental or intentional constraint widening after an envelope has been signed and assigned.

---

## Further Reading

- [Trust Model](trust-model.md) -- overall trust architecture
- [Verification Gradient](verification-gradient.md) -- how constraint evaluation maps to action handling
- [Fail-Closed Contract](fail-closed-contract.md) -- error path enforcement
