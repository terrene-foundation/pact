# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Cost tracking service -- DataFlow-backed LLM spend aggregation.

Records per-run costs and provides aggregation queries at the objective
and agent level.  All float inputs are NaN-guarded before persistence
per ``rules/trust-plane-security.md`` Rule 3.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pact_platform.models import safe_sum_finite, validate_finite

if TYPE_CHECKING:
    from dataflow import DataFlow

logger = logging.getLogger(__name__)

__all__ = ["CostTrackingService"]


class CostTrackingService:
    """Aggregates LLM execution costs through DataFlow persistence.

    Args:
        db: DataFlow instance.
    """

    def __init__(self, db: DataFlow) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record_run_cost(
        self,
        run_id: str,
        session_id: str,
        request_id: str,
        agent_address: str,
        cost_usd: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        provider: str = "",
        model_name: str = "",
    ) -> dict[str, Any]:
        """Persist a ``Run`` record with cost data.

        Args:
            run_id: Unique run identifier (caller-generated or auto).
            session_id: Parent work session.
            request_id: Parent request.
            agent_address: D/T/R address of the executing agent.
            cost_usd: Cost in USD for this run.
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens produced.
            provider: LLM provider name (e.g. ``"anthropic"``).
            model_name: Model identifier (e.g. ``"claude-opus-4-6"``).

        Returns:
            Dict with the persisted run fields.

        Raises:
            ValueError: If *cost_usd* is NaN or Inf, or required IDs are
                empty.
        """
        if not run_id:
            run_id = f"run-{uuid4().hex[:12]}"
        if not agent_address:
            raise ValueError("agent_address must not be empty")

        # NaN/Inf guard -- per rules/trust-plane-security.md Rule 3
        validate_finite(cost_usd=cost_usd)

        now_iso = datetime.now(UTC).isoformat()

        wf = self._db.create_workflow("record_run_cost")
        self._db.add_node(
            wf,
            "Run",
            "Create",
            "create_run",
            {
                "id": run_id,
                "session_id": session_id,
                "request_id": request_id,
                "agent_address": agent_address,
                "run_type": "llm",
                "status": "completed",
                "started_at": now_iso,
                "ended_at": now_iso,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "verification_level": "auto_approved",
                "metadata": {"provider": provider, "model_name": model_name},
            },
        )
        self._db.execute_workflow(wf)

        logger.info(
            "Run cost recorded: run_id=%s agent=%s cost=$%.6f tokens=%d/%d",
            run_id,
            agent_address,
            cost_usd,
            input_tokens,
            output_tokens,
        )
        return {
            "run_id": run_id,
            "session_id": session_id,
            "request_id": request_id,
            "agent_address": agent_address,
            "cost_usd": cost_usd,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "provider": provider,
            "model_name": model_name,
        }

    # ------------------------------------------------------------------
    # Aggregation -- objective level
    # ------------------------------------------------------------------

    def get_objective_cost(self, objective_id: str) -> dict[str, Any]:
        """Aggregate cost across all requests/sessions/runs for an objective.

        Walks the chain: Objective -> Requests -> Sessions -> Runs and sums
        ``cost_usd``, ``input_tokens``, ``output_tokens``.

        Args:
            objective_id: The ``AgenticObjective.id``.

        Returns:
            Dict with ``objective_id``, ``total_cost_usd``,
            ``total_input_tokens``, ``total_output_tokens``, ``run_count``.
        """
        if not objective_id:
            raise ValueError("objective_id must not be empty")

        # Get all requests for this objective
        wf_req = self._db.create_workflow("list_requests")
        self._db.add_node(
            wf_req,
            "AgenticRequest",
            "List",
            "requests",
            {"filter": {"objective_id": objective_id}, "limit": 10000},
        )
        req_results, _ = self._db.execute_workflow(wf_req)
        requests = req_results.get("requests", {}).get("records", [])
        request_ids = [r["id"] for r in requests]

        if not request_ids:
            return {
                "objective_id": objective_id,
                "total_cost_usd": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "run_count": 0,
            }

        # Aggregate runs across all request_ids
        all_costs: list[float] = []
        all_input: list[int] = []
        all_output: list[int] = []
        run_count = 0

        for req_id in request_ids:
            wf_runs = self._db.create_workflow("list_runs")
            self._db.add_node(
                wf_runs,
                "Run",
                "List",
                "runs",
                {"filter": {"request_id": req_id}, "limit": 10000},
            )
            run_results, _ = self._db.execute_workflow(wf_runs)
            runs = run_results.get("runs", {}).get("records", [])

            for run in runs:
                all_costs.append(run.get("cost_usd", 0.0))
                all_input.append(run.get("input_tokens", 0))
                all_output.append(run.get("output_tokens", 0))
                run_count += 1

        # C3/M3 fix: NaN-safe summation -- corrupted DB values don't poison totals
        total_cost = safe_sum_finite(all_costs)
        total_input = int(safe_sum_finite(all_input))
        total_output = int(safe_sum_finite(all_output))

        return {
            "objective_id": objective_id,
            "total_cost_usd": round(total_cost, 6),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "run_count": run_count,
        }

    # ------------------------------------------------------------------
    # Aggregation -- agent level
    # ------------------------------------------------------------------

    def get_agent_cost(self, agent_address: str) -> dict[str, Any]:
        """Total cost across all runs for a specific agent.

        Args:
            agent_address: D/T/R address of the agent.

        Returns:
            Dict with ``agent_address``, ``total_cost_usd``,
            ``total_input_tokens``, ``total_output_tokens``, ``run_count``.
        """
        if not agent_address:
            raise ValueError("agent_address must not be empty")

        wf = self._db.create_workflow("list_agent_runs")
        self._db.add_node(
            wf,
            "Run",
            "List",
            "runs",
            {"filter": {"agent_address": agent_address}, "limit": 10000},
        )
        results, _ = self._db.execute_workflow(wf)
        runs = results.get("runs", {}).get("records", [])

        # C3/M3 fix: NaN-safe summation
        total_cost = safe_sum_finite([run.get("cost_usd", 0.0) for run in runs])
        total_input = int(safe_sum_finite([run.get("input_tokens", 0) for run in runs]))
        total_output = int(safe_sum_finite([run.get("output_tokens", 0) for run in runs]))

        return {
            "agent_address": agent_address,
            "total_cost_usd": round(total_cost, 6),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "run_count": len(runs),
        }

    # ------------------------------------------------------------------
    # Budget check
    # ------------------------------------------------------------------

    def check_budget(self, objective_id: str) -> dict[str, Any]:
        """Compare actual spend against the objective's ``budget_usd``.

        Args:
            objective_id: The ``AgenticObjective.id``.

        Returns:
            Dict with ``objective_id``, ``budget_usd``, ``spent_usd``,
            ``remaining_usd``, ``utilization_pct``, and ``over_budget``.
        """
        if not objective_id:
            raise ValueError("objective_id must not be empty")

        # Read the objective to get budget_usd
        wf_obj = self._db.create_workflow("read_objective")
        self._db.add_node(
            wf_obj,
            "AgenticObjective",
            "Read",
            "read",
            {"id": objective_id},
        )
        obj_results, _ = self._db.execute_workflow(wf_obj)
        obj_record = obj_results.get("read", {})

        budget_usd = float(obj_record.get("budget_usd", 0.0))

        # M3 fix: NaN-guard budget_usd read from database
        if not math.isfinite(budget_usd):
            logger.error(
                "Budget for objective '%s' is non-finite (%r) -- treating as 0.0",
                objective_id,
                budget_usd,
            )
            budget_usd = 0.0

        # Get actual spend
        cost_data = self.get_objective_cost(objective_id)
        spent_usd = cost_data["total_cost_usd"]

        remaining = budget_usd - spent_usd
        utilization = (spent_usd / budget_usd * 100.0) if budget_usd > 0 else 0.0

        return {
            "objective_id": objective_id,
            "budget_usd": budget_usd,
            "spent_usd": round(spent_usd, 6),
            "remaining_usd": round(remaining, 6),
            "utilization_pct": round(utilization, 2),
            "over_budget": spent_usd > budget_usd,
        }
