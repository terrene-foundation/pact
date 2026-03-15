# Todo 3502: Keyword Normalization

**Milestone**: M35 — Security Hardening
**Priority**: High
**Effort**: Small
**Source**: Phase 4 plan
**Dependencies**: None

## What

Normalize action strings in `PostureEnforcer` before keyword matching to close bypass vectors identified in RT11-H2. Currently `_is_consequential_action()` and `_is_planning_action()` compare raw action strings against keyword sets, which can be bypassed via CamelCase ("deleteDraft"), hyphenation ("delete-draft"), underscore-separation ("delete_draft"), or unicode homoglyphs.

Add a `_normalize_action(action: str) -> str` private method that applies the following transformations in order:

1. `unicodedata.normalize('NFKD', action)` — decompose unicode to ASCII equivalents
2. `.encode('ascii', 'ignore').decode('ascii')` — strip remaining non-ASCII characters
3. Insert a space before each uppercase letter to split CamelCase ("deleteDraft" becomes "delete Draft")
4. Replace hyphens and underscores with spaces
5. `.casefold()` — case-fold for locale-independent case-insensitive comparison
6. Split into words; keyword matching checks each individual word against the keyword sets rather than the whole string

Call `_normalize_action()` at the top of both `_is_consequential_action()` and `_is_planning_action()` so all keyword comparisons operate on normalized tokens.

## Where

- `src/care_platform/execution/posture_enforcer.py`

## Evidence

- [ ] `_normalize_action()` method exists on `PostureEnforcer`
- [ ] `_normalize_action("deleteDraft")` returns a form that triggers consequential detection
- [ ] `_normalize_action("delete-draft")` returns a form that triggers consequential detection
- [ ] `_normalize_action("delete_draft")` returns a form that triggers consequential detection
- [ ] A unicode homoglyph input (e.g. "dеlete" with Cyrillic е) is normalized and detected correctly
- [ ] `_is_consequential_action()` calls `_normalize_action()` before keyword matching
- [ ] `_is_planning_action()` calls `_normalize_action()` before keyword matching
- [ ] All existing `PostureEnforcer` tests still pass
- [ ] New unit tests cover CamelCase, hyphenated, underscore, and unicode homoglyph inputs
