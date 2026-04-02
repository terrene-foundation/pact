# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Session completion and review lifecycle service.

Manages the tail end of work: recording artifacts, submitting them for
review, capturing findings, and finalizing review verdicts.  All state
is persisted through DataFlow Express.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from dataflow import DataFlow

logger = logging.getLogger(__name__)

__all__ = ["CompletionWorkflowService"]

_VALID_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})
_VALID_REVIEW_VERDICTS = frozenset({"pending", "approved", "revision_required", "rejected"})


class CompletionWorkflowService:
    """Manages the session-completion and artifact-review lifecycle.

    Args:
        db: DataFlow instance for persistence.
    """

    def __init__(self, db: DataFlow) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Session completion
    # ------------------------------------------------------------------

    def complete_session(
        self,
        session_id: str,
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Mark a session as completed and persist its artifacts.

        Each entry in *artifacts* should contain at minimum ``title`` and
        ``content_ref`` (a path or URI).  Additional optional keys:
        ``artifact_type``, ``content_hash``, ``created_by``.

        Args:
            session_id: The ``AgenticWorkSession.id`` to complete.
            artifacts: List of artifact dicts to persist.

        Returns:
            Dict with ``session_id``, ``status``, and ``artifact_ids``.

        Raises:
            ValueError: If *session_id* is empty.
        """
        if not session_id:
            raise ValueError("session_id must not be empty")

        now_iso = datetime.now(UTC).isoformat()

        # Read session to get request_id
        session_record = self._db.express_sync.read("AgenticWorkSession", session_id)
        request_id = session_record.get("request_id", "")

        # Mark session completed
        self._db.express_sync.update(
            "AgenticWorkSession",
            session_id,
            {"status": "completed", "ended_at": now_iso},
        )

        # Create artifacts
        artifact_ids: list[str] = []
        for art in artifacts:
            artifact_id = f"art-{uuid4().hex[:12]}"
            self._db.express_sync.create(
                "AgenticArtifact",
                {
                    "id": artifact_id,
                    "request_id": request_id,
                    "session_id": session_id,
                    "artifact_type": art.get("artifact_type", "document"),
                    "title": art.get("title", ""),
                    "content_ref": art.get("content_ref", ""),
                    "content_hash": art.get("content_hash", ""),
                    "created_by": art.get("created_by", ""),
                    "status": "draft",
                },
            )
            artifact_ids.append(artifact_id)

        logger.info(
            "Session %s completed with %d artifact(s)",
            session_id,
            len(artifact_ids),
        )
        return {
            "session_id": session_id,
            "status": "completed",
            "artifact_ids": artifact_ids,
        }

    # ------------------------------------------------------------------
    # Review submission
    # ------------------------------------------------------------------

    def submit_for_review(
        self,
        request_id: str,
        artifact_id: str,
        reviewer_address: str,
        review_type: str = "quality",
    ) -> str:
        """Create a review decision for an artifact.

        Args:
            request_id: The owning request.
            artifact_id: The artifact to review.
            reviewer_address: D/T/R address of the reviewer.
            review_type: ``quality``, ``security``, ``compliance``, or ``peer``.

        Returns:
            The new ``AgenticReviewDecision.id``.

        Raises:
            ValueError: On empty required fields.
        """
        if not request_id:
            raise ValueError("request_id must not be empty")
        if not artifact_id:
            raise ValueError("artifact_id must not be empty")
        if not reviewer_address:
            raise ValueError("reviewer_address must not be empty")

        review_id = f"rev-{uuid4().hex[:12]}"

        self._db.express_sync.create(
            "AgenticReviewDecision",
            {
                "id": review_id,
                "request_id": request_id,
                "artifact_id": artifact_id,
                "reviewer_address": reviewer_address,
                "review_type": review_type,
                "verdict": "pending",
                "findings_count": 0,
                "comments": "",
            },
        )

        # Mark the artifact as submitted for review
        self._db.express_sync.update("AgenticArtifact", artifact_id, {"status": "submitted"})

        logger.info(
            "Review %s created for artifact %s (type=%s, reviewer=%s)",
            review_id,
            artifact_id,
            review_type,
            reviewer_address,
        )
        return review_id

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def record_finding(
        self,
        review_id: str,
        request_id: str,
        severity: str,
        category: str,
        title: str,
        description: str,
        remediation: str = "",
    ) -> str:
        """Record a finding discovered during review.

        Args:
            review_id: The review this finding belongs to.
            request_id: The owning request (for cross-referencing).
            severity: ``info``, ``low``, ``medium``, ``high``, or ``critical``.
            category: Free-form category tag (e.g. ``"security"``, ``"style"``).
            title: Short summary of the finding.
            description: Full description.
            remediation: Suggested fix (may be empty).

        Returns:
            The new ``AgenticFinding.id``.

        Raises:
            ValueError: On invalid severity or empty required fields.
        """
        if not review_id:
            raise ValueError("review_id must not be empty")
        if not title:
            raise ValueError("title must not be empty")
        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"severity must be one of {sorted(_VALID_SEVERITIES)}, got {severity!r}"
            )

        finding_id = f"fnd-{uuid4().hex[:12]}"

        self._db.express_sync.create(
            "AgenticFinding",
            {
                "id": finding_id,
                "review_id": review_id,
                "request_id": request_id,
                "severity": severity,
                "category": category,
                "title": title,
                "description": description,
                "remediation": remediation,
                "status": "open",
            },
        )

        # Increment findings_count on the review
        review_record = self._db.express_sync.read("AgenticReviewDecision", review_id)
        current_count = review_record.get("findings_count", 0)
        self._db.express_sync.update(
            "AgenticReviewDecision",
            review_id,
            {"findings_count": current_count + 1},
        )

        logger.info(
            "Finding %s recorded on review %s (severity=%s)",
            finding_id,
            review_id,
            severity,
        )
        return finding_id

    # ------------------------------------------------------------------
    # Finalize review
    # ------------------------------------------------------------------

    def finalize_review(
        self,
        review_id: str,
        verdict: str,
        comments: str = "",
    ) -> dict[str, Any]:
        """Set the final verdict on a review.

        Args:
            review_id: The review to finalize.
            verdict: ``approved``, ``revision_required``, or ``rejected``.
            comments: Optional reviewer comments.

        Returns:
            Dict with the updated review fields.

        Raises:
            ValueError: On invalid verdict or if the review is not found.
        """
        if not review_id:
            raise ValueError("review_id must not be empty")
        if verdict not in _VALID_REVIEW_VERDICTS:
            raise ValueError(
                f"verdict must be one of {sorted(_VALID_REVIEW_VERDICTS)}, got {verdict!r}"
            )

        # Read current state
        record = self._db.express_sync.read("AgenticReviewDecision", review_id)

        if not record:
            raise ValueError(f"Review '{review_id}' not found")

        now_iso = datetime.now(UTC).isoformat()
        self._db.express_sync.update(
            "AgenticReviewDecision",
            review_id,
            {"verdict": verdict, "comments": comments},
        )

        # If verdict is approved, update the artifact status too
        artifact_id = record.get("artifact_id", "")
        if verdict == "approved" and artifact_id:
            self._db.express_sync.update("AgenticArtifact", artifact_id, {"status": "approved"})
        elif verdict == "rejected" and artifact_id:
            self._db.express_sync.update("AgenticArtifact", artifact_id, {"status": "rejected"})

        logger.info(
            "Review %s finalized: verdict=%s",
            review_id,
            verdict,
        )
        return {
            "review_id": review_id,
            "verdict": verdict,
            "comments": comments,
            "artifact_id": artifact_id,
            "finalized_at": now_iso,
        }
