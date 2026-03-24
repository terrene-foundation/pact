# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Work management DataFlow models.

Provides 11 models generating 121 auto-nodes for objectives, requests,
sessions, artifacts, decisions, reviews, findings, pools, runs, and metrics.

Usage:
    from pact_platform.models import db
    # All nodes registered: AgenticObjectiveCreateNode, etc.
"""

import math
import os
from datetime import datetime
from typing import Optional

from dataflow import DataFlow

__all__ = [
    "db",
    "validate_finite",
    "safe_sum_finite",
    "validate_string_length",
    "MAX_SHORT_STRING",
    "MAX_LONG_STRING",
    "MAX_POOL_MEMBERS",
    "MAX_CONCURRENT_UPPER",
    "AgenticObjective",
    "AgenticRequest",
    "AgenticWorkSession",
    "AgenticArtifact",
    "AgenticDecision",
    "AgenticReviewDecision",
    "AgenticFinding",
    "AgenticPool",
    "AgenticPoolMembership",
    "Run",
    "ExecutionMetric",
]

# ---------------------------------------------------------------------------
# DataFlow initialization
# ---------------------------------------------------------------------------


# Four slashes (sqlite:////abs/path) produce a proper absolute path.
# In Docker the WORKDIR is /app; outside Docker use CWD-relative.
_DEFAULT_DB = (
    "sqlite:////app/pact_platform.db" if os.path.isdir("/app") else "sqlite:///pact_platform.db"
)
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DB)

db = DataFlow(
    database_url=DATABASE_URL,
    auto_migrate=True,
    pool_recycle=3600,
    cache_enabled=False,
)


# ---------------------------------------------------------------------------
# NaN/Inf guard -- per rules/trust-plane-security.md Rule 3
# ---------------------------------------------------------------------------


def validate_finite(**fields: float | int | None) -> None:
    """Validate that all numeric fields are finite (not NaN or Inf).

    Raises ValueError if any field is NaN or Inf.
    """
    for name, value in fields.items():
        if value is not None and isinstance(value, (int, float)):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite, got {value!r}")


def safe_sum_finite(values: list[float | int | None], default: float = 0.0) -> float:
    """Sum numeric values, skipping None and non-finite entries.

    NaN and Inf values read back from the database are silently dropped
    rather than poisoning the accumulator.  This is the read-back
    counterpart to ``validate_finite()`` which guards writes.

    Args:
        values: List of numeric values (may contain None).
        default: Value returned when no finite values are found.

    Returns:
        Sum of all finite values, or *default* if none are finite.
    """
    total = 0.0
    has_finite = False
    for v in values:
        if v is not None:
            fv = float(v)
            if math.isfinite(fv):
                total += fv
                has_finite = True
    return total if has_finite else default


# ---------------------------------------------------------------------------
# Input validation helpers -- per rules/security.md Rule 3
# ---------------------------------------------------------------------------

MAX_SHORT_STRING: int = 500
"""Maximum length for short string fields (titles, names, addresses)."""

MAX_LONG_STRING: int = 10_000
"""Maximum length for long string fields (descriptions, comments)."""

MAX_POOL_MEMBERS: int = 1_000
"""Maximum number of members per pool (DoS prevention)."""

MAX_CONCURRENT_UPPER: int = 1_000
"""Maximum allowed value for max_concurrent fields."""


def validate_string_length(
    value: str,
    field_name: str,
    max_length: int = MAX_SHORT_STRING,
) -> str:
    """Validate and truncate a string field to the maximum allowed length.

    Args:
        value: The input string.
        field_name: Human-readable field name for error messages.
        max_length: Maximum allowed length.

    Returns:
        The validated string.

    Raises:
        ValueError: If the string exceeds *max_length*.
    """
    if len(value) > max_length:
        raise ValueError(
            f"{field_name} exceeds maximum length of {max_length} characters " f"(got {len(value)})"
        )
    return value


# ---------------------------------------------------------------------------
# Models -- 11 models, 121 auto-generated nodes
# ---------------------------------------------------------------------------


@db.model
class AgenticObjective:
    """Top-level work unit submitted for execution."""

    id: str
    org_address: str
    title: str
    description: str = ""
    submitted_by: str = ""
    status: str = "draft"  # draft, active, completed, cancelled
    priority: str = "normal"  # low, normal, high, critical
    budget_usd: float = 0.0  # NaN-guarded at application layer
    deadline: Optional[str] = None  # ISO 8601
    parent_objective_id: Optional[str] = None
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticRequest:
    """Decomposed task from an objective."""

    id: str
    objective_id: str
    title: str
    description: str = ""
    assigned_to: Optional[str] = None  # pool_id or agent_address
    assigned_type: str = "unassigned"  # unassigned, pool, agent
    claimed_by: Optional[str] = None
    status: str = "pending"  # pending, assigned, in_progress, review, completed, failed, cancelled
    priority: str = "normal"
    sequence_order: int = 0
    depends_on: dict = {}  # {"request_ids": [...]}
    envelope_id: Optional[str] = None
    deadline: Optional[str] = None
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticWorkSession:
    """Active work period with cost tracking."""

    id: str
    request_id: str
    worker_address: str
    status: str = "active"  # active, paused, completed, failed
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0  # NaN-guarded
    provider: str = ""
    model_name: str = ""
    tool_calls: int = 0
    verification_verdicts: dict = {}  # {"verdicts": [...]}
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticArtifact:
    """Produced deliverable from a work session."""

    id: str
    request_id: str
    session_id: Optional[str] = None
    artifact_type: str = "document"  # document, code, data, report, other
    title: str = ""
    content_ref: str = ""  # path or URI
    content_hash: str = ""  # SHA-256
    version: int = 1
    parent_artifact_id: Optional[str] = None
    created_by: str = ""
    status: str = "draft"  # draft, submitted, approved, rejected
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticDecision:
    """Human judgment point -- created when governance returns HELD."""

    id: str
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_address: str = ""
    action: str = ""
    decision_type: str = "governance_hold"  # governance_hold, budget_hold, manual_review
    status: str = "pending"  # pending, approved, rejected, expired
    reason_held: str = ""
    constraint_dimension: str = ""  # financial, operational, temporal, data_access, communication
    constraint_details: dict = {}
    urgency: str = "normal"  # low, normal, high, critical
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    decision_reason: str = ""
    expires_at: Optional[str] = None
    envelope_version: int = 0  # TOCTOU defense
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticReviewDecision:
    """Review outcome for an artifact."""

    id: str
    request_id: str
    artifact_id: Optional[str] = None
    reviewer_address: str = ""
    review_type: str = "quality"  # quality, security, compliance, peer
    verdict: str = "pending"  # pending, approved, revision_required, rejected
    findings_count: int = 0
    comments: str = ""
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticFinding:
    """Issue discovered during review."""

    id: str
    review_id: str
    request_id: Optional[str] = None
    severity: str = "info"  # info, low, medium, high, critical
    category: str = ""
    title: str = ""
    description: str = ""
    remediation: str = ""
    status: str = "open"  # open, acknowledged, resolved, wontfix
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticPool:
    """Agent/human group for work assignment."""

    id: str
    org_id: str
    name: str
    description: str = ""
    pool_type: str = "agent"  # agent, human, mixed
    routing_strategy: str = "round_robin"  # round_robin, least_busy, capability_match
    max_concurrent: int = 5
    active_requests: int = 0
    status: str = "active"  # active, paused, archived
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class AgenticPoolMembership:
    """Pool member link."""

    id: str
    pool_id: str
    member_address: str
    member_type: str = "agent"  # agent, human
    capabilities: dict = {}  # {"skills": [...]}
    max_concurrent: int = 3
    active_count: int = 0
    status: str = "active"  # active, paused, removed
    joined_at: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class Run:
    """Execution record for a single agent invocation."""

    id: str
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    agent_address: str = ""
    run_type: str = "llm"  # llm, tool, workflow
    status: str = "running"  # running, completed, failed, cancelled
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0  # NaN-guarded
    verification_level: str = "auto_approved"
    error_message: str = ""
    metadata: dict = {}
    created_at: datetime = None
    updated_at: datetime = None


@db.model
class ExecutionMetric:
    """Performance metrics for dashboard reporting."""

    id: str
    run_id: Optional[str] = None
    metric_type: str = ""  # latency, cost, tokens, throughput
    agent_address: str = ""
    pool_id: Optional[str] = None
    org_id: Optional[str] = None
    value: float = 0.0  # NaN-guarded
    unit: str = ""
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    dimensions: dict = {}
    created_at: datetime = None
    updated_at: datetime = None
