# 808: Documentation Validation

**Milestone**: 8 — Documentation and Developer Experience
**Priority**: Medium (documentation that doesn't work erodes trust)
**Estimated effort**: Small

## Description

Validate that all code examples in the documentation actually work. Documentation that contains broken code examples is worse than no documentation — it wastes developer time and erodes trust in the platform. Use documentation-validator to check all code blocks.

## Tasks

- [ ] Delegate to documentation-validator to check all code in:
  - `README.md` — quick start code blocks
  - `docs/getting-started.md` — all 10-step tutorial commands
  - `docs/architecture.md` — code snippets
  - `docs/trust-model.md` — code examples
  - `docs/constraint-envelopes.md` — configuration examples
  - All `examples/*/README.md` files
- [ ] Fix any broken code examples found
- [ ] Set up CI check for documentation code blocks:
  - Extract code blocks with `python` language tag and run them
  - Fail CI if any example raises an unhandled exception
- [ ] Validate all YAML configuration examples:
  - Load each example YAML through the platform's schema validation
  - Fail if any example YAML is invalid
- [ ] Review all command-line examples:
  - Run each `care-platform` CLI command shown in docs
  - Capture actual output and compare to documented expected output
  - Update documented output where it has drifted

## Acceptance Criteria

- All Python code examples in documentation execute without errors
- All YAML examples validate against schema
- All CLI examples produce documented output
- CI job added that validates documentation code blocks
- documentation-validator review completed

## Dependencies

- 801-807: All documentation exists to validate
- 112: Package installed (needed to run examples)

## References

- documentation-validator agent: `agents/testing/documentation-validator`
