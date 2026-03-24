# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""SupervisorOrchestrator -- end-to-end governed execution pipeline.

The orchestrator is the top-level entry point for executing a request
through the full PACT governance + GovernedSupervisor pipeline.  It
wires together:

1. **GovernanceEngine** -- resolves envelope, verifies actions
2. **PlatformEnvelopeAdapter** -- converts envelopes to supervisor params
3. **GovernedSupervisor** -- plans and executes the objective
4. **GovernedDelegate** -- per-node governance enforcement callback
5. **ApprovalBridge** -- HELD verdict persistence
6. **EventBridge** -- real-time event streaming
7. **DataFlow** -- Run record persistence

Flow::

    execute_request(request_id, role_address, objective, context)
    -> resolve governance envelope for the agent
    -> adapt envelope to GovernedSupervisor params
    -> create GovernedSupervisor with adapted params
    -> create GovernedDelegate with governance engine
    -> run supervisor with delegate as execute_node callback
    -> record Run in DataFlow
    -> bridge events to platform EventBus
    -> return results
"""

from __future__ import annotations

import logging
import math
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pact_platform.engine.approval_bridge import ApprovalBridge
from pact_platform.engine.delegate import GovernedDelegate
from pact_platform.engine.envelope_adapter import PlatformEnvelopeAdapter
from pact_platform.engine.event_bridge import EventBridge
from pact_platform.models import validate_finite

if TYPE_CHECKING:
    from dataflow import DataFlow
    from pact.governance.engine import GovernanceEngine
    from pact_platform.use.api.events import EventBus

logger = logging.getLogger(__name__)

__all__ = ["SupervisorOrchestrator"]


class SupervisorOrchestrator:
    """Orchestrates GovernedSupervisor execution with full governance wiring.

    Args:
        governance_engine: The GovernanceEngine for envelope resolution
            and action verification.
        db: DataFlow instance for persistence (Run records, decisions).
        event_bus: Optional platform EventBus for real-time streaming.
            When ``None``, events are silently discarded.
        llm_model: The LLM model identifier for GovernedSupervisor.
            Defaults to ``PACT_LLM_MODEL`` env var, then
            ``"claude-sonnet-4-6"``.
    """

    def __init__(
        self,
        governance_engine: GovernanceEngine,
        db: DataFlow,
        event_bus: EventBus | None = None,
        llm_model: str | None = None,
    ) -> None:
        self._engine = governance_engine
        self._db = db
        self._adapter = PlatformEnvelopeAdapter(governance_engine)
        self._approval_bridge = ApprovalBridge(db)
        self._event_bridge = EventBridge(event_bus)
        self._llm_model = llm_model or os.getenv("PACT_LLM_MODEL", "claude-sonnet-4-6")

    @property
    def approval_bridge(self) -> ApprovalBridge:
        """Expose the approval bridge for external resolution (approve/reject)."""
        return self._approval_bridge

    @property
    def event_bridge(self) -> EventBridge:
        """Expose the event bridge for external event subscription."""
        return self._event_bridge

    def execute_request(
        self,
        request_id: str,
        role_address: str,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a request through the governed supervisor pipeline.

        Steps:
        1. Resolve governance envelope for the role.
        2. Adapt envelope to GovernedSupervisor parameters.
        3. Create GovernedSupervisor with adapted parameters.
        4. Create GovernedDelegate with governance engine.
        5. Run supervisor with delegate as execute_node callback.
        6. Record Run in DataFlow.
        7. Bridge events to platform EventBus.
        8. Return results.

        Args:
            request_id: The platform AgenticRequest ID being executed.
            role_address: The D/T/R address of the agent executing.
            objective: The natural-language objective for the supervisor.
            context: Optional execution context dict (forwarded to the
                supervisor and delegate).

        Returns:
            Dict with keys:
            - ``"success"`` (bool): Whether execution completed.
            - ``"request_id"`` (str): Echo of the input request ID.
            - ``"run_id"`` (str): The generated Run record ID.
            - ``"results"`` (dict): Node results from the supervisor.
            - ``"budget_consumed"`` (float): Total USD consumed.
            - ``"budget_allocated"`` (float): Total USD allocated.
            - ``"audit_trail"`` (list): EATP audit records.
            - ``"error"`` (str | None): Error message if failed.

        Raises:
            ValueError: If request_id or role_address is empty, or if
                any context cost value is NaN/Inf.
        """
        if not request_id:
            raise ValueError("request_id must not be empty")
        if not role_address:
            raise ValueError("role_address must not be empty")

        ctx = context or {}
        run_id = f"run-{uuid4().hex[:12]}"
        started_at = datetime.now(UTC)

        # NaN-guard any cost values in the incoming context
        for cost_key in ("cost", "daily_total", "transaction_amount"):
            val = ctx.get(cost_key)
            if val is not None and isinstance(val, (int, float)):
                validate_finite(**{cost_key: val})

        logger.info(
            "Orchestrator: starting execution for request='%s' " "role='%s' objective='%.80s...'",
            request_id,
            role_address,
            objective,
        )

        # Step 1+2: Resolve and adapt envelope
        try:
            supervisor_params = self._adapter.adapt(
                envelope=None,  # Force resolution from engine
                role_address=role_address,
            )
        except Exception as exc:
            logger.error(
                "Orchestrator: envelope resolution failed for role='%s': %s",
                role_address,
                exc,
            )
            self._record_run(
                run_id=run_id,
                request_id=request_id,
                role_address=role_address,
                status="failed",
                started_at=started_at,
                error_message=f"Envelope resolution failed: {exc}",
            )
            # H4 fix: generic error message to caller, full detail logged server-side
            return {
                "success": False,
                "request_id": request_id,
                "run_id": run_id,
                "results": {},
                "budget_consumed": 0.0,
                "budget_allocated": 0.0,
                "audit_trail": [],
                "error": "Envelope resolution failed",
            }

        # Step 3: Create GovernedSupervisor
        try:
            from kaizen_agents import GovernedSupervisor

            supervisor = GovernedSupervisor(
                model=self._llm_model,
                budget_usd=supervisor_params["budget_usd"],
                tools=supervisor_params["tools"] or None,
                data_clearance=supervisor_params["data_clearance"],
                timeout_seconds=supervisor_params["timeout_seconds"],
                max_children=supervisor_params["max_children"],
                max_depth=supervisor_params["max_depth"],
                policy_source=f"pact-governance:{role_address}",
            )
        except Exception as exc:
            logger.error("Orchestrator: supervisor creation failed: %s", exc)
            self._record_run(
                run_id=run_id,
                request_id=request_id,
                role_address=role_address,
                status="failed",
                started_at=started_at,
                error_message=f"Supervisor creation failed: {exc}",
            )
            # H4 fix: generic error message to caller
            return {
                "success": False,
                "request_id": request_id,
                "run_id": run_id,
                "results": {},
                "budget_consumed": 0.0,
                "budget_allocated": supervisor_params["budget_usd"],
                "audit_trail": [],
                "error": "Supervisor creation failed",
            }

        # Step 4: Create GovernedDelegate
        delegate = GovernedDelegate(
            governance_engine=self._engine,
            approval_bridge=self._approval_bridge,
            role_address=role_address,
        )

        # Step 5: Run the supervisor
        supervisor_context = {
            "request_id": request_id,
            "role_address": role_address,
            "run_id": run_id,
            **ctx,
        }

        try:
            result = supervisor.run(
                objective=objective,
                context=supervisor_context,
                execute_node=delegate,
            )
        except Exception as exc:
            logger.error(
                "Orchestrator: supervisor execution failed for " "request='%s': %s",
                request_id,
                exc,
            )
            self._record_run(
                run_id=run_id,
                request_id=request_id,
                role_address=role_address,
                status="failed",
                started_at=started_at,
                error_message=f"Supervisor execution failed: {exc}",
            )
            # Emit completion event (failure)
            self._event_bridge.on_completion_event(
                request_id=request_id,
                success=False,
                budget_consumed=0.0,
                budget_allocated=supervisor_params["budget_usd"],
            )
            # H4 fix: generic error message to caller
            return {
                "success": False,
                "request_id": request_id,
                "run_id": run_id,
                "results": {},
                "budget_consumed": 0.0,
                "budget_allocated": supervisor_params["budget_usd"],
                "audit_trail": [],
                "error": "Supervisor execution failed",
            }

        # Step 6: Record Run in DataFlow
        ended_at = datetime.now(UTC)
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        # NaN-guard the budget values from the supervisor result
        budget_consumed = result.budget_consumed
        budget_allocated = result.budget_allocated
        if not math.isfinite(budget_consumed):
            logger.error(
                "Orchestrator: budget_consumed is non-finite (%r) -- " "recording as 0.0",
                budget_consumed,
            )
            budget_consumed = 0.0
        if not math.isfinite(budget_allocated):
            logger.error(
                "Orchestrator: budget_allocated is non-finite (%r) -- " "recording as 0.0",
                budget_allocated,
            )
            budget_allocated = 0.0

        self._record_run(
            run_id=run_id,
            request_id=request_id,
            role_address=role_address,
            status="completed" if result.success else "failed",
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            cost_usd=budget_consumed,
            verification_level="auto_approved",
            metadata={
                "model": self._llm_model,
                "budget_allocated": budget_allocated,
                "node_count": len(result.results),
                "modifications": len(result.modifications),
            },
        )

        # Step 7: Bridge completion event
        self._event_bridge.on_completion_event(
            request_id=request_id,
            success=result.success,
            budget_consumed=budget_consumed,
            budget_allocated=budget_allocated,
        )

        logger.info(
            "Orchestrator: completed request='%s' success=%s " "budget=$%.4f/$%.4f duration=%dms",
            request_id,
            result.success,
            budget_consumed,
            budget_allocated,
            duration_ms,
        )

        return {
            "success": result.success,
            "request_id": request_id,
            "run_id": run_id,
            "results": result.results,
            "budget_consumed": budget_consumed,
            "budget_allocated": budget_allocated,
            "audit_trail": result.audit_trail,
            "error": None if result.success else "Supervisor reported failure",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_run(
        self,
        run_id: str,
        request_id: str,
        role_address: str,
        status: str,
        started_at: datetime,
        ended_at: datetime | None = None,
        duration_ms: int = 0,
        cost_usd: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        verification_level: str = "auto_approved",
        error_message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a Run record in DataFlow.

        All numeric fields are NaN-guarded before persistence.
        """
        # NaN-guard all numerics
        if not math.isfinite(cost_usd):
            cost_usd = 0.0
        if not math.isfinite(float(duration_ms)):
            duration_ms = 0

        now_iso = datetime.now(UTC).isoformat()
        ended_iso = ended_at.isoformat() if ended_at else ""

        try:
            wf = self._db.create_workflow("record_run")
            self._db.add_node(
                wf,
                "Run",
                "Create",
                "create_run",
                {
                    "id": run_id,
                    "request_id": request_id,
                    "agent_address": role_address,
                    "run_type": "llm",
                    "status": status,
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_iso,
                    "duration_ms": duration_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost_usd,
                    "verification_level": verification_level,
                    "error_message": error_message,
                    "metadata": metadata or {},
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
            )
            self._db.execute_workflow(wf)
        except Exception:
            logger.exception(
                "Orchestrator: failed to record Run '%s' -- " "run data may be lost",
                run_id,
            )
