# Task 6044: Define Cross-Functional Bridges Between All Teams

**Milestone**: M41
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Define all Cross-Functional Bridges between Foundation teams. Bridges enable governed information and task flow across team boundaries. Three bridge types: Standing (permanent), Scoped (project-based), Ad-Hoc (one-off).

Known required bridges (minimum):

- **Standards → Governance** (Standing): Standards team publishes specs; Governance team reviews and ratifies
- **Standards → Website** (Standing): Approved specs are published to the website
- **Media/DM → Website** (Standing): Media content published to web presence
- **Developer Relations → Standards** (Standing): DevRel feeds community feedback into standards process
- **Governance → Legal** (Standing): Constitutional matters escalated to Legal
- **Certification → Standards** (Standing): Certification requirements anchored to standards versions
- **Community → Developer Relations** (Standing): Community signals escalated to DevRel

## Acceptance Criteria

- [ ] At minimum 7 bridges defined (the list above)
- [ ] Each bridge specifies: source team, target team, bridge type, permitted capability scope, and envelope for the bridged actions
- [ ] Bridge envelopes are tighter than both source and target team envelopes (most restrictive wins)
- [ ] Bridges defined in `build/templates/builtin/foundation/bridges.yaml`
- [ ] Full Foundation org with all bridges passes `validate_org_detailed()` (or equivalent bridge validation)
- [ ] Comments in YAML explain each bridge's purpose and governance rationale

## Dependencies

- Tasks 6040-6043 (all teams and departments must be defined)
- Task 6021 (OrgDefinition must support bridges — verify existing bridge support or extend here)
