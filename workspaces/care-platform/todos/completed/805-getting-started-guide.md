# 805: Getting Started Guide

**Milestone**: 8 — Documentation and Developer Experience
**Priority**: Medium (drives adoption)
**Estimated effort**: Medium

## Description

Write a detailed getting-started guide that takes a new user from zero to a running governed agent team. Unlike the README (which is an overview), this guide is a step-by-step tutorial with expected output at each step.

## Tasks

- [ ] Create `docs/getting-started.md` tutorial covering:
  1. Install CARE Platform: `pip install care-platform`
  2. Configure `.env` (API keys, signing key)
  3. Run `care-platform init` — create genesis record
  4. Run `care-platform team add` — create a Content team from template
  5. Run `care-platform team establish` — create delegation chains
  6. Run `care-platform status` — see your team is active
  7. Create first agent action — auto-approved content draft
  8. Simulate a HELD action — publication attempt
  9. Approve it via CLI
  10. View audit trail: `care-platform audit report --team content --days 1`
- [ ] Include expected output for every command (captured from real runs)
- [ ] Include troubleshooting section:
  - "My genesis record fails to verify" (key mismatch)
  - "All actions are being BLOCKED" (envelope misconfiguration)
  - "HELD queue is empty but I expected an action" (gradient rule not configured)
- [ ] Validate the tutorial by running it on a fresh install
- [ ] Link from README to this guide

## Acceptance Criteria

- Tutorial works on a fresh install with no prior knowledge of the platform
- Expected output matches actual output (validated)
- Troubleshooting covers the three most common errors
- README links to guide

## Dependencies

- 801: README (links from there)
- 705: Organization Builder CLI (tutorial uses it)
- 304: Audit query CLI (tutorial uses it)
- 403: Human-in-the-loop approval (tutorial demonstrates it)

## References

- Existing getting-started pattern from `802-architecture-docs.md` (overlaps; separate docs)
