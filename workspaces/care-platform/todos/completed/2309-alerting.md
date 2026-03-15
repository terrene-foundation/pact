# Todo 2309: Error Reporting and Alerting via Webhooks

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: Medium
**Effort**: Small-Medium
**Source**: I10
**Dependencies**: 2101 (.env loading wired — webhook URL via env var), 2308 (structured logging — alerting uses same event context)

## What

Add webhook-based alerting for CRITICAL governance events. When any of the following occurs, a JSON payload is posted to a configured webhook URL:

- Trust chain revocation (any agent revoked)
- BLOCKED action (constraint enforcement triggered)
- Trust chain integrity failure (hash chain mismatch or signature failure)
- Genesis record change (root of trust modified or re-established)

The webhook URL is configured via `CARE_ALERT_WEBHOOK_URL` env var. If the env var is not set, alerting is silently skipped. Each alert payload includes: event type, timestamp, agent ID, action ID (if applicable), correlation ID (if applicable), and a human-readable description.

Delivery must be fire-and-forget (non-blocking): a failed webhook post must log the failure but must not block the operation that triggered it.

## Where

- `src/care_platform/api/alerts.py` — `AlertDispatcher` class with `dispatch(event_type, payload)` method; HTTP POST logic with timeout and non-blocking failure handling
- `src/care_platform/config/env.py` — `CARE_ALERT_WEBHOOK_URL` env var declaration and documentation

## Evidence

- [ ] A revocation event triggers a webhook POST to `CARE_ALERT_WEBHOOK_URL`
- [ ] A BLOCKED verification result triggers a webhook POST
- [ ] A trust chain integrity failure triggers a webhook POST
- [ ] A genesis record change triggers a webhook POST
- [ ] Webhook payload is valid JSON with required fields (event type, timestamp, agent ID, correlation ID)
- [ ] When `CARE_ALERT_WEBHOOK_URL` is not set, no webhook is attempted and no error is raised
- [ ] A failed webhook POST logs the failure but does not propagate an exception to the caller
- [ ] Unit tests mock the HTTP client and assert payload structure for each event type
- [ ] Unit test confirms no exception raised when webhook URL is absent
