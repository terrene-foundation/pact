# Todo 3001: Full Phase 3 Security and Standards Validation

**Milestone**: M30 — Final Validation
**Priority**: High
**Effort**: Large
**Source**: Phase 3 requirement
**Dependencies**: 2501, 2502, 2503, 2504, 2505, 2601, 2602, 2603, 2604, 2701, 2702, 2703, 2704, 2705, 2801, 2802, 2803, 2804, 2805, 2806, 2807, 2808, 2809, 2810, 2901, 2902, 2903, 2904

## What

Deploy security-reviewer, deep-analyst, and gold-standards-validator agents to conduct a full red team (RT11) across all Phase 3 deliverables. The validation must cover:

- **LLM backend security**: API key handling, error message sanitisation, prompt injection surface in the Kaizen bridge, rate limit and retry logic correctness
- **Frontend security**: XSS surface in the dashboard views, CSRF protection on approval actions, WebSocket authentication bypass attempts
- **Docker configuration**: Non-root user enforcement, secret leakage via environment variables or image layers, network isolation between services
- **EATP alignment**: Verify that all five trust posture modes match the CARE standard specification exactly; verify constraint dimensions use canonical names throughout
- **Security hardening items**: Carry forward any unresolved HIGH findings from RT1-RT10 and confirm they are resolved or formally accepted

Produce a structured red team report at the output path.

## Where

- `workspaces/care-platform/04-validate/rt11-phase3-report.md`

## Evidence

- [ ] Red team report is present at the output path
- [ ] All CRITICAL findings are resolved before the report is finalised
- [ ] All HIGH findings are either resolved or have a documented accepted-risk justification
- [ ] EATP alignment section confirms all five posture modes match the specification
- [ ] Constraint dimension names throughout the codebase match the canonical CARE standard names
- [ ] Frontend XSS surface assessment is complete
- [ ] Docker security assessment is complete (non-root, no secret leakage, network isolation)
- [ ] All RT1-RT10 carry-forward items are addressed
