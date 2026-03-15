#!/usr/bin/env python3
# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Lint rule: fail-closed compliance for trust and constraint layers.

Scans trust/constraint/audit/persistence code for patterns that could
silently allow actions when an error occurs. The CARE Platform's trust
layer must fail closed — any error must result in denial, not approval.

Usage:
    python scripts/lint_fail_closed.py [--fix]

Exit codes:
    0: All files pass
    1: Violations found
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# Directories to scan
SCAN_DIRS = [
    "src/care_platform/trust",
    "src/care_platform/constraint",
    "src/care_platform/audit",
    "src/care_platform/persistence",
]

# Files exempt from fail-closed requirement (intentional fail-open)
EXEMPT_FILES = {
    "shadow_enforcer.py",  # Observational — never blocks by design
    "shadow_enforcer_live.py",  # Live shadow — same exemption
    "decorators.py",  # Shadow decorator has intentional fail-open for observation
}

# Patterns that indicate fail-open violations
FAIL_OPEN_PATTERNS = [
    # Bare except with pass (silently swallows errors)
    (r"except\s*:\s*\n\s*pass", "bare except:pass — errors silently swallowed"),
    # except Exception with pass (same issue, slightly more specific)
    (
        r"except\s+\w+(?:\s*,\s*\w+)*\s*:\s*\n\s*pass\s*$",
        "except with pass — errors silently swallowed",
    ),
]

# AST patterns to check
SUSPICIOUS_RETURNS_IN_EXCEPT = {
    "return True",
    "return None",
    "return []",
    "return {}",
}


class Violation:
    """A fail-closed violation found during linting."""

    def __init__(self, file: Path, line: int, pattern: str, context: str) -> None:
        self.file = file
        self.line = line
        self.pattern = pattern
        self.context = context

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.pattern} — {self.context}"


def scan_file(filepath: Path) -> list[Violation]:
    """Scan a single file for fail-open patterns."""
    violations: list[Violation] = []
    content = filepath.read_text()
    lines = content.splitlines()

    # Check regex patterns
    for pattern, description in FAIL_OPEN_PATTERNS:
        for match in re.finditer(pattern, content, re.MULTILINE):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                Violation(filepath, line_num, description, lines[line_num - 1].strip())
            )

    # AST analysis for except blocks
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            _check_except_handler(node, filepath, lines, violations)

    return violations


def _check_except_handler(
    handler: ast.ExceptHandler,
    filepath: Path,
    lines: list[str],
    violations: list[Violation],
) -> None:
    """Check an except handler for fail-open patterns."""
    # Check for bare pass in except block
    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
        violations.append(
            Violation(
                filepath,
                handler.lineno,
                "except with bare pass",
                lines[handler.lineno - 1].strip() if handler.lineno <= len(lines) else "",
            )
        )
        return

    # Check for return True/None in except blocks (potential fail-open)
    for node in ast.walk(handler):
        if isinstance(node, ast.Return):
            if isinstance(node.value, ast.Constant) and node.value.value is True:
                violations.append(
                    Violation(
                        filepath,
                        node.lineno,
                        "return True in except block — may silently allow",
                        lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                    )
                )


def main() -> int:
    """Run the fail-closed lint check."""
    root = Path(__file__).parent.parent
    violations: list[Violation] = []
    files_scanned = 0
    files_clean = 0

    for scan_dir in SCAN_DIRS:
        dir_path = root / scan_dir
        if not dir_path.exists():
            continue
        for py_file in sorted(dir_path.rglob("*.py")):
            if py_file.name in EXEMPT_FILES:
                continue
            if py_file.name == "__init__.py":
                continue

            file_violations = scan_file(py_file)
            files_scanned += 1
            if file_violations:
                violations.extend(file_violations)
            else:
                files_clean += 1

    # Report
    print(f"\nFail-closed lint: {files_scanned} files scanned, {files_clean} clean")

    if violations:
        print(f"\n{len(violations)} violation(s) found:\n")
        for v in violations:
            print(f"  {v}")
        print(
            "\nFail-closed contract: every error in the trust/constraint layer "
            "must deny, not allow. See docs/architecture/fail-closed-contract.md"
        )
        return 1

    print("All files pass fail-closed check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
