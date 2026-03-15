# 806: Security Policy and Vulnerability Disclosure

**Milestone**: 8 — Documentation and Developer Experience
**Priority**: Medium (required for open-source credibility)
**Estimated effort**: Small

## Description

Create a security policy and responsible disclosure process. As an open-source platform handling cryptographic trust chains, the CARE Platform has a heightened responsibility for security transparency. Vulnerabilities in constraint enforcement or audit chain integrity have direct trust implications.

## Tasks

- [ ] Create `SECURITY.md`:
  - Supported versions table
  - How to report vulnerabilities (private email, not public GitHub issue)
  - Response time commitment (acknowledge within 48h, patch timeline)
  - Security researcher acknowledgment policy (public credit after patch)
  - Scope: what is in scope vs out of scope
- [ ] Define security-critical areas:
  - Cryptographic trust chain integrity (CRITICAL)
  - Constraint envelope bypass (CRITICAL)
  - Audit chain tampering (CRITICAL)
  - Authentication bypass for approval API (HIGH)
  - Information disclosure in audit export (MEDIUM)
- [ ] Create security review checklist for contributors:
  - Items to check before submitting a PR touching trust, crypto, or enforcement modules
  - Link to security-reviewer agent
- [ ] Configure GitHub security features:
  - Enable vulnerability reporting via GitHub Security Advisories
  - Configure dependency scanning (Dependabot)
  - Configure secret scanning
- [ ] Write initial threat model (`docs/security/threat-model.md`):
  - Attacker: rogue agent trying to expand its own constraints
  - Attacker: external actor trying to poison audit chain
  - Attacker: insider trying to approve their own HELD actions
  - Mitigations for each threat

## Acceptance Criteria

- `SECURITY.md` present and follows standard format
- Security-critical areas documented with severity levels
- Threat model covers three primary attack scenarios
- GitHub security features enabled
- Contributor security checklist created

## Dependencies

- 204: Constraint envelope signing (what makes signing tamper-evident)
- 205: Audit anchor integration (what protects the chain)
- 403: Human-in-the-loop approval (what prevents self-approval)

## References

- `rules/security.md` — Security rules for this project
- GitHub Security Advisories documentation
