# M15-T02: SD-JWT selective disclosure

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M15 — EATP v2.2 Alignment
**Dependencies**: 1501

## What

Implement SD-JWT (Selective Disclosure JSON Web Token) based on confidentiality level. Trust chain elements serialized as SD-JWTs where fields above the viewer's clearance are disclosed only as hashes.

Consider: `sd-jwt` Python library or implement minimal SD-JWT per IETF draft. Fields to selectively disclose: reasoning traces, constraint details, metadata.

## Where

- New: `src/care_platform/trust/sd_jwt.py`

## Evidence

- Tests: create SD-JWT from delegation record, verify disclosure at each confidentiality level, verify undisclosed fields are hash-only
