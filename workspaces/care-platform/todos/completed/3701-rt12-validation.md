# Todo 3701: RT12 Red Team Validation

**Milestone**: M37 — Red Team
**Priority**: High
**Effort**: Large
**Source**: Phase 4 plan
**Dependencies**: 3105, 3204, 3305, 3404, 3501, 3502, 3503, 3504, 3601, 3605

## What

Deploy security-reviewer, deep-analyst, and gold-standards-validator to conduct the RT12 red team exercise covering the full Phase 4 deliverables. RT12 is the final red team round before the platform readiness assessment.

Security audit scope:

- Bridge trust integrity: can bridge delegations be forged or bypassed without a valid `BridgeDelegation` in the trust store?
- Constraint intersection correctness: can `compute_bridge_envelope` produce an effective envelope wider than either input envelope?
- Cross-team audit completeness: are dual audit anchors consistently created for every cross-team action, and are they retrievable via the audit endpoint?
- Information sharing enforcement: can `never-share` fields leak through bridge responses under any code path?
- Posture resolution: can an agent operating under a lower trust posture escalate to higher-posture operations by routing tasks through a bridge?
- Prompt injection hardening: does the system prompt from todo 3501 prevent jailbreaking via crafted task payloads? Test with known injection patterns.
- Keyword normalization: after todo 3502, do CamelCase, hyphenated, underscore-separated, and unicode homoglyph action strings still bypass `PostureEnforcer` detection?
- Rate limiting: does the middleware from todo 3503 actually block requests after the configured threshold? Test both GET and mutating tiers.
- Security headers: are all headers from todo 3504 present on every response, including error responses?
- RT11 carry-forward items: confirm all findings rated H1 through H5 in the RT11 report are resolved or have accepted-risk entries.

Standards compliance checks:

- Bridge type labels use canonical names: Standing, Scoped, Ad-Hoc (exact capitalisation, no synonyms)
- All new code uses "Cross-Functional Bridge" consistently — not "cross-team bridge" or "inter-team connector"
- Apache 2.0 license header on all new source files introduced in Phase 4
- No stubs, `raise NotImplementedError`, or `pass # placeholder` in production code
- Verification gradient level names are uppercase: AUTO_APPROVED, FLAGGED, HELD, BLOCKED
- Trust posture names are uppercase: PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED

All CRITICAL findings must be resolved before the RT12 report is marked complete. HIGH findings must be resolved or have a written accepted-risk entry with justification and owner.

## Where

- `workspaces/care-platform/04-validate/rt12-phase4-report.md`

## Evidence

- [ ] `workspaces/care-platform/04-validate/rt12-phase4-report.md` exists
- [ ] Report documents all tested attack vectors with pass/fail result for each
- [ ] Zero unresolved CRITICAL findings
- [ ] Zero unresolved HIGH findings (or each has an accepted-risk entry with justification and owner)
- [ ] Bridge trust integrity: forgery and bypass attempts documented as blocked
- [ ] Constraint intersection correctness: no widening vector found
- [ ] Information sharing: no `never-share` leakage path identified
- [ ] Posture escalation via bridge: no escalation path found
- [ ] Prompt injection: system prompt holds against all tested patterns
- [ ] Keyword normalization: all bypass patterns now detected
- [ ] Rate limiting: threshold enforcement verified at both tiers
- [ ] Security headers: all headers confirmed present including on error responses
- [ ] RT11 H1-H5 carry-forward items all marked resolved
- [ ] Standards compliance: canonical names, Apache 2.0 headers, no stubs confirmed
