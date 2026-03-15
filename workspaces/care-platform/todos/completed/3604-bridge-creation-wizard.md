# Task 3604 — Bridge Creation Wizard

**Milestone**: M36 — Bridge API + Dashboard
**Dependencies**: 3601, 3602, 3603
**Evidence type**: Component tests, visual verification

## What

Create a multi-step bridge creation wizard UI:
1. **Step 1: Select Teams** — choose source and target teams from workspace
2. **Step 2: Choose Bridge Type** — Standing, Scoped, or Ad-Hoc with type-specific fields
3. **Step 3: Define Constraints** — set constraint envelope for the bridge (all 5 dimensions)
4. **Step 4: Set Information Sharing** — configure per-field sharing modes (auto-share, request-share, never-share)
5. **Step 5: Review & Submit** — summary view, submit for bilateral approval

## Where

- `apps/web/app/bridges/create/page.tsx` — wizard page
- `apps/web/app/bridges/create/components/` — step components

## Acceptance Criteria

- [ ] Multi-step form with progress indicator
- [ ] Team selection from available workspace teams
- [ ] Bridge type selection with type-specific field display
- [ ] Constraint editor for all 5 CARE dimensions
- [ ] Information sharing mode editor (per-field)
- [ ] Review step showing complete bridge configuration
- [ ] Submit calls POST /bridges endpoint
- [ ] Validation at each step before proceeding
- [ ] Apache 2.0 license headers on all files
