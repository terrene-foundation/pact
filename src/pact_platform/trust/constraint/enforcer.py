# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint enforcer — makes constraint checking mandatory at runtime.

Wraps VerificationMiddleware so that every runtime action passes through
constraint verification. If the enforcer is absent when the runtime tries
to process an action, an explicit EnforcerRequiredError is raised (never
a silent bypass).

The enforcer's check() method takes an action, agent_id, and optional
resource, and returns a MiddlewareResult. BLOCKED results reject the
action, HELD results queue for approval, and AUTO_APPROVED/FLAGGED
results allow the action to proceed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pact_platform.trust.constraint.middleware import MiddlewareResult, VerificationMiddleware

logger = logging.getLogger(__name__)


class EnforcerRequiredError(RuntimeError):
    """Raised when constraint enforcement is required but no enforcer is configured.

    This error ensures fail-closed behavior: rather than silently bypassing
    constraint checks, the runtime raises an explicit error when the enforcer
    is missing.
    """

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = (
                "Constraint enforcer is required but not configured. "
                "Every runtime action must pass through constraint verification. "
                "Provide a ConstraintEnforcer to the ExecutionRuntime to proceed."
            )
        super().__init__(message)


class ConstraintEnforcer:
    """Makes constraint checking mandatory for every runtime action.

    Wraps a VerificationMiddleware instance, providing a simplified check()
    interface that the runtime calls before processing any task.

    Args:
        middleware: The VerificationMiddleware to delegate constraint checks to.
            Must not be None.

    Raises:
        ValueError: If middleware is None.
    """

    def __init__(self, middleware: VerificationMiddleware) -> None:
        if middleware is None:
            raise ValueError(
                "middleware is required and must not be None. "
                "The ConstraintEnforcer requires a VerificationMiddleware "
                "to evaluate actions against constraint envelopes."
            )
        self._middleware = middleware

    @property
    def middleware(self) -> VerificationMiddleware:
        """The underlying VerificationMiddleware."""
        return self._middleware

    def check(
        self,
        action: str,
        agent_id: str,
        *,
        resource: str = "",
        spend_amount: float = 0.0,
        current_action_count: int = 0,
        is_external: bool = False,
        data_paths: list[str] | None = None,
    ) -> MiddlewareResult:
        """Check an action against the constraint envelope.

        Delegates to the underlying VerificationMiddleware.process_action().
        Every call is recorded in the middleware's audit chain.

        Args:
            action: The action being attempted.
            agent_id: The agent attempting the action.
            resource: Optional resource the action targets.
            spend_amount: Per-action spend amount (USD).
            current_action_count: Number of actions taken today.
            is_external: Whether this is an external communication.
            data_paths: List of data paths being accessed.

        Returns:
            A MiddlewareResult with the verification outcome.
        """
        logger.debug(
            "Enforcer checking: action=%s agent_id=%s resource=%s",
            action,
            agent_id,
            resource,
        )

        result = self._middleware.process_action(
            agent_id=agent_id,
            action=action,
            resource=resource,
            spend_amount=spend_amount,
            current_action_count=current_action_count,
            is_external=is_external,
            data_paths=data_paths,
        )

        logger.debug(
            "Enforcer result: action=%s agent_id=%s level=%s outcome=%s",
            action,
            agent_id,
            result.verification_level.value,
            result.outcome.value,
        )

        return result
