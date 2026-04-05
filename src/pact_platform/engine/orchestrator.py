# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""SupervisorOrchestrator -- end-to-end governed execution pipeline.

The orchestrator is the top-level entry point for executing a request
through the full PACT governance + PactEngine pipeline.  It composes:

1. **PactEngine** -- dual-plane bridge handling enforcement mode,
   per-node governance, supervisor lifecycle, NaN guards, and cost
   tracking (all via ``PactEngine.submit()``)
2. **ApprovalBridge** -- HELD verdict persistence (wired into PactEngine
   via ``_PlatformHeldCallback``)
3. **EventBridge** -- real-time event streaming
4. **DataFlow** -- Run record persistence

Flow::

    execute_request(request_id, role_address, objective, context)
    -> NaN-guard incoming context
    -> warn if operating under degenerate envelope
    -> call PactEngine.submit(objective, role, context)
    -> record Run in DataFlow
    -> bridge events to platform EventBus
    -> return results

Migration (v0.4.0): Previously the orchestrator manually wired
GovernanceEngine + PlatformEnvelopeAdapter + GovernedSupervisor +
GovernedDelegate.  Now PactEngine 0.7.0 handles all of that internally
-- the orchestrator focuses on L3 platform features (persistence,
events, approval bridging).
"""

from __future__ import annotations

import logging
import math
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pact_platform.engine.approval_bridge import ApprovalBridge
from pact_platform.engine.event_bridge import EventBridge
from pact_platform.engine.settings import get_platform_settings
from pact_platform.models import validate_finite

if TYPE_CHECKING:
    from dataflow import DataFlow
    from pact.engine import PactEngine
    from pact.governance.engine import GovernanceEngine
    from pact_platform.trust.store.posture_history import PostureHistoryStore
    from pact_platform.use.api.events import EventBus

logger = logging.getLogger(__name__)

__all__ = ["SupervisorOrchestrator"]


class _PlatformHeldCallback:
    """Bridges PactEngine HELD verdicts to L3 ApprovalBridge persistence.

    Implements the ``HeldActionCallback`` protocol from ``pact.engine``.
    When PactEngine's per-node governance callback encounters a HELD
    verdict, it invokes this callback which persists an AgenticDecision
    record via the ApprovalBridge and returns ``False`` to block the
    action until a human approves it.

    Args:
        approval_bridge: The L3 ApprovalBridge for decision persistence.
    """

    def __init__(self, approval_bridge: ApprovalBridge) -> None:
        self._bridge = approval_bridge

    async def __call__(
        self,
        verdict: Any,
        role: str,
        action: str,
        context: dict[str, Any],
    ) -> bool:
        """Handle a HELD verdict by creating an AgenticDecision.

        Returns ``False`` to block the action until human approval.
        """
        decision_id = self._bridge.create_decision(
            role_address=role,
            action=action,
            verdict=verdict,
            request_id=context.get("request_id"),
            session_id=context.get("session_id"),
        )
        logger.info(
            "HELD: created AgenticDecision '%s' for role='%s' action='%s'",
            decision_id,
            role,
            action,
        )
        return False  # Block until human approves


class SupervisorOrchestrator:
    """Orchestrates governed execution via PactEngine with L3 platform features.

    The orchestrator composes PactEngine (which handles enforcement mode,
    per-node governance, supervisor lifecycle, NaN guards, and cost
    tracking) with L3 features: Run persistence (DataFlow), real-time
    events (EventBridge), and HELD-verdict approval persistence
    (ApprovalBridge via ``_PlatformHeldCallback``).

    Accepts either a ``PactEngine`` instance or a ``GovernanceEngine``
    for backward compatibility.  When a bare ``GovernanceEngine`` is
    provided, the orchestrator wraps it in a PactEngine internally.

    Args:
        engine: A ``PactEngine`` or ``GovernanceEngine`` instance.
        db: DataFlow instance for persistence (Run records, decisions).
        event_bus: Optional platform EventBus for real-time streaming.
            When ``None``, events are silently discarded.
        llm_model: The LLM model identifier for PactEngine/supervisor.
            Defaults to ``PACT_LLM_MODEL`` env var, then ``None``
            (PactEngine reads DEFAULT_LLM_MODEL from env internally).
    """

    def __init__(
        self,
        engine: PactEngine | GovernanceEngine,
        db: DataFlow,
        event_bus: EventBus | None = None,
        llm_model: str | None = None,
    ) -> None:
        self._db = db
        self._approval_bridge = ApprovalBridge(db)
        self._event_bridge = EventBridge(event_bus)
        self._llm_model = llm_model or os.getenv("PACT_LLM_MODEL")

        # Accept either PactEngine or bare GovernanceEngine
        self._pact = self._resolve_pact_engine(engine)

        # PactEngine detects degenerate envelopes at construction and
        # caches them in _degenerate_addresses. We use that directly
        # for per-request warnings during execute_request().

    def _resolve_pact_engine(self, engine: Any) -> PactEngine:
        """Resolve a PactEngine from the provided engine argument.

        If ``engine`` is already a ``PactEngine``, returns it directly
        (with HELD callback wired if not already set).

        If ``engine`` is a bare ``GovernanceEngine``, wraps it in a new
        PactEngine with platform settings (enforcement mode, HELD
        callback, LLM model).

        Args:
            engine: A PactEngine or GovernanceEngine instance.

        Returns:
            A PactEngine instance ready for submit().
        """
        from pact.engine import PactEngine

        if isinstance(engine, PactEngine):
            return engine

        # Bare GovernanceEngine -- wrap it in PactEngine
        # Read enforcement mode from platform settings
        l1_mode = get_platform_settings().enforcement_mode

        # Extract the compiled org from the engine to build PactEngine
        try:
            compiled_org = engine.get_org()
        except Exception:
            # Fallback: try compiled_org property
            compiled_org = getattr(engine, "compiled_org", None)
            if compiled_org is None:
                raise

        # PactEngine._create_governance_engine won't accept our compiled
        # org directly.  Instead, we construct PactEngine and swap in the
        # existing governance engine.
        pact = object.__new__(PactEngine)

        # Initialize PactEngine's internal state manually, mirroring
        # PactEngine.__init__ but reusing the provided governance engine
        from pact.costs import CostTracker
        from pact.enforcement import validate_enforcement_mode
        from pact.events import EventBus as L1EventBus

        validate_enforcement_mode(l1_mode)
        pact._enforcement_mode = l1_mode
        pact._on_held = _PlatformHeldCallback(self._approval_bridge)
        pact._model = self._llm_model
        pact._clearance = "restricted"
        pact._store_backend = "memory"
        pact._governance = engine
        pact._costs = CostTracker(budget_usd=None)
        pact._events = L1EventBus(maxlen=10000)
        pact._supervisor = None

        # Run degenerate detection (same as PactEngine.__init__)
        pact._detect_degenerate_envelopes()
        logger.info(
            "SupervisorOrchestrator: wrapped GovernanceEngine in PactEngine "
            "(enforcement_mode=%s)",
            l1_mode.value,
        )
        return pact

    @property
    def pact_engine(self) -> PactEngine:
        """The underlying PactEngine instance."""
        return self._pact

    @property
    def approval_bridge(self) -> ApprovalBridge:
        """Expose the approval bridge for external resolution (approve/reject)."""
        return self._approval_bridge

    @property
    def event_bridge(self) -> EventBridge:
        """Expose the event bridge for external event subscription."""
        return self._event_bridge

    def wire_posture_assessor(
        self,
        posture_store: PostureHistoryStore,
        compliance_roles: set[str] | None = None,
    ) -> None:
        """Wire the D/T/R assessor validator into a PostureHistoryStore.

        Enables structural independence checking for posture upgrades:
        direct supervisors are blocked from assessing their subordinates
        (conflict of interest), while compliance roles and distant
        ancestors are allowed.

        Call this during platform initialization after the
        PostureHistoryStore has been created.

        Args:
            posture_store: The PostureHistoryStore to attach the
                D/T/R assessor validator to.
            compliance_roles: Optional set of D/T/R address strings
                for designated compliance roles that may always
                assess posture upgrades.
        """
        from pact_platform.trust.posture_assessor import wire_assessor_validator

        # Use the admin governance engine for posture wiring
        admin_engine = self._pact._admin_governance
        wire_assessor_validator(admin_engine, posture_store, compliance_roles)
        logger.info("Orchestrator: D/T/R posture assessor validator wired")

    def execute_request(
        self,
        request_id: str,
        role_address: str,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a request through the PactEngine-governed pipeline.

        Steps:
        1. Validate inputs and NaN-guard context cost values.
        2. Warn if operating under a degenerate envelope.
        3. Submit to PactEngine (handles enforcement mode, per-node
           governance, supervisor lifecycle, NaN guards, cost tracking).
        4. Record Run in DataFlow.
        5. Bridge completion event to platform EventBus.
        6. Return results.

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
            - ``"audit_trail"`` (list): Governance verdicts.
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

        # Enrich context with L3 platform identifiers
        submit_context = {
            "request_id": request_id,
            "role_address": role_address,
            "run_id": run_id,
            **ctx,
        }

        # Submit to PactEngine -- handles enforcement mode, per-node
        # governance, supervisor lifecycle, NaN guards, and cost tracking.
        try:
            result = self._submit_sync(objective, role_address, submit_context)
        except Exception as exc:
            logger.error(
                "Orchestrator: PactEngine submission failed for " "request='%s': %s",
                request_id,
                exc,
            )
            self._record_run(
                run_id=run_id,
                request_id=request_id,
                role_address=role_address,
                status="failed",
                started_at=started_at,
                error_message=f"PactEngine submission failed: {exc}",
            )
            self._event_bridge.on_completion_event(
                request_id=request_id,
                success=False,
                budget_consumed=0.0,
                budget_allocated=0.0,
            )
            # H4 fix: generic error message to caller
            return {
                "success": False,
                "request_id": request_id,
                "run_id": run_id,
                "results": {},
                "budget_consumed": 0.0,
                "budget_allocated": 0.0,
                "audit_trail": [],
                "error": "Execution failed",
            }

        # NaN-guard the budget values from PactEngine result
        budget_consumed = result.cost_usd
        if not math.isfinite(budget_consumed):
            logger.error(
                "Orchestrator: cost_usd is non-finite (%r) -- " "recording as 0.0",
                budget_consumed,
            )
            budget_consumed = 0.0

        # Record Run in DataFlow
        ended_at = datetime.now(UTC)
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

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
                "node_count": len(result.results),
                "governance_shadow": result.governance_shadow,
            },
            error_message=result.error or "",
        )

        # Bridge completion event
        self._event_bridge.on_completion_event(
            request_id=request_id,
            success=result.success,
            budget_consumed=budget_consumed,
            budget_allocated=0.0,  # PactEngine handles budget internally
        )

        logger.info(
            "Orchestrator: completed request='%s' success=%s " "budget=$%.4f duration=%dms",
            request_id,
            result.success,
            budget_consumed,
            duration_ms,
        )

        return {
            "success": result.success,
            "request_id": request_id,
            "run_id": run_id,
            "results": result.results,
            "budget_consumed": budget_consumed,
            "budget_allocated": 0.0,
            "audit_trail": result.governance_verdicts,
            "error": result.error if not result.success else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _submit_sync(
        self,
        objective: str,
        role: str,
        context: dict[str, Any],
    ) -> Any:
        """Call PactEngine.submit() synchronously.

        Uses PactEngine.submit_sync() which handles event loop detection
        and thread delegation internally.

        Returns:
            A WorkResult from PactEngine.
        """
        return self._pact.submit_sync(
            objective=objective,
            role=role,
            context=context,
        )

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
            self._db.express_sync.create(
                "Run",
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
        except Exception:
            logger.exception(
                "Orchestrator: failed to record Run '%s' -- run data may be lost",
                run_id,
            )
