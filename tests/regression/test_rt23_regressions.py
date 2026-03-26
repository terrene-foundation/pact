# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Regression tests for RT23 red team findings.

These tests guard against the specific vulnerabilities identified in RT23:
- F4: RequestRouterService must block without a governance engine (fail-closed)
- F2: API error responses must not leak exception details to clients
- F6: Checkpoint verification must use hmac.compare_digest (timing-safe)

Regression tests are PERMANENT — they must never be deleted.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pact.governance import GovernanceVerdict
from pact_platform.use.services.request_router import RequestRouterService

# Resolve source root for inspection tests
_SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _WorkflowStub:
    """Lightweight stand-in for DataFlow workflow object."""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self.nodes: list = []


class _MockDataFlow:
    """Minimal DataFlow mock for regression tests."""

    def create_workflow(self, name: str = "") -> _WorkflowStub:
        return _WorkflowStub(name)

    def add_node(self, wf, model, operation, node_id, params) -> None:
        wf.nodes.append((model, operation, node_id, params))

    def execute_workflow(self, wf) -> tuple[dict, str]:
        return ({}, "run-test")


# ---------------------------------------------------------------------------
# F4: RequestRouterService blocks without governance engine (fail-closed)
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_rt23_f4_request_router_blocks_without_engine() -> None:
    """Regression: RT23-F4 — RequestRouterService must fail-closed when no
    governance engine is configured.

    The bug: without a governance engine, requests could potentially be routed
    without any governance check.  The fix ensures that a missing engine always
    returns status='blocked' with a clear reason.

    Fixed in: v0.3.0 initial implementation (fail-closed by design).
    """
    db = _MockDataFlow()
    service = RequestRouterService(db=db, governance_engine=None)

    result = service.route_request(
        request_id="rt23-f4-001",
        org_address="D1-R1",
        action="write",
    )

    # MUST be blocked — never approved, never held
    assert (
        result["status"] == "blocked"
    ), f"Expected status='blocked' when no governance engine is set, got '{result['status']}'"
    assert (
        "fail-closed" in result["reason"].lower()
    ), f"Expected 'fail-closed' in reason, got: {result['reason']}"
    # Must include the request_id for traceability
    assert result["request_id"] == "rt23-f4-001"


@pytest.mark.regression
def test_rt23_f4_engine_exception_also_blocks() -> None:
    """Regression: RT23-F4 extension — engine exceptions must also fail-closed.

    If the governance engine raises any exception, the service must return
    blocked, not propagate the exception or return an approved status.
    """
    db = _MockDataFlow()
    engine = MagicMock()
    engine.verify_action.side_effect = RuntimeError("Simulated engine failure")

    service = RequestRouterService(db=db, governance_engine=engine)

    result = service.route_request(
        request_id="rt23-f4-002",
        org_address="D1-R1",
        action="write",
    )

    assert (
        result["status"] == "blocked"
    ), f"Expected status='blocked' on engine exception, got '{result['status']}'"


# ---------------------------------------------------------------------------
# F2: API error responses must not leak exception details
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_rt23_f2_api_errors_do_not_leak_exceptions() -> None:
    """Regression: RT23-F2 — API router error handlers must not return raw
    exception messages to clients.

    The bug: error handlers using ``str(exc)`` or ``str(e)`` expose internal
    stack traces and implementation details to API consumers.

    This is a source inspection test — it checks that the requests router
    does not contain patterns that would leak exception details in HTTP
    responses.
    """
    requests_router_path = _SRC_ROOT / "pact_platform" / "use" / "api" / "routers" / "requests.py"
    assert requests_router_path.exists(), f"requests.py router not found at {requests_router_path}"

    source = requests_router_path.read_text()
    tree = ast.parse(source, filename=str(requests_router_path))

    # Walk the AST looking for exception handlers that use str(exc) or str(e)
    # in return statements or HTTPException detail arguments
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        exc_name = node.name  # the 'as exc' or 'as e' binding
        if exc_name is None:
            continue

        # Search within this handler for str(exc_name) patterns
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Check for str(exc) / str(e)
                if (
                    isinstance(child.func, ast.Name)
                    and child.func.id == "str"
                    and len(child.args) == 1
                    and isinstance(child.args[0], ast.Name)
                    and child.args[0].id == exc_name
                ):
                    violations.append(
                        f"Line {child.lineno}: str({exc_name}) found in exception handler "
                        f"— may leak internal details to API response"
                    )

            # Also check for f-string references to the exception variable
            # in return contexts
            if isinstance(child, ast.JoinedStr):
                for value in child.values:
                    if (
                        isinstance(value, ast.FormattedValue)
                        and isinstance(value.value, ast.Name)
                        and value.value.id == exc_name
                    ):
                        violations.append(
                            f"Line {child.lineno}: f-string referencing {exc_name} "
                            f"found — may leak internal details"
                        )

    assert (
        len(violations) == 0
    ), f"RT23-F2 VIOLATION: API error responses may leak exception details:\n" + "\n".join(
        f"  - {v}" for v in violations
    )


