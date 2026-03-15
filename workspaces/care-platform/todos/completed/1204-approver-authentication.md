# 1204: Approver Authentication

**Priority**: High
**Effort**: Medium
**Source**: RT3 Theme E
**Dependencies**: None

## Problem

The approval queue accepts any string as approver_id with no authentication. Anyone who knows an approver ID can approve held actions.

## Implementation

Create `care_platform/execution/approver_auth.py`:

- Ed25519 keypair management for approvers
- Signed approval/rejection decisions
- ApprovalQueue integration: verify signature before accepting decision
- Approver registry: map approver_id to public key
- Challenge-response for interactive approvals

## Acceptance Criteria

- [ ] Approval decisions are cryptographically signed
- [ ] Forged approver_id is rejected (signature verification fails)
- [ ] Approver registry maps identities to public keys
- [ ] Tests verify signature-based approval and rejection
