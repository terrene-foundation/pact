# Task 6034: Add `org generate` CLI Command

**Milestone**: M40
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Add a `care org generate` subcommand to the CLI that accepts a YAML file describing an organization and outputs the fully validated `OrgDefinition` (as YAML or JSON). This makes the OrgGenerator accessible to users without writing Python.

```bash
# Usage
care org generate --input foundation.yaml --output foundation-full.yaml
care org generate --input foundation.yaml --format json
care org generate --input foundation.yaml --dry-run  # validate only, no output
```

## Acceptance Criteria

- [ ] `care org generate --input <file>` reads the input YAML and calls `OrgGenerator.from_yaml()`
- [ ] `--output <file>` writes the generated OrgDefinition as YAML (default: stdout)
- [ ] `--format json` outputs JSON instead of YAML
- [ ] `--dry-run` validates input and reports pass/fail without writing output
- [ ] Validation errors are reported as clear human-readable messages (not Python tracebacks)
- [ ] `care org generate --help` shows clear usage documentation
- [ ] Integration test: `care org generate --input examples/foundation.yaml --dry-run` exits 0
- [ ] Integration test: invalid YAML input exits non-zero with descriptive error

## Dependencies

- Task 6032 (OrgGenerator must exist)
- Task 6033 (coordinator injection must work)
- Task 6012 (CLI lives in build/cli/ after M38 restructure)
