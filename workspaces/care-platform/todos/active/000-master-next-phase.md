# CARE Platform — Phase 5 Master Roadmap

**Updated**: 2026-03-18
**Status**: APPROVED
**Scope**: 32 tasks across 7 milestones
**Supersedes**: Phase A (Polish & Deploy), Phase B (Org Builder), Phase C (DM Vertical)
**Continues from**: 241 completed tasks across Phases 1-4

---

## Overview

Restructure the codebase to reflect the Fractal Dual Plane architecture, add the Department layer, build the auto-generation engine, dog-food with the full Foundation org (11 teams), wire known data issues, and reach production green-light. Phase C (DM Vertical, M23-M25) is deferred — not in scope for this phase.

---

## M0b — Quick Wins (4 tasks, 2 hours)

Prerequisite fixes before M38 restructure begins. No dependencies.

| #    | Task                                                            | Priority | Effort |
| ---- | --------------------------------------------------------------- | -------- | ------ |
| 6001 | Remove CARE_DEV_MODE=true from root Dockerfile                  | Critical | Tiny   |
| 6002 | Fix pyproject.toml: remove broken eatp extra, update classifier | High     | Tiny   |
| 6003 | Create py.typed marker at src/care_platform/py.typed            | Medium   | Tiny   |
| 6004 | Create CHANGELOG.md for 0.1.0 release                           | Medium   | Small  |

---

## M38 — TRUST/BUILD/USE Codebase Restructure (6 tasks, 2-3 days)

Restructure `src/care_platform/` into three top-level packages reflecting the Fractal Dual Plane architecture.

