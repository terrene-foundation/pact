# Task 6002: Fix pyproject.toml — Remove Broken eatp Extra, Update Classifier

**Milestone**: M0b
**Priority**: High
**Effort**: Tiny
**Status**: Active

## Description

`pyproject.toml` has two issues:

1. The `all` optional-dependencies group includes an `eatp` extra that does not resolve correctly (broken package reference). This causes `pip install care-platform[all]` to fail.
2. The Development Status classifier is likely still set to `"Development Status :: 3 - Alpha"` or an incorrect value. It should reflect 0.1.0 Alpha.

## Acceptance Criteria

- [ ] The broken `eatp` reference is removed from the `[project.optional-dependencies]` `all` group
- [ ] If `eatp` is needed as a dependency, it is added correctly with the right package name and version specifier, or documented as a manual install
- [ ] Development Status classifier is set to `"Development Status :: 3 - Alpha"` (consistent with 0.1.0 pre-release status)
- [ ] `pip install -e .` succeeds without warnings about unresolvable extras
- [ ] `pip install -e ".[all]"` succeeds or fails with a clear, intentional message if some extras are intentionally unavailable

## Dependencies

- None.
