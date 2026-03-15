# 405: Session Management and Context Persistence

**Milestone**: 4 — Agent Execution Runtime
**Priority**: Medium (anti-amnesia — preserves team context across sessions)
**Estimated effort**: Medium
**Completed**: 2026-03-12
**Verified by**: SessionManager + PlatformSession + SessionCheckpoint + SessionState in `care_platform/execution/session.py`; 21 unit tests pass in `tests/unit/execution/test_session.py`

## Description

Implement session management that preserves agent team context across Claude Code sessions. Currently, sessions end and context is lost (anti-amnesia problem from COC). The platform must maintain team state, active tasks, and pending decisions across session boundaries. This upgrades the existing `.session-notes` pattern to a structured, persisted session record.

## Tasks

- [ ] Design session model:
  - `PlatformSession`: session_id, started_at, ended_at, active_teams, pending_held_actions, last_agent_actions, session_notes
  - `SessionCheckpoint`: point-in-time snapshot of team state
- [ ] Implement session lifecycle:
  - `SessionManager.start()` — begin a new session, load previous checkpoint
  - `SessionManager.checkpoint()` — save current state (can run periodically)
  - `SessionManager.end()` — final checkpoint on session close
- [ ] Implement automatic context loading:
  - On session start, load: active teams, pending HELD actions, last posture states, recent audit summary
  - Generate session briefing: "3 actions pending approval. DM team last ran 2 days ago. Content Creator has 15 of 20 daily drafts used."
- [ ] Implement session wrapup hook:
  - Triggered by `/wrapup` command
  - Creates final checkpoint
  - Generates session summary for handoff
  - Lists any open items (held actions, expiring envelopes, scheduled reviews)
- [ ] Implement session notes (structured, not free-form):
  - Machine-readable session notes that feed next session's briefing
  - Backward compatible with existing `.session-notes` format
- [ ] Write integration tests for session lifecycle

## Acceptance Criteria

- Session state persists across restart
- New session loads correct context automatically
- Session briefing provides actionable summary (not just a dump)
- `/wrapup` creates complete handoff document
- Integration tests verify round-trip

## Dependencies

- 301-307: Persistence layer (session records stored in DataFlow)
- 403: Human-in-the-loop queue (pending held actions included in briefing)

## References

- Existing `.session-notes` pattern in COC setup
- `/wrapup` command behavior in current CLAUDE.md