# ---------------------------------------------------------------------------
# F6: Checkpoint verification uses hmac.compare_digest (timing-safe)
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_rt23_f6_checkpoint_uses_compare_digest() -> None:
    """Regression: RT23-F6 — AuditChain.verify_against_checkpoint() must use
    hmac.compare_digest for hash comparison, not bare ``==``.

    The bug: using ``==`` for hash comparison leaks timing information that
    enables byte-by-byte hash forgery attacks.

    This is a source inspection test — it verifies that anchor.py uses
    hmac.compare_digest in the checkpoint verification method.
    """
    anchor_path = _SRC_ROOT / "pact_platform" / "trust" / "audit" / "anchor.py"
    assert anchor_path.exists(), f"anchor.py not found at {anchor_path}"

    source = anchor_path.read_text()
    tree = ast.parse(source, filename=str(anchor_path))

    # Find the verify_against_checkpoint method
    found_method = False
    uses_compare_digest = False
    uses_bare_eq_on_hash = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "verify_against_checkpoint":
            found_method = True

            # Walk the method body looking for hmac.compare_digest calls
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    # Check for hmac.compare_digest(...)
                    if isinstance(child.func, ast.Attribute):
                        if child.func.attr == "compare_digest":
                            uses_compare_digest = True

                # Check for bare == comparisons on hash-like variables
                if isinstance(child, ast.Compare):
                    for op in child.ops:
                        if isinstance(op, (ast.Eq, ast.NotEq)):
                            # Check if either side references 'hash' variables
                            comparands = [child.left] + child.comparators
                            for comp in comparands:
                                if isinstance(comp, ast.Attribute) and "hash" in comp.attr.lower():
                                    uses_bare_eq_on_hash = True
                                elif isinstance(comp, ast.Name) and "hash" in comp.id.lower():
                                    uses_bare_eq_on_hash = True

            break

    assert found_method, "verify_against_checkpoint method not found in anchor.py"
    assert uses_compare_digest, (
        "RT23-F6 VIOLATION: verify_against_checkpoint does not use "
        "hmac.compare_digest — timing-safe comparison required for hash verification"
    )
    # This assertion catches regressions where someone adds a bare == alongside compare_digest
    assert not uses_bare_eq_on_hash, (
        "RT23-F6 VIOLATION: verify_against_checkpoint uses bare == on hash fields — "
        "this leaks timing information and must use hmac.compare_digest instead"
    )


@pytest.mark.regression
def test_rt23_f6_verify_integrity_uses_compare_digest() -> None:
    """Regression: RT23-F6 extension — AuditAnchor.verify_integrity() must
    also use hmac.compare_digest for its content_hash comparison.
    """
    anchor_path = _SRC_ROOT / "pact_platform" / "trust" / "audit" / "anchor.py"
    source = anchor_path.read_text()
    tree = ast.parse(source, filename=str(anchor_path))

    found_method = False
    uses_compare_digest = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "verify_integrity":
            found_method = True
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if child.func.attr == "compare_digest":
                        uses_compare_digest = True
            break

    assert found_method, "verify_integrity method not found in anchor.py"
    assert (
        uses_compare_digest
    ), "RT23-F6 VIOLATION: verify_integrity does not use hmac.compare_digest"
