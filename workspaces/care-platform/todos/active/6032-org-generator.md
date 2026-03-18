# Task 6032: Create OrgGenerator Class

**Milestone**: M40
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

Create `OrgGenerator` — the high-level interface that takes a compact YAML or dict description of an organization and produces a fully valid `OrgDefinition` complete with departments, teams, agents, envelopes, and coordinator injection.

Input format (YAML):

```yaml
org:
  id: "terrene-foundation"
  name: "Terrene Foundation"
  envelope:
    financial_limit: 10000
    # ... other dimensions

departments:
  - id: "standards"
    name: "Standards Department"
    teams:
      - id: "eatp-team"
        name: "EATP Standards Team"
        roles:
          - coordinator
          - analyst
          - writer
```

The generator:

1. Derives department envelopes from org envelope via EnvelopeDeriver
2. Derives team envelopes from department envelopes
3. Creates agents from role definitions in RoleCatalog
4. Auto-injects CoordinatorAgent into every team (task 6033)
5. Runs `validate_org_detailed()` on the generated org
6. Returns the validated `OrgDefinition`

## Acceptance Criteria

- [ ] `OrgGenerator` class in `src/care_platform/build/org/generator.py`
- [ ] `OrgGenerator.from_yaml(yaml_str: str) -> OrgDefinition` works end-to-end
- [ ] `OrgGenerator.from_dict(data: dict) -> OrgDefinition` works end-to-end
- [ ] Generated org passes `validate_org_detailed()` without errors
- [ ] Unsatisfiable inputs (e.g., team envelope tighter than org) raise `GenerationError` with clear message
- [ ] `OrgGenerator` exported from `care_platform.build`
- [ ] At least 3 example YAML inputs in tests covering: single team, multi-team with department, Foundation-style org

## Dependencies

- Tasks 6030, 6031 (RoleCatalog and EnvelopeDeriver)
- Task 6022 (validate_org_detailed with 3-level tightening)
- Task 6021 (OrgDefinition with departments)
