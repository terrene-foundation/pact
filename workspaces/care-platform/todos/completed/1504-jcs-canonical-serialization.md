# M15-T04: JCS canonical serialization (RFC 8785)

**Status**: ACTIVE
**Priority**: High
**Milestone**: M15 — EATP v2.2 Alignment
**Dependencies**: 1301-1304

## What

Replace current `json.dumps(signable, sort_keys=True, separators=(",", ":"))` in `constraint/signing.py` with RFC 8785 JCS. JCS handles edge cases sort_keys doesn't: Unicode normalization, number serialization.

Add `jcs>=0.2.1` to dependencies. Add `canonical_version` field to `SignedEnvelope` for migration support.

**Also**: Create a shared `canonical_hash(data)` utility in `trust/jcs.py` and migrate ALL content_hash implementations to use it. Currently inconsistent approaches across envelope.py (model_dump_json exclude), attestation.py (string concat), reasoning.py (string concat), versioning (json.dumps sort_keys). All must use JCS for consistent integrity guarantees.

## Where

- Modify: `src/care_platform/constraint/signing.py`
- New utility: `src/care_platform/trust/jcs.py` (canonical_hash wrapper used by ALL modules)
- Modify: `src/care_platform/audit/anchor.py` (hash computation)
- Modify: `src/care_platform/trust/attestation.py` (content_hash → canonical_hash)
- Modify: `src/care_platform/trust/reasoning.py` (compute_hash → canonical_hash)
- Modify: `src/care_platform/constraint/envelope.py` (content_hash → canonical_hash)
- Modify: `pyproject.toml` (add jcs dependency)

## Evidence

- Tests: canonical output matches RFC 8785 test vectors; existing signature tests still pass
