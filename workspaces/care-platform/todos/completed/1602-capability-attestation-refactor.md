# M16-T02: Capability attestation — separate authorization from capability

**Status**: ACTIVE
**Priority**: Critical
**Milestone**: M16 — Gap Closure: Runtime Enforcement
**Dependencies**: 1301-1304

## What

Currently `CapabilityAttestation.has_capability()` conflates authorization with capability. Separate:
- Authorization = "agent is permitted" (constraint envelope check)
- Capability = "agent is able" (attestation check)

Add `AuthorizationCheck` that evaluates both independently.

## Where

- Modify: `src/care_platform/trust/attestation.py` (add `has_authorization()`)
- New: `src/care_platform/trust/authorization.py` (AuthorizationCheck)
- Modify: `src/care_platform/constraint/middleware.py`

## Evidence

- Test: agent with capability but no envelope authorization → blocked
- Test: agent with authorization but no capability attestation → blocked
- Test: agent with both → passes
