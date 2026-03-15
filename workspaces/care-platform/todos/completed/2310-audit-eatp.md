# Todo 2310: Audit Chain EATP Completeness

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: Medium
**Effort**: Small-Medium
**Source**: RT5-26, RT5-27
**Dependencies**: 2303 (delegation expiry — delegation_id must be reliably present), 205 (audit anchor integration — completed)

## What

Add two fields that are currently absent from the audit anchor model, making the anchor a complete EATP accountability record:

- `delegation_id: Optional[str]` — the identifier of the delegation record in effect when the action was authorised. Populated from the delegation chain resolution during verification. `None` for genesis-authority actions.
- `genesis_authority: str` — the identifier of the genesis record at the root of the trust chain for this action. Always present; allows external auditors to verify the entire lineage back to the trust root without querying intermediate records.

Both fields must be populated during anchor creation in the verification pipeline, not added as empty post-hoc fields. The audit anchor serialisation (used for hash-chain and EATP interoperability export) must include both fields.

## Where

- `src/care_platform/audit/anchor.py` — add the two fields to the anchor model and populate them in the creation path

## Evidence

- [ ] `delegation_id` field present on the audit anchor model with `Optional[str]` type
- [ ] `genesis_authority` field present on the audit anchor model with `str` type
- [ ] `delegation_id` is populated from the active delegation record during anchor creation
- [ ] `delegation_id` is `None` for actions authorised directly by the genesis authority
- [ ] `genesis_authority` is always populated with the genesis record ID
- [ ] Both fields appear in the anchor's serialised JSON output
- [ ] Hash-chain computation includes both new fields (no regression on integrity checks)
- [ ] Unit tests confirm field population for delegated actions and for genesis-authority actions
- [ ] EATP interoperability: an external consumer can reconstruct the full trust lineage from anchor fields alone
