# Todo 3104: Cross-Team Audit Anchoring

**Milestone**: M31 — Bridge Trust Foundation
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3101

## What

Implement dual audit anchor creation for cross-bridge actions. Every action taken through a bridge must produce two linked audit records — one in the source team's chain and one in the target team's chain — with cryptographic cross-references between them.

### `BridgeAuditAnchor`

A Pydantic model extending `AuditAnchor` (from `src/care_platform/audit/anchor.py`) with cross-team fields:

- `bridge_id: str` — the bridge through which the action was taken
- `source_team_id: str`
- `target_team_id: str`
- `counterpart_anchor_hash: str | None` — SHA-256 hash of the other team's corresponding anchor (None until the counterpart is created)
- `side: Literal["source", "target"]` — which team's chain this anchor belongs to

Each `BridgeAuditAnchor` also records on the inherited fields:

- `action` — the cross-team action
- `envelope_id` — the bridge constraint envelope that was active
- `metadata` — include `effective_posture` and `effective_verification_level`

### `create_bridge_audit_pair`

```python
def create_bridge_audit_pair(
    action: str,
    bridge: Bridge,
    source_agent: str,
    target_agent: str,
    effective_posture: TrustPostureLevel,
    effective_verification_level: VerificationLevel,
    source_anchor_chain: AuditAnchorChain,
    target_anchor_chain: AuditAnchorChain,
) -> tuple[BridgeAuditAnchor, BridgeAuditAnchor]:
```

Source-first commit pattern:

1. Create and commit the source-side anchor (no `counterpart_anchor_hash` yet — set to None)
2. Compute `source_anchor.content_hash`
3. Create the target-side anchor with `counterpart_anchor_hash = source_anchor.content_hash`
4. Attempt to update the source anchor's `counterpart_anchor_hash` to the target anchor's hash
5. If step 4 fails (target-side creation failed), the source anchor's `counterpart_anchor_hash` remains None — this is acceptable and must be detectable during audit

The function returns `(source_anchor, target_anchor)`.

Import `AuditAnchor` from `src/care_platform/audit/anchor.py` and use the existing `content_hash` field already defined there.

## Where

- `src/care_platform/audit/bridge_audit.py` (new file)

## Evidence

- [ ] `src/care_platform/audit/bridge_audit.py` exists with `BridgeAuditAnchor` model
- [ ] `BridgeAuditAnchor` extends `AuditAnchor` with `bridge_id`, `source_team_id`, `target_team_id`, `counterpart_anchor_hash`, `side` fields
- [ ] `create_bridge_audit_pair()` function creates two linked anchors
- [ ] Source anchor is committed first (source-first pattern)
- [ ] Target anchor's `counterpart_anchor_hash` equals source anchor's `content_hash`
- [ ] Source anchor is updated with target anchor's hash after target creation succeeds
- [ ] If target-side creation fails, source anchor's `counterpart_anchor_hash` remains None (acceptable partial state)
- [ ] `metadata` on each anchor includes `effective_posture` and `effective_verification_level`
- [ ] Audit chain integrity preserved (each anchor chains to the previous in its team's sequence)
- [ ] All unit tests pass
