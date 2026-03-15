# 210: Implement Inter-Agent Messaging with Replay Protection

**Milestone**: 2 — EATP Trust Integration
**Priority**: Medium (needed for cross-team delegation)
**Estimated effort**: Medium
**Status**: COMPLETED — 2026-03-12

## Completion Summary

`AgentMessage`, `MessageChannel`, and `MessageRouter` implemented in `care_platform/trust/messaging.py`.

- `care_platform/trust/messaging.py` — full message passing with nonce-based replay protection
- `MessageType` enum: REQUEST, RESPONSE, NOTIFICATION, DELEGATION_REQUEST, DELEGATION_RESPONSE, DATA_REQUEST
- Nonce registry and timestamp window validation prevent replay attacks
- `MessageChannel` enforces participant membership
- `MessageRouter` routes across multiple channels
- `tests/unit/trust/test_messaging.py` — authenticity verification, replay protection, revoked sender rejection

## Description

Implement the inter-agent messaging layer — typed channels with envelope authentication and replay protection.

## Tasks

- [x] `care_platform/trust/messaging.py` with `AgentMessage` model
- [x] Message ID with nonce for replay protection
- [x] All message types implemented
- [x] Nonce-based deduplication and timestamp window validation
- [x] `MessageChannel` — typed communication channel
- [x] `MessageRouter` — routing across channels
- [x] Unit tests (creation, signing, replay protection, revoked sender rejection)

## Acceptance Criteria

- [x] Messages authenticated via delegation chain proof
- [x] Replay protection prevents message reuse
- [x] Revoked agents cannot send valid messages
- [x] All message types functional
- [x] Unit tests passing

## References

- `care_platform/trust/messaging.py`
- `tests/unit/trust/test_messaging.py`