- **trust/** — governance primitives (Trust Plane)
- **build/** — define organizations (Build Plane)
- **use/** — run and observe (Use Plane)

| #    | Task                                                              | Priority | Effort |
| ---- | ----------------------------------------------------------------- | -------- | ------ |
| 6010 | Create trust/build/use directory structure with **init**.py files | Critical | Small  |
| 6011 | Move trust-plane modules into trust/                              | Critical | Large  |
| 6012 | Move build-plane modules into build/                              | Critical | Large  |
| 6013 | Move use-plane modules into use/                                  | Critical | Large  |
| 6014 | Update all source imports across the entire codebase              | Critical | Large  |
| 6015 | Update all test imports and verify all tests pass                 | Critical | Large  |
| 6016 | Update CLAUDE.md, documentation, and any path references          | High     | Medium |

---

## M39 — Department Layer (5 tasks, 2-3 days)

Add `DepartmentConfig` between organization and team levels. Enables 3-level monotonic tightening: department → team → agent.

**Depends on**: M38

| #    | Task                                                                 | Priority | Effort |
| ---- | -------------------------------------------------------------------- | -------- | ------ |
| 6020 | Create DepartmentConfig model (id, name, teams, head, envelope)      | Critical | Medium |
| 6021 | Add departments field to OrgDefinition, update OrgBuilder            | Critical | Medium |
| 6022 | Extend validate_org_detailed() for 3-level monotonic tightening      | Critical | Large  |
| 6023 | Update templates to include department grouping                      | High     | Medium |
| 6024 | Tests for department validation, tightening, and builder integration | High     | Medium |

---

## M40 — Auto-Generation Engine (6 tasks, 3-5 days)

Create `OrgGenerator` that produces valid organizations from high-level definitions.

**Depends on**: M39

| #    | Task                                                                             | Priority | Effort |
| ---- | -------------------------------------------------------------------------------- | -------- | ------ |
| 6030 | Create RoleCatalog with standard role definitions                                | High     | Medium |
| 6031 | Create EnvelopeDeriver — generate valid child envelopes via monotonic tightening | Critical | Medium |
| 6032 | Create OrgGenerator class — YAML input → OrgDefinition output                    | Critical | Large  |
| 6033 | Universal agent injection — auto-inject CoordinatorAgent into every team         | High     | Medium |
| 6034 | Add `org generate` CLI command                                                   | High     | Medium |
| 6035 | Comprehensive tests for auto-generation                                          | High     | Large  |

---

## M41 — Foundation Full Org — 11 Teams (7 tasks, 3-5 days)

Define the complete Terrene Foundation as an organization. Dog-food test.

**Depends on**: M40

| #    | Task                                                                        | Priority | Effort |
| ---- | --------------------------------------------------------------------------- | -------- | ------ |
| 6040 | Define Tier 1 teams: Media/DM, Standards, Governance, Partnerships, Website | Critical | Large  |
| 6041 | Define Tier 2 teams: Community, Developer Relations, Finance                | High     | Medium |
| 6042 | Define Tier 3 teams: Certification, Training, Legal                         | High     | Medium |
| 6043 | Create department groupings for all 11 teams                                | High     | Medium |
| 6044 | Define cross-team bridges between all teams                                 | High     | Medium |
| 6045 | Foundation org full validation test suite — round-trip                      | Critical | Large  |
| 6046 | Migrate existing Python templates to YAML in build/templates/builtin/       | Medium   | Medium |

---

## M42 — Known Issues / Data Wiring (4 tasks, 1-2 days)

Fix the 3 known data-wiring issues plus discovered sub-issues.

**Depends on**: M38 (parallel with M39-M41)

| #    | Task                                                                 | Priority | Effort |
| ---- | -------------------------------------------------------------------- | -------- | ------ |
| 6050 | Wire verification_stats + fix \_build_platform_api() fallback        | High     | Small  |
| 6051 | Wire AuditChain from seed data into PlatformAPI for dashboard trends | High     | Medium |
| 6052 | Create upgrade-evidence API endpoint for PostureUpgradeWizard        | High     | Medium |
| 6053 | Wire PostureUpgradeWizard to real upgrade-evidence API               | High     | Small  |

---

## M43 — Production Green-Light (5 tasks, 2-3 days)

Final polish for production deployment readiness.

**Depends on**: M42

| #    | Task                                                                                           | Priority | Effort |
| ---- | ---------------------------------------------------------------------------------------------- | -------- | ------ |
| 6060 | Create 3 missing docs pages: trust-model.md, constraint-envelopes.md, verification-gradient.md | High     | Medium |
| 6061 | Add frontend CI job (npm ci, lint, build, test) to GitHub Actions                              | High     | Medium |
| 6062 | Add Docker Compose smoke test to CI                                                            | Medium   | Medium |
| 6063 | Align Dockerfile port strategy (document 8080 Cloud Run vs 8000 compose)                       | Medium   | Small  |
| 6064 | Document PyPI trusted publisher setup steps                                                    | Medium   | Small  |

---

## Dependency Graph

```
M0b (Quick Wins)
  │
M38 (TRUST/BUILD/USE Restructure)
  │
  ├── M39 (Department Layer)
  │     │
  │     └── M40 (Auto-Generation Engine)
  │           │
  │           └── M41 (Foundation 11 Teams)
  │
  └── M42 (Known Issues) ← parallel with M39-M41
        │
        └── M43 (Production Green-Light)
```

---

## Effort Summary

| Milestone | Tasks  | Tiny  | Small | Medium | Large  | Estimated     |
| --------- | ------ | ----- | ----- | ------ | ------ | ------------- |
| M0b       | 4      | 3     | 1     | 0      | 0      | 2 hours       |
| M38       | 7      | 0     | 1     | 1      | 5      | 2-3 days      |
| M39       | 5      | 0     | 0     | 4      | 1      | 2-3 days      |
| M40       | 6      | 0     | 0     | 4      | 2      | 3-5 days      |
| M41       | 7      | 0     | 0     | 4      | 2      | 3-5 days      |
| M42       | 4      | 0     | 2     | 2      | 0      | 1-2 days      |
| M43       | 5      | 0     | 2     | 2      | 0      | 2-3 days      |
| **Total** | **38** | **3** | **6** | **17** | **10** | **2-3 weeks** |

---

## Deferred

- **Phase C (DM Vertical)** — M23-M25 (tasks 5049-5061) — deferred, not in scope for Phase 5.

---

## Superseded

The previous Phase A (Polish & Deploy, M12-M18), Phase B (Org Builder, M19-M22), and Phase C (DM Vertical, M23-M25) task files have been archived to `todos/completed/` with note "Superseded by Phase 5 restructure (2026-03-18)".

Prerequisite M0 task 5000 (CI path fix) was completed before this restructure.
