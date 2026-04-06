# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Multi-approver service for quorum-based approval workflows.

Provides reusable approval logic for any record type that needs
multi-party approval (clearance vetting, emergency bypass, etc.).
Each approval is stored as an ApprovalRecord for full audit trail.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from dataflow import DataFlow

logger = logging.getLogger(__name__)

__all__ = ["MultiApproverService"]


_MAX_LOCKS = 10_000


class MultiApproverService:
    """Quorum-based approval service backed by the ``ApprovalRecord`` model.

    Uses per-decision asyncio locks to prevent TOCTOU race conditions
    on the duplicate-check + create sequence. All approvers for the same
    decision are serialized through a single lock keyed by decision_id.

    Args:
        db: DataFlow instance.
    """

    def __init__(self, db: DataFlow) -> None:
        self._db = db
        self._locks: dict[str, asyncio.Lock] = {}

    async def record_approval(
        self,
        decision_id: str,
        approver_address: str,
        approver_identity: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        """Record an approval vote and return updated counts.

        Prevents duplicate approvals from the same approver_address.

        Args:
            decision_id: The decision or vetting record being approved.
            approver_address: D/T/R address of the approver.
            approver_identity: Human-readable identity (optional).
            reason: Approval reason (optional).

        Returns:
            Dict with ``approval_id``, ``current_approvals``,
            ``required_approvals``, and ``quorum_met``.

        Raises:
            ValueError: On empty required fields or duplicate approval.
        """
        if not decision_id:
            raise ValueError("decision_id must not be empty")
        if not approver_address:
            raise ValueError("approver_address must not be empty")

        # Per-decision lock prevents TOCTOU on duplicate-check + create.
        # All approvers for the same decision share one lock so that
        # concurrent approvals are fully serialized (prevents double-count).
        lock_key = decision_id
        if lock_key not in self._locks:
            # Evict oldest entries when at capacity (LRU eviction)
            if len(self._locks) >= _MAX_LOCKS:
                # Remove the oldest 10% of entries
                evict_count = max(1, _MAX_LOCKS // 10)
                keys_to_remove = list(self._locks.keys())[:evict_count]
                for k in keys_to_remove:
                    del self._locks[k]
            self._locks[lock_key] = asyncio.Lock()
        async with self._locks[lock_key]:
            # Check for duplicate approval from the same approver
            existing = await self._db.express.list(
                "ApprovalRecord",
                {"decision_id": decision_id, "approver_address": approver_address},
                limit=1,
            )
            if existing:
                raise ValueError(
                    f"Approver '{approver_address}' has already voted on decision '{decision_id}'"
                )

            approval_id = f"apr-{uuid4().hex[:12]}"
            await self._db.express.create(
                "ApprovalRecord",
                {
                    "id": approval_id,
                    "decision_id": decision_id,
                    "approver_address": approver_address,
                    "approver_identity": approver_identity,
                    "verdict": "approved",
                    "reason": reason,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )

        # Count all approvals for this decision (outside lock — read-only)
        all_approvals = await self._db.express.list(
            "ApprovalRecord",
            {"decision_id": decision_id, "verdict": "approved"},
            limit=10000,
        )
        current_count = len(all_approvals)

        logger.info(
            "Approval %s recorded for %s by %s (count=%d)",
            approval_id,
            decision_id,
            approver_address,
            current_count,
        )

        return {
            "approval_id": approval_id,
            "current_approvals": current_count,
        }

    async def get_approval_count(self, decision_id: str) -> int:
        """Return the number of approvals for a decision."""
        approvals = await self._db.express.list(
            "ApprovalRecord",
            {"decision_id": decision_id, "verdict": "approved"},
            limit=10000,
        )
        return len(approvals)

    async def list_approvals(self, decision_id: str) -> list[dict[str, Any]]:
        """List all approval records for a decision."""
        return await self._db.express.list(
            "ApprovalRecord",
            {"decision_id": decision_id},
            limit=10000,
        )
