# CARE Platform Project Skills

Skills specific to the CARE Platform — the Terrene Foundation's open-source governed operational model.

## Available Skills

| Skill                        | File                                                                     | Description                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Trust Layer Patterns         | [trust-layer-patterns.md](trust-layer-patterns.md)                       | EATP decorator integration, enforcement pipeline, verification gradient, fail-closed contract |
| Dashboard Patterns           | [dashboard-patterns.md](dashboard-patterns.md)                           | Design system, page architecture, WebSocket patterns, auth/notification systems               |
| Store Backend Implementation | [store-backend-implementation.md](store-backend-implementation.md)       | Step-by-step guide for adding new TrustPlaneStore backends                                    |
| Security Patterns            | [trust-plane-security-patterns.md](trust-plane-security-patterns.md)     | 11 hardened security patterns from 14 red team rounds                                         |
| Enterprise Features          | [trust-plane-enterprise-features.md](trust-plane-enterprise-features.md) | RBAC, OIDC, SIEM, Dashboard, Archive, Shadow mode                                             |

## When to Use

- **Working on trust/constraint code** → Trust Layer Patterns + `care-trust-specialist` agent
- **Working on frontend dashboard** → Dashboard Patterns + `care-dashboard-specialist` agent
- **Adding a new store backend** → Store Backend Implementation
- **Security-sensitive changes** → Security Patterns
- **Understanding EATP protocol** → See `skills/26-eatp-reference/` instead

## Cross-References

- `skills/26-eatp-reference/` — EATP protocol and SDK reference
- `agents/standards/eatp-expert.md` — EATP expert agent
- `agents/project/care-trust-specialist.md` — Trust layer specialist
- `agents/project/care-dashboard-specialist.md` — Dashboard specialist
- `docs/architecture/fail-closed-contract.md` — Fail-closed requirement
- `workspaces/care-platform/decisions.yml` — All architectural decisions
