# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Verification gradient middleware — intercepts every agent action.

Routes actions through the constraint envelope and gradient engine:
- AUTO_APPROVED: execute and log
- FLAGGED: execute, log, and highlight for review
- HELD: queue for human approval
- BLOCKED: reject with explanation, log attempt

RT-03: NEVER_DELEGATED_ACTIONS check before gradient classification.
RT-05: Unified approval queues via optional shared ApprovalQueue.
RT-08: Envelope expiry check at start of process_action.
RT-30: Emergency halt mechanism blocks all actions until resumed.
RT-09: Trust posture level affects action processing.
RT2-01: Emergency halt blocks approval queue.
RT2-03: Re-verify envelope/attestation at approval time.
RT2-06: Attestation validity check in pipeline.
RT2-14: Cumulative spend tracking.
RT2-33: Signed envelope verification.
RT2-19: Resource recorded in audit metadata for traceability.
RT2-34: Audit chain signing.
RT2-36: Halt/resume events audited.
"""

from __future__ import annotations

import logging
import threading
import time as _time
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from pact_platform.build.config.schema import TrustPostureLevel, VerificationLevel
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.trust.constraint.cache import CachedVerification, VerificationCache
from pact_platform.trust.constraint.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from pact_platform.trust.constraint.envelope import ConstraintEnvelope
from pact_platform.trust.constraint.gradient import GradientEngine, VerificationResult
from pact_platform.trust._compat import TrustPosture
from pact_platform.use.execution.approval import ApprovalQueue

if TYPE_CHECKING:
    from typing import Any

    from pact_platform.trust.constraint.signing import SignedEnvelope
    from pact_platform.trust.store.health import TrustStoreHealthCheck
    from pact_platform.trust.store.store import TrustStore

    # Deleted modules — types used only in optional parameters (None-checked at runtime)
    AuthorizationCheck = Any  # was: pact_platform.trust.authorization.AuthorizationCheck
    EATPBridge = Any  # was: pact_platform.trust.eatp_bridge.EATPBridge

logger = logging.getLogger(__name__)


class ActionOutcome(str, Enum):
    """Outcome of an action after middleware processing."""

    EXECUTED = "executed"  # Action was executed
    QUEUED = "queued"  # Action queued for human approval
    REJECTED = "rejected"  # Action blocked


class ApprovalRequest(BaseModel):
    """A held action awaiting human approval.

    .. deprecated::
        Use pact.use.execution.approval.PendingAction with a shared
        ApprovalQueue instead. This class is retained for backward
        compatibility with existing callers.
    """

    request_id: str
    agent_id: str
    action: str
    resource: str
    reason: str  # why it was held
    constraint_details: dict  # which constraints triggered
    requested_at: datetime
    status: str = "pending"  # pending, approved, rejected
    decided_by: str | None = None
    decided_at: datetime | None = None


class MiddlewareResult(BaseModel):
    """Result of middleware evaluation."""

    action: str
    agent_id: str
    verification_level: VerificationLevel
    outcome: ActionOutcome
    approval_request: ApprovalRequest | None = None  # if HELD
    audit_recorded: bool = False
    details: str = ""


class VerificationMiddleware:
    """Intercepts agent actions, evaluates constraints, routes appropriately.

    Flow: action -> check expiry -> check never-delegated -> check posture
    -> evaluate envelope -> classify gradient -> route:
    - AUTO_APPROVED: execute and log
    - FLAGGED: execute, log, and highlight for review
    - HELD: queue for human approval
    - BLOCKED: reject with explanation, log attempt
    """

    def __init__(
        self,
        gradient_engine: GradientEngine,
        envelope: ConstraintEnvelope,
        audit_chain: AuditChain | None = None,
        approval_queue: ApprovalQueue | None = None,
        signed_envelope: SignedEnvelope | None = None,
        *,
        eatp_bridge: EATPBridge | None = None,
        signing_key: bytes | None = None,
        signer_id: str = "middleware",
        public_key: bytes | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        authorization_check: AuthorizationCheck | None = None,
        trust_store_health: TrustStoreHealthCheck | None = None,
        verification_cache: VerificationCache | None = None,
        cache_ttl_seconds: float = 60.0,
        spend_store: TrustStore | None = None,
        delegation_expiry: datetime | None = None,
    ) -> None:
        if gradient_engine is None:
            raise ValueError("gradient_engine is required and must not be None")
        if envelope is None:
            raise ValueError("envelope is required and must not be None")
        self.gradient = gradient_engine
        self._envelope = envelope
        self.audit_chain = audit_chain or AuditChain(chain_id="middleware")
        self._approval_queue: list[ApprovalRequest] = []
        self._action_log: list[MiddlewareResult] = []
        # RT-05: Shared approval queue (optional)
        self._shared_queue: ApprovalQueue | None = approval_queue
        # RT2-33: Typed signed envelope with optional signature verification
        self.signed_envelope = signed_envelope
        if signed_envelope is not None and public_key is not None:
            if not signed_envelope.verify_signature(public_key):
                raise ValueError("Signed envelope signature verification failed")
        # RT2-06: EATP bridge for attestation checks
        self._eatp_bridge: EATPBridge | None = eatp_bridge
        # RT2-34: Signing key for audit chain signing
        self._signing_key: bytes | None = signing_key
        self._signer_id: str = signer_id
        self._public_key: bytes | None = public_key
        # RT-03: Trust posture helper for never-delegated checks
        self._posture_helper = TrustPosture(agent_id="__middleware_helper__")
        # RT-30: Emergency halt state
        self._halted: bool = False
        self._halt_reason: str = ""
        # M23/2303: Delegation expiry — checked at action-execution time
        self._delegation_expiry: datetime | None = delegation_expiry
        # RT2-14: Cumulative spend tracking per agent with optional persistence.
        # RT10-DP2: When a spend_store is provided, cumulative spend survives restarts.
        self._spend_store: TrustStore | None = spend_store
        self._cumulative_spend: dict[str, float] = {}
        # M23/2304: Thread lock for cumulative spend updates
        self._spend_lock = threading.Lock()
        self._hydrate_cumulative_spend()
        # M23/2306: Per-agent rate limiting sliding window
        # Maps agent_id -> list of action timestamps within the window
        self._rate_limit_windows: dict[str, list[float]] = {}
        # RT2-26: Circuit breaker for verification pipeline
        self._circuit_breaker: CircuitBreaker | None = circuit_breaker
        # M16-02: Authorization check (separates authorization from capability)
        self._authorization_check: AuthorizationCheck | None = authorization_check
        # M16-03: Trust store health check (fail-closed when store is unreachable)
        self._trust_store_health: TrustStoreHealthCheck | None = trust_store_health
        # M17-03: Verification cache (optional) for caching AUTO_APPROVED/FLAGGED results
        self._verification_cache: VerificationCache | None = verification_cache
        self._cache_ttl_seconds: float = cache_ttl_seconds

    def _hydrate_cumulative_spend(self) -> None:
        """RT10-DP2: Load persisted cumulative spend data on startup.

        Reads from the TrustStore under a well-known key. No-op when
        no spend_store is configured.
        """
        if self._spend_store is None:
            return
        data = self._spend_store.get_delegation("__cumulative_spend__")
        if data is not None:
            spends = data.get("spends", {})
            for agent_id, amount in spends.items():
                if isinstance(amount, (int, float)):
                    self._cumulative_spend[agent_id] = float(amount)
            if spends:
                logger.info(
                    "RT10-DP2: Hydrated cumulative spend for %d agent(s) from store",
                    len(spends),
                )

    def _persist_cumulative_spend(self) -> None:
        """RT10-DP2: Persist cumulative spend data to the TrustStore.

        Called after every spend update to ensure budgets survive restarts.
        No-op when no spend_store is configured.
        """
        if self._spend_store is None:
            return
        self._spend_store.store_delegation(
            "__cumulative_spend__",
            {
                "delegation_id": "__cumulative_spend__",
                "spends": dict(self._cumulative_spend),
            },
        )

    @property
    def envelope(self) -> ConstraintEnvelope:
        """Read-only access to the constraint envelope."""
        return self._envelope

    def halt(self, reason: str) -> None:
        """RT-30: Emergency halt — block all actions until resumed.

        RT2-36: Records the halt event in the audit chain.

        Args:
            reason: Non-empty reason for the halt.
        """
        if not reason:
            raise ValueError("Halt reason must not be empty")
        self._halted = True
        self._halt_reason = reason
        logger.warning("Middleware HALTED: %s", reason)
        # RT2-36: Audit the halt event
        self.audit_chain.append(
            agent_id="__system__",
            action="emergency_halt",
            verification_level=VerificationLevel.BLOCKED,
            envelope_id=self.envelope.id,
            result="halt_activated",
            metadata={"reason": reason},
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

    def resume(self) -> None:
        """RT-30: Resume normal operation after an emergency halt.

        RT2-36: Records the resume event in the audit chain.
        """
        was_halted = self._halted
        self._halted = False
        self._halt_reason = ""
        if was_halted:
            # RT2-36: Audit the resume event
            self.audit_chain.append(
                agent_id="__system__",
                action="emergency_resume",
                verification_level=VerificationLevel.AUTO_APPROVED,
                envelope_id=self.envelope.id,
                result="halt_lifted",
                signing_key=self._signing_key,
                signer_id=self._signer_id,
            )

    @property
    def is_halted(self) -> bool:
        """Whether the middleware is in emergency halt state."""
        return self._halted

    def process_action(
        self,
        agent_id: str,
        action: str,
        resource: str = "",
        spend_amount: float = 0.0,
        current_action_count: int = 0,
        is_external: bool = False,
        data_paths: list[str] | None = None,
        agent_posture: TrustPostureLevel | None = None,
        current_time: datetime | None = None,
    ) -> MiddlewareResult:
        """Process an action through the verification pipeline.

        1. Check emergency halt (RT-30)
        2. Check envelope expiry (RT-08)
        3. Check agent posture restrictions (RT-09)
        3b. Check agent attestation validity (RT2-06)
        4. Check NEVER_DELEGATED_ACTIONS (RT-03)
        5. Evaluate through envelope (all five CARE constraint dimensions)
        6. Classify through gradient (passing envelope result)
        7. Apply never-delegated and posture-based upgrades
        8. Route based on verification level
        9. Record audit anchor
        10. Return result
        """
        # RT-30: Emergency halt check
        if self._halted:
            result = self._handle_blocked_direct(
                agent_id=agent_id,
                action=action,
                resource=resource,
                reason=f"Middleware halted: {self._halt_reason}",
            )
            self._action_log.append(result)
            return result

        # M16-03: Trust store health check — fail-closed when store is unreachable
        if self._trust_store_health is not None and self._trust_store_health.should_block_all():
            result = self._handle_blocked_direct(
                agent_id=agent_id,
                action=action,
                resource=resource,
                reason="Trust store is unreachable — fail-closed (all actions BLOCKED)",
            )
            self._action_log.append(result)
            return result

        # M23/2303: Check delegation expiry at action-execution time
        if self._delegation_expiry is not None and datetime.now(UTC) > self._delegation_expiry:
            result = self._handle_blocked_direct(
                agent_id=agent_id,
                action=action,
                resource=resource,
                reason="Delegation has expired — agent's trust chain is no longer valid",
            )
            self._action_log.append(result)
            return result

        # RT-08: Check envelope expiry first
        if self.envelope.is_expired:
            result = self._handle_blocked_direct(
                agent_id=agent_id,
                action=action,
                resource=resource,
                reason="Constraint envelope has expired",
            )
            self._action_log.append(result)
            return result

        # RT-09: PSEUDO_AGENT posture has no action authority at all
        if agent_posture == TrustPostureLevel.PSEUDO_AGENT:
            result = self._handle_blocked_direct(
                agent_id=agent_id,
                action=action,
                resource=resource,
                reason="Agent at PSEUDO_AGENT posture has no action authority",
            )
            self._action_log.append(result)
            return result

        # RT2-06: Check attestation validity before proceeding
        if self._eatp_bridge is not None:
            if not self._eatp_bridge.verify_capability(agent_id, action):
                result = self._handle_blocked_direct(
                    agent_id=agent_id,
                    action=action,
                    resource=resource,
                    reason="Agent capability attestation is invalid, expired, or revoked",
                )
                self._action_log.append(result)
                return result

        # M16-02: Authorization check — separates authorization from capability
        if self._authorization_check is not None:
            auth_result = self._authorization_check.evaluate(action=action, agent_id=agent_id)
            if not auth_result.permitted:
                result = self._handle_blocked_direct(
                    agent_id=agent_id,
                    action=action,
                    resource=resource,
                    reason=auth_result.denial_reason
                    or f"Authorization denied for agent '{agent_id}' action '{action}'",
                )
                self._action_log.append(result)
                return result

        # M23/2306: Per-agent rate limiting (max_actions_per_hour)
        max_per_hour = self._envelope.config.operational.max_actions_per_hour
        if max_per_hour is not None:
            now_ts = _time.monotonic()
            window = self._rate_limit_windows.setdefault(agent_id, [])
            # Prune timestamps older than 1 hour
            cutoff = now_ts - 3600.0
            window[:] = [ts for ts in window if ts > cutoff]
            if len(window) >= max_per_hour:
                result = self._handle_blocked_direct(
                    agent_id=agent_id,
                    action=action,
                    resource=resource,
                    reason=(
                        f"Per-agent rate limit exceeded: {len(window)} actions "
                        f"in the last hour (limit: {max_per_hour})"
                    ),
                )
                self._action_log.append(result)
                return result
            # Record this action's timestamp
            window.append(now_ts)

        # RT-03: Check NEVER_DELEGATED_ACTIONS before gradient classification
        is_never_delegated = self._posture_helper.is_action_always_held(action)

        # M17-03: Cache lookup — skip full evaluation for cacheable actions.
        # Only use cache when:
        # - Cache is configured
        # - Action has no spend (spend tracking requires fresh evaluation)
        # - Action is not never-delegated (always requires fresh eval)
        _cache_eligible = (
            self._verification_cache is not None and spend_amount == 0.0 and not is_never_delegated
        )
        if _cache_eligible:
            assert self._verification_cache is not None  # for type checker
            # RT10-DP3: Include envelope content hash in cache key so that
            # tightened envelopes immediately invalidate stale cached verdicts.
            cache_key = (agent_id, action, self.envelope.content_hash())
            cached = self._verification_cache.get(cache_key)
            if cached is not None:
                # Cache hit — use the cached verification level
                cached_level = VerificationLevel(cached.verification_result)
                if cached_level in (
                    VerificationLevel.AUTO_APPROVED,
                    VerificationLevel.FLAGGED,
                ):
                    if cached_level == VerificationLevel.AUTO_APPROVED:
                        result = self._handle_auto_approved_cached(
                            agent_id=agent_id,
                            action=action,
                            resource=resource,
                            cached_level=cached_level,
                        )
                    else:
                        result = self._handle_flagged_cached(
                            agent_id=agent_id,
                            action=action,
                            resource=resource,
                            cached_level=cached_level,
                        )
                    self._action_log.append(result)
                    return result

        # RT2-14: Get cumulative spend for this agent
        # M23/2304: Read under lock for consistency
        with self._spend_lock:
            agent_cumulative = self._cumulative_spend.get(agent_id, 0.0)

        # Step 1: Evaluate through the constraint envelope
        envelope_evaluation = self.envelope.evaluate_action(
            action=action,
            agent_id=agent_id,
            spend_amount=spend_amount,
            cumulative_spend=agent_cumulative,
            current_action_count=current_action_count,
            is_external=is_external,
            data_paths=data_paths,
            current_time=current_time,
        )

        # Step 2: Classify through the gradient engine (envelope result feeds in)
        # RT2-26: If circuit breaker is configured, wrap classification call
        try:
            if self._circuit_breaker is not None:
                verification = self._circuit_breaker.call(
                    self.gradient.classify,
                    action=action,
                    agent_id=agent_id,
                    envelope_evaluation=envelope_evaluation,
                )
            else:
                verification = self.gradient.classify(
                    action=action,
                    agent_id=agent_id,
                    envelope_evaluation=envelope_evaluation,
                )
        except CircuitBreakerOpen:
            # Fail-safe: circuit breaker tripped, BLOCK all actions
            result = self._handle_blocked_direct(
                agent_id=agent_id,
                action=action,
                resource=resource,
                reason="Verification circuit breaker is OPEN — fail-safe BLOCK",
            )
            self._action_log.append(result)
            return result

        level = verification.level

        # RT-03: Force HELD for never-delegated actions (unless BLOCKED,
        # which is more restrictive)
        if is_never_delegated and level != VerificationLevel.BLOCKED:
            level = VerificationLevel.HELD

        # RT-09: Posture-based upgrades
        if agent_posture == TrustPostureLevel.SUPERVISED:
            # SUPERVISED: minimum level is HELD (unless BLOCKED)
            if level in (VerificationLevel.AUTO_APPROVED, VerificationLevel.FLAGGED):
                level = VerificationLevel.HELD
        # Higher postures (SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED)
        # defer to gradient rules — no modification needed.

        # RT2-18: If envelope returned NEAR_BOUNDARY due to approval threshold,
        # upgrade FLAGGED to HELD so it actually requires human approval
        if level == VerificationLevel.FLAGGED and envelope_evaluation.is_near_boundary:
            for dim in envelope_evaluation.dimensions:
                if (
                    dim.result.value == "near_boundary"
                    and "approval threshold" in dim.reason.lower()
                ):
                    level = VerificationLevel.HELD
                    break

        # RT2-14: Track cumulative spend after successful evaluation
        # RT10-DP2: Persist spend data to store if configured
        # M23/2304: Thread-safe spend updates via _spend_lock
        if spend_amount > 0 and level != VerificationLevel.BLOCKED:
            with self._spend_lock:
                # Re-read under lock to prevent TOCTOU race
                agent_cumulative = self._cumulative_spend.get(agent_id, 0.0)
                self._cumulative_spend[agent_id] = agent_cumulative + spend_amount
            self._persist_cumulative_spend()

        # Step 3: Route based on verification level
        if level == VerificationLevel.AUTO_APPROVED:
            result = self._handle_auto_approved(
                agent_id=agent_id,
                action=action,
                resource=resource,
                verification=verification,
            )
        elif level == VerificationLevel.FLAGGED:
            result = self._handle_flagged(
                agent_id=agent_id,
                action=action,
                resource=resource,
                verification=verification,
            )
        elif level == VerificationLevel.HELD:
            result = self._handle_held(
                agent_id=agent_id,
                action=action,
                resource=resource,
                verification=verification,
            )
        elif level == VerificationLevel.BLOCKED:
            result = self._handle_blocked(
                agent_id=agent_id,
                action=action,
                resource=resource,
                verification=verification,
            )
        else:
            raise ValueError(
                f"Unknown verification level '{level}' for action '{action}' "
                f"by agent '{agent_id}'. This indicates a configuration error."
            )

        # M17-03: Populate cache for cacheable results (AUTO_APPROVED, FLAGGED only).
        # HELD and BLOCKED are NOT cached because they represent security-sensitive
        # outcomes that must always be freshly evaluated.
        if (
            _cache_eligible
            and self._verification_cache is not None
            and level in (VerificationLevel.AUTO_APPROVED, VerificationLevel.FLAGGED)
        ):
            # RT10-DP3: Cache key includes envelope hash for staleness detection
            cache_key = (agent_id, action, self.envelope.content_hash())
            cached_value = CachedVerification(
                trust_score=0.0,  # score not tracked in middleware context
                posture=TrustPostureLevel.SUPERVISED,  # placeholder
                verification_result=level.value,
            )
            self._verification_cache.put(
                cache_key, cached_value, ttl_seconds=self._cache_ttl_seconds
            )

        # Track in action log
        self._action_log.append(result)
        return result

    def approve_request(self, request_id: str, approver_id: str) -> MiddlewareResult:
        """Approve a held action -- executes it and records audit trail.

        RT2-01: Blocks approval when middleware is halted.
        RT2-03: Re-verifies envelope expiry and agent revocation before approval.
        """
        # RT2-01: Block approvals during emergency halt
        if self._halted:
            raise RuntimeError(
                f"Cannot approve actions while middleware is halted: {self._halt_reason}"
            )

        # RT-05: Try shared queue first
        if self._shared_queue is not None:
            return self._approve_via_shared_queue(request_id, approver_id)

        request = self._find_pending_request(request_id)

        # RT2-03: Re-verify before approval
        self._re_verify_before_decision(request)

        # Update the request status
        request.status = "approved"
        request.decided_by = approver_id
        request.decided_at = datetime.now(UTC)

        # Record approval in audit chain
        self.audit_chain.append(
            agent_id=request.agent_id,
            action=request.action,
            verification_level=VerificationLevel.HELD,
            envelope_id=self.envelope.id,
            result="approved",
            metadata={
                "approver_id": approver_id,
                "request_id": request_id,
            },
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        result = MiddlewareResult(
            action=request.action,
            agent_id=request.agent_id,
            verification_level=VerificationLevel.HELD,
            outcome=ActionOutcome.EXECUTED,
            approval_request=request,
            audit_recorded=True,
            details=f"Approved by {approver_id}",
        )

        logger.info(
            "Held action approved: action=%s agent=%s approver=%s request_id=%s",
            request.action,
            request.agent_id,
            approver_id,
            request_id,
        )

        self._action_log.append(result)
        return result

    def reject_request(
        self, request_id: str, approver_id: str, reason: str = ""
    ) -> MiddlewareResult:
        """Reject a held action.

        RT2-01: Blocks rejection when middleware is halted.
        """
        # RT2-01: Block rejections during emergency halt
        if self._halted:
            raise RuntimeError(
                f"Cannot reject actions while middleware is halted: {self._halt_reason}"
            )

        # RT-05: Try shared queue first
        if self._shared_queue is not None:
            return self._reject_via_shared_queue(request_id, approver_id, reason)

        request = self._find_pending_request(request_id)

        # Update the request status
        request.status = "rejected"
        request.decided_by = approver_id
        request.decided_at = datetime.now(UTC)

        # Record rejection in audit chain
        self.audit_chain.append(
            agent_id=request.agent_id,
            action=request.action,
            verification_level=VerificationLevel.HELD,
            envelope_id=self.envelope.id,
            result="rejected",
            metadata={
                "approver_id": approver_id,
                "request_id": request_id,
                "rejection_reason": reason,
            },
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        details = f"Rejected by {approver_id}"
        if reason:
            details += f": {reason}"

        result = MiddlewareResult(
            action=request.action,
            agent_id=request.agent_id,
            verification_level=VerificationLevel.HELD,
            outcome=ActionOutcome.REJECTED,
            approval_request=request,
            audit_recorded=True,
            details=details,
        )

        logger.info(
            "Held action rejected: action=%s agent=%s approver=%s reason=%s request_id=%s",
            request.action,
            request.agent_id,
            approver_id,
            reason,
            request_id,
        )

        self._action_log.append(result)
        return result

    @property
    def pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return [r for r in self._approval_queue if r.status == "pending"]

    @property
    def action_log(self) -> list[MiddlewareResult]:
        """Get all processed actions."""
        return list(self._action_log)

    def get_flagged_actions(self) -> list[MiddlewareResult]:
        """Get actions that were flagged for review."""
        return [r for r in self._action_log if r.verification_level == VerificationLevel.FLAGGED]

    # --- Private helpers ---

    def _handle_auto_approved_cached(
        self,
        agent_id: str,
        action: str,
        resource: str,
        cached_level: VerificationLevel,
    ) -> MiddlewareResult:
        """Handle a cache hit for AUTO_APPROVED actions."""
        self.audit_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=VerificationLevel.AUTO_APPROVED,
            envelope_id=self.envelope.id,
            result="executed",
            metadata={"cache_hit": True, "resource": resource} if resource else {"cache_hit": True},
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )
        return MiddlewareResult(
            action=action,
            agent_id=agent_id,
            verification_level=VerificationLevel.AUTO_APPROVED,
            outcome=ActionOutcome.EXECUTED,
            audit_recorded=True,
            details="Auto-approved (cached)",
        )

    def _handle_flagged_cached(
        self,
        agent_id: str,
        action: str,
        resource: str,
        cached_level: VerificationLevel,
    ) -> MiddlewareResult:
        """Handle a cache hit for FLAGGED actions."""
        self.audit_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=VerificationLevel.FLAGGED,
            envelope_id=self.envelope.id,
            result="executed_flagged",
            metadata={"cache_hit": True, "resource": resource} if resource else {"cache_hit": True},
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )
        return MiddlewareResult(
            action=action,
            agent_id=agent_id,
            verification_level=VerificationLevel.FLAGGED,
            outcome=ActionOutcome.EXECUTED,
            audit_recorded=True,
            details="Flagged for review (cached)",
        )

    def _handle_blocked_direct(
        self,
        agent_id: str,
        action: str,
        resource: str,
        reason: str,
    ) -> MiddlewareResult:
        """Block an action without going through the gradient engine.

        Used for pre-pipeline checks (envelope expiry, posture restrictions).
        """
        self.audit_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=VerificationLevel.BLOCKED,
            envelope_id=self.envelope.id,
            result="rejected",
            metadata={"reason": reason, "resource": resource} if resource else {"reason": reason},
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        logger.warning(
            "Action blocked (pre-pipeline): action=%s agent=%s reason=%s",
            action,
            agent_id,
            reason,
        )

        return MiddlewareResult(
            action=action,
            agent_id=agent_id,
            verification_level=VerificationLevel.BLOCKED,
            outcome=ActionOutcome.REJECTED,
            audit_recorded=True,
            details=f"Blocked: {reason}",
        )

    def _handle_auto_approved(
        self,
        agent_id: str,
        action: str,
        resource: str,
        verification: VerificationResult,
    ) -> MiddlewareResult:
        """Execute the action, record audit, return result."""
        self.audit_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=VerificationLevel.AUTO_APPROVED,
            envelope_id=self.envelope.id,
            result="executed",
            metadata={"resource": resource} if resource else None,
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        logger.debug(
            "Auto-approved action executed: action=%s agent=%s",
            action,
            agent_id,
        )

        return MiddlewareResult(
            action=action,
            agent_id=agent_id,
            verification_level=VerificationLevel.AUTO_APPROVED,
            outcome=ActionOutcome.EXECUTED,
            audit_recorded=True,
            details=(
                f"Auto-approved: {verification.reason}" if verification.reason else "Auto-approved"
            ),
        )

    def _handle_flagged(
        self,
        agent_id: str,
        action: str,
        resource: str,
        verification: VerificationResult,
    ) -> MiddlewareResult:
        """Execute the action but mark it for review."""
        self.audit_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=VerificationLevel.FLAGGED,
            envelope_id=self.envelope.id,
            result="executed_flagged",
            metadata=(
                {"reason": verification.reason, "resource": resource}
                if resource
                else {"reason": verification.reason}
            ),
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        logger.info(
            "Flagged action executed (review needed): action=%s agent=%s reason=%s",
            action,
            agent_id,
            verification.reason,
        )

        return MiddlewareResult(
            action=action,
            agent_id=agent_id,
            verification_level=VerificationLevel.FLAGGED,
            outcome=ActionOutcome.EXECUTED,
            audit_recorded=True,
            details=(
                f"Flagged for review: {verification.reason}"
                if verification.reason
                else "Flagged for review"
            ),
        )

    def _handle_held(
        self,
        agent_id: str,
        action: str,
        resource: str,
        verification: VerificationResult,
    ) -> MiddlewareResult:
        """Queue the action for human approval."""
        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent_id=agent_id,
            action=action,
            resource=resource,
            reason=verification.reason or "Action requires human approval",
            constraint_details={
                "matched_rule": verification.matched_rule,
                "verification_level": verification.level.value,
            },
            requested_at=datetime.now(UTC),
        )

        self._approval_queue.append(request)

        # RT-05: Also submit to shared queue when present
        if self._shared_queue is not None:
            self._shared_queue.submit(
                agent_id=agent_id,
                action=action,
                reason=verification.reason or "Action requires human approval",
                resource=resource,
                constraint_details={
                    "matched_rule": verification.matched_rule,
                    "verification_level": verification.level.value,
                    "middleware_request_id": request.request_id,
                },
            )

        self.audit_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=VerificationLevel.HELD,
            envelope_id=self.envelope.id,
            result="queued",
            metadata={"request_id": request.request_id},
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        logger.info(
            "Action held for approval: action=%s agent=%s request_id=%s reason=%s",
            action,
            agent_id,
            request.request_id,
            verification.reason,
        )

        return MiddlewareResult(
            action=action,
            agent_id=agent_id,
            verification_level=VerificationLevel.HELD,
            outcome=ActionOutcome.QUEUED,
            approval_request=request,
            audit_recorded=True,
            details=(
                f"Held for approval: {verification.reason}"
                if verification.reason
                else "Held for approval"
            ),
        )

    def _handle_blocked(
        self,
        agent_id: str,
        action: str,
        resource: str,
        verification: VerificationResult,
    ) -> MiddlewareResult:
        """Reject the action with explanation."""
        self.audit_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=VerificationLevel.BLOCKED,
            envelope_id=self.envelope.id,
            result="rejected",
            metadata=(
                {"reason": verification.reason, "resource": resource}
                if resource
                else {"reason": verification.reason}
            ),
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        reason = verification.reason or "Action blocked by verification gradient"
        details = f"Blocked: {reason}"

        logger.warning(
            "Action blocked: action=%s agent=%s reason=%s",
            action,
            agent_id,
            reason,
        )

        return MiddlewareResult(
            action=action,
            agent_id=agent_id,
            verification_level=VerificationLevel.BLOCKED,
            outcome=ActionOutcome.REJECTED,
            audit_recorded=True,
            details=details,
        )

    def _find_pending_request(self, request_id: str) -> ApprovalRequest:
        """Find a pending approval request by ID, raising ValueError if not found."""
        for request in self._approval_queue:
            if request.request_id == request_id and request.status == "pending":
                return request

        raise ValueError(
            f"Approval request '{request_id}' not found in pending queue. "
            f"It may have already been decided or the ID is invalid. "
            f"Current pending count: {len(self.pending_approvals)}"
        )

    # --- RT-05: Shared queue delegation helpers ---

    def _approve_via_shared_queue(self, request_id: str, approver_id: str) -> MiddlewareResult:
        """Approve via shared queue, keeping internal state in sync."""
        # RT2-01: Defense-in-depth halt check (caller already checks, re-check for safety)
        if self._halted:
            raise RuntimeError(
                f"Cannot approve actions while middleware is halted: {self._halt_reason}"
            )

        request = self._find_pending_request(request_id)

        # RT2-03: Re-verify before approval
        self._re_verify_before_decision(request)

        # Find the matching shared queue action
        assert self._shared_queue is not None  # guaranteed by caller
        shared_action_id = self._find_shared_action_id(request_id)
        if shared_action_id is not None:
            self._shared_queue.approve(shared_action_id, approver_id)

        # Update internal state
        request.status = "approved"
        request.decided_by = approver_id
        request.decided_at = datetime.now(UTC)

        self.audit_chain.append(
            agent_id=request.agent_id,
            action=request.action,
            verification_level=VerificationLevel.HELD,
            envelope_id=self.envelope.id,
            result="approved",
            metadata={
                "approver_id": approver_id,
                "request_id": request_id,
            },
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        result = MiddlewareResult(
            action=request.action,
            agent_id=request.agent_id,
            verification_level=VerificationLevel.HELD,
            outcome=ActionOutcome.EXECUTED,
            approval_request=request,
            audit_recorded=True,
            details=f"Approved by {approver_id}",
        )

        self._action_log.append(result)
        return result

    def _reject_via_shared_queue(
        self, request_id: str, approver_id: str, reason: str = ""
    ) -> MiddlewareResult:
        """Reject via shared queue, keeping internal state in sync."""
        # RT2-01: Defense-in-depth halt check (caller already checks, re-check for safety)
        if self._halted:
            raise RuntimeError(
                f"Cannot reject actions while middleware is halted: {self._halt_reason}"
            )

        request = self._find_pending_request(request_id)

        # Find the matching shared queue action
        assert self._shared_queue is not None  # guaranteed by caller
        shared_action_id = self._find_shared_action_id(request_id)
        if shared_action_id is not None:
            self._shared_queue.reject(shared_action_id, approver_id, reason)

        # Update internal state
        request.status = "rejected"
        request.decided_by = approver_id
        request.decided_at = datetime.now(UTC)

        self.audit_chain.append(
            agent_id=request.agent_id,
            action=request.action,
            verification_level=VerificationLevel.HELD,
            envelope_id=self.envelope.id,
            result="rejected",
            metadata={
                "approver_id": approver_id,
                "request_id": request_id,
                "rejection_reason": reason,
            },
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        details = f"Rejected by {approver_id}"
        if reason:
            details += f": {reason}"

        result = MiddlewareResult(
            action=request.action,
            agent_id=request.agent_id,
            verification_level=VerificationLevel.HELD,
            outcome=ActionOutcome.REJECTED,
            approval_request=request,
            audit_recorded=True,
            details=details,
        )

        self._action_log.append(result)
        return result

    def _re_verify_before_decision(self, request: ApprovalRequest) -> None:
        """RT2-03: Re-verify envelope and agent state before approving a held action.

        Between the time an action was HELD and when a human approves it,
        conditions may have changed: the envelope may have expired, or the
        agent may have been revoked. This prevents time-of-check-time-of-use
        (TOCTOU) gaps in the approval flow.

        Raises:
            RuntimeError: If the envelope has expired or the agent is revoked.
        """
        # Re-check envelope expiry
        if self.envelope.is_expired:
            raise RuntimeError(
                f"Cannot approve action '{request.action}' for agent '{request.agent_id}': "
                "constraint envelope has expired since the action was held"
            )

        # Re-check agent revocation via EATP bridge
        if self._eatp_bridge is not None:
            if not self._eatp_bridge.verify_capability(request.agent_id, request.action):
                raise RuntimeError(
                    f"Cannot approve action '{request.action}' for agent '{request.agent_id}': "
                    "agent capability attestation is no longer valid (revoked or expired)"
                )

    def _find_shared_action_id(self, middleware_request_id: str) -> str | None:
        """Find the shared queue action_id matching a middleware request_id."""
        if self._shared_queue is None:
            return None
        for pa in self._shared_queue.pending:
            if pa.constraint_details.get("middleware_request_id") == middleware_request_id:
                return pa.action_id
        return None
