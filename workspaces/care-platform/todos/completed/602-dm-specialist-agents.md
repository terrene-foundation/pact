# 602: Define DM Specialist Agents with Constraint Envelopes

**Milestone**: 6 — DM Team Vertical
**Priority**: High
**Estimated effort**: Medium
**Depends on**: 601
**Status**: COMPLETED
**Completed**: 2026-03-12

## Description

Define all DM specialist agents with full constraint envelopes. Each specialist has narrower constraints than the Team Lead (monotonic tightening).

## Tasks

- [x] Define **Content Creator** agent — DM_CONTENT_CREATOR with DM_CONTENT_ENVELOPE
  - Role: Draft LinkedIn posts, blog content, format content
  - Envelope: $0 financial, draft-only write, 08:00-20:00, max 20 actions/day, internal channels only
  - BLOCKED: publish, approve, schedule, send externally, modify published content
- [x] Define **Analytics** agent — DM_ANALYTICS with DM_ANALYTICS_ENVELOPE
  - Role: Collect metrics, generate reports, trend analysis
  - Envelope: $0 financial, read-only analytics, 24/7 monitoring, internal reporting only
  - BLOCKED: modify content, access PII
- [x] Define **Community Manager** agent — DM_COMMUNITY_MANAGER with DM_COMMUNITY_ENVELOPE
  - Role: Draft community responses, moderate content, flag issues
  - Envelope: $0 financial, draft-only, 08:00-20:00, internal channels only
  - BLOCKED: publish, approve, modify brand guidelines
- [x] Define **SEO Specialist** agent — DM_SEO_SPECIALIST with DM_SEO_ENVELOPE
  - Role: Keyword analysis, structure suggestions, SEO audits
  - Envelope: $0 financial, analysis and suggestions only, no publishing
  - BLOCKED: publish, approve, modify brand guidelines
- [x] Verify monotonic tightening — validate_dm_team() checks each specialist subset of lead
- [x] Create capability attestation for each specialist (via AgentConfig.capabilities)
- [x] Write validation tests (tightening verification, envelope completeness)

## Acceptance Criteria

- [x] All specialist agents defined with complete constraint envelopes
- [x] Monotonic tightening verified (every specialist financial <= lead, communication subset of lead)
- [x] Capability attestations consistent — capabilities field on each AgentConfig
- [x] Validation tests passing

## Notes

Implementation uses 4 specialist agents (Content Creator, Analytics, Community Manager, SEO Specialist) under 1 team lead, differing slightly from the spec's 5 agents (Scheduling, Podcast Clip Extractor, Outreach). The implemented agents cover core DM functions with the same EATP patterns.

## Implementation

- `care_platform/verticals/dm_team.py` — DM_CONTENT_CREATOR, DM_ANALYTICS, DM_COMMUNITY_MANAGER, DM_SEO_SPECIALIST with envelopes
- `tests/unit/verticals/test_dm_team.py` — TestDMConstraintTightening, TestDMAnalyticsTemporal, TestDMContentCreatorCommunication
