# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-18

### Added

- **Trust Plane**: Genesis Records, delegation chains, constraint envelopes (5 dimensions), verification gradient (AUTO_APPROVED / FLAGGED / HELD / BLOCKED), trust postures (PSEUDO_AGENT through DELEGATED), ShadowEnforcer, cascade revocation, audit anchors with hash chaining.
- **EATP SDK Integration**: Trust decorators (@care_verified, @care_audited, @care_shadow), CareEnforcementPipeline with GradientEngine + StrictEnforcer, ProximityScanner, reasoning trace factories with JCS signing, SD-JWT dual binding.
- **Constraint System**: Constraint envelope signing (Ed25519), content-hash verification cache, circuit breaker, fail-closed enforcement across 43 source files.
- **Organization Builder**: OrgDefinition model, OrgBuilder fluent API, validate_org_detailed() with comprehensive semantic validation, template registry with 6 built-in templates, YAML import/export, org diff, org deploy CLI.
- **Cross-Functional Bridges**: Standing, Scoped, and Ad-Hoc bridge types, CoordinatorAgent, bridge lifecycle management, bridge trust and posture integration.
- **Agent Runtime**: Agent registry, approval queue, LLM backend abstraction (OpenAI, Anthropic, Google, local), Kaizen bridge, session management, posture enforcement.
- **API Server**: FastAPI with authentication (Firebase SSO + static token), CORS, rate limiting, security headers, WebSocket with Sec-WebSocket-Protocol auth, graceful shutdown, Prometheus metrics, structured logging.
- **Web Dashboard**: 17 Next.js pages, 30+ React components, CARE design system, governance actions (suspend, revoke, posture change), ShadowEnforcer dashboard, cost report, audit export (CSV/JSON), posture upgrade wizard, notification system, 47 WCAG 2.1 AA accessibility fixes.
- **Flutter App**: Cross-platform mobile/desktop companion app.
- **CI/CD**: GitHub Actions for lint, test (Python 3.11/3.12/3.13 matrix, 90% coverage gate), Docker build, MkDocs deployment, PyPI publishing with trusted publisher.
- **Deployment**: Docker Compose (PostgreSQL + API + Web), Cloud Run Dockerfile, deployment configuration documentation.
- **DM Team Vertical**: First reference vertical with 5 agents, 5 envelopes, full monotonic tightening.

### Security

- Fail-closed on all trust paths (unknown states resolve to BLOCKED).
- Thread-safe shared mutable state (11 components with threading.Lock).
- Non-root container users in all Docker images.
- No hardcoded secrets (all from .env).
- Parameterized database queries throughout.

[0.1.0]: https://github.com/terrene-foundation/care/releases/tag/v0.1.0
