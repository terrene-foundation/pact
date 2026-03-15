# Todo 3504: Security Response Headers

**Milestone**: M35 — Security Hardening
**Priority**: High
**Effort**: Small
**Source**: Phase 4 plan
**Dependencies**: None

## What

Add security response headers to every HTTP response via a Starlette middleware class. This addresses RT11-H4, which found that the API returns no security headers, leaving browser-based clients exposed to clickjacking, MIME-sniffing, and related attacks.

Create `src/care_platform/api/security_headers.py` with a `SecurityHeadersMiddleware` class (extending `starlette.middleware.base.BaseHTTPMiddleware`) that appends the following headers to every response:

- `Content-Security-Policy: default-src 'self'`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` — added only when the request host is not `localhost` or `127.0.0.1`, so local development is not broken by HSTS preloading

Register `SecurityHeadersMiddleware` in `src/care_platform/api/server.py` using `app.add_middleware()` so it wraps all routes including health endpoints.

## Where

- `src/care_platform/api/security_headers.py` (new)
- `src/care_platform/api/server.py` (register middleware)

## Evidence

- [ ] `src/care_platform/api/security_headers.py` exists with `SecurityHeadersMiddleware`
- [ ] `Content-Security-Policy: default-src 'self'` present on all responses
- [ ] `X-Frame-Options: DENY` present on all responses
- [ ] `X-Content-Type-Options: nosniff` present on all responses
- [ ] `Referrer-Policy: strict-origin-when-cross-origin` present on all responses
- [ ] `Permissions-Policy: camera=(), microphone=(), geolocation=()` present on all responses
- [ ] `Strict-Transport-Security` present on non-localhost responses
- [ ] `Strict-Transport-Security` absent on localhost responses
- [ ] `SecurityHeadersMiddleware` registered in `server.py`
- [ ] Unit tests verify presence of all headers on a test response
- [ ] Unit test verifies HSTS is omitted for localhost requests
- [ ] All existing API tests still pass
