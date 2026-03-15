# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the fail-closed lint script."""

import textwrap
from pathlib import Path

import pytest

from scripts.lint_fail_closed import Violation, scan_file


@pytest.fixture()
def tmp_py(tmp_path):
    """Factory for creating temporary Python files."""

    def _create(content: str, name: str = "test_file.py") -> Path:
        p = tmp_path / name
        p.write_text(textwrap.dedent(content))
        return p

    return _create


class TestDetectsViolations:
    """Tests that the linter catches known fail-open patterns."""

    def test_bare_except_pass(self, tmp_py):
        """Catches bare except: pass."""
        f = tmp_py(
            """
            try:
                verify()
            except:
                pass
        """
        )
        violations = scan_file(f)
        assert len(violations) >= 1

    def test_except_exception_pass(self, tmp_py):
        """Catches except Exception: pass."""
        f = tmp_py(
            """
            try:
                verify()
            except Exception:
                pass
        """
        )
        violations = scan_file(f)
        assert len(violations) >= 1

    def test_return_true_in_except(self, tmp_py):
        """Catches return True in except block."""
        f = tmp_py(
            """
            def check():
                try:
                    verify()
                except Exception:
                    return True
        """
        )
        violations = scan_file(f)
        assert any("return True" in v.pattern for v in violations)

    def test_return_none_in_except_not_flagged(self, tmp_py):
        """return None is NOT flagged (too many false positives in utility code)."""
        f = tmp_py(
            """
            def check():
                try:
                    verify()
                except Exception:
                    return None
        """
        )
        violations = scan_file(f)
        # return None has legitimate uses in query/utility functions,
        # so it's not flagged by the lint. Manual review handles these.
        assert len(violations) == 0


class TestPassesCompliantCode:
    """Tests that the linter passes properly fail-closed code."""

    def test_except_with_reraise(self, tmp_py):
        """Allows except that re-raises."""
        f = tmp_py(
            """
            def check():
                try:
                    verify()
                except Exception:
                    logger.error("Failed")
                    raise
        """
        )
        violations = scan_file(f)
        assert len(violations) == 0

    def test_except_with_return_false(self, tmp_py):
        """Allows except that returns False (deny)."""
        f = tmp_py(
            """
            def check():
                try:
                    verify()
                except Exception:
                    return False
        """
        )
        violations = scan_file(f)
        assert len(violations) == 0

    def test_except_with_logging(self, tmp_py):
        """Allows except with logging and explicit deny."""
        f = tmp_py(
            """
            def check():
                try:
                    verify()
                except Exception as e:
                    logger.error("Verification failed: %s", e)
                    return "BLOCKED"
        """
        )
        violations = scan_file(f)
        assert len(violations) == 0

    def test_clean_file(self, tmp_py):
        """Clean file produces no violations."""
        f = tmp_py(
            """
            def verify_agent(agent_id):
                if not agent_id:
                    raise ValueError("Missing agent_id")
                return True
        """
        )
        violations = scan_file(f)
        assert len(violations) == 0


class TestLintRunsOnProject:
    """Integration test: lint passes on the actual CARE Platform codebase."""

    def test_all_trust_files_pass(self):
        """All trust layer files pass the fail-closed check."""
        from scripts.lint_fail_closed import EXEMPT_FILES, SCAN_DIRS

        root = Path(__file__).parent.parent.parent
        violations = []
        for scan_dir in SCAN_DIRS:
            dir_path = root / scan_dir
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                if py_file.name in EXEMPT_FILES or py_file.name == "__init__.py":
                    continue
                violations.extend(scan_file(py_file))

        assert violations == [], f"Fail-closed violations found: {violations}"
