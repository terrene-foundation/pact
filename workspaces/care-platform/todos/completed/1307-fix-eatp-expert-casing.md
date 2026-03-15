# M13-T07: Fix eatp-expert.md casing

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M13 — Project Restructure
**Dependencies**: None

## What

Fix verification gradient level names and trust posture names in `.claude/agents/standards/eatp-expert.md`. Per `terrene-naming.md`: verification gradient levels must be UPPERCASE (AUTO_APPROVED, FLAGGED, HELD, BLOCKED) and trust postures must be UPPERCASE (PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED).

## Where

- `.claude/agents/standards/eatp-expert.md` (lines ~60-77)

## Evidence

- All instances use correct UPPERCASE per terrene-naming.md
