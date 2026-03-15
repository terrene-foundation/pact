# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""CARE trust decorators — thin wrappers around EATP SDK enforce operations.

These decorators wire EATP's trust operations (VERIFY, AUDIT, shadow check)
to the CARE Platform's trust infrastructure (EATPBridge, ShadowEnforcer),
providing dynamic agent_id extraction from function arguments.

Usage::

    from care_platform.trust.decorators import CareTrustOpsProvider, care_verified

    provider = CareTrustOpsProvider(bridge)

    @care_verified(action="read_data", provider=provider)
    async def read_data(agent_id: str, path: str) -> dict:
        ...

Migration path (shadow → audited → verified)::

    # Stage 1: Observe — deploy with @care_shadow to collect empirical evidence.
    # Shadow mode never blocks; it records what WOULD happen under enforcement.
    # CARE ShadowEnforcer metrics feed into posture upgrade decisions.
    @care_shadow(action="read_data", provider=provider)
    async def read_data(agent_id: str, path: str) -> dict: ...

    # Stage 2: Record — switch to @care_audited for cryptographic audit trail.
    # Actions succeed normally; an EATP audit anchor is created after each call.
    @care_audited(provider=provider)
    async def read_data(agent_id: str, path: str) -> dict: ...

    # Stage 3: Enforce — switch to @care_verified for full trust enforcement.
    # VERIFY runs before execution. BLOCKED actions raise EATPBlockedError.
    # HELD actions raise EATPHeldError (configurable via on_held).
    @care_verified(action="read_data", provider=provider)
    async def read_data(agent_id: str, path: str) -> dict: ...

Each stage increases trust requirements. ShadowEnforcer metrics from stage 1
provide the empirical evidence needed to justify the upgrade to stage 3.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import inspect
import logging
import re
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from eatp.chain import VerificationLevel
from eatp.enforce import ShadowEnforcer as EATPShadowEnforcer
from eatp.enforce.strict import HeldBehavior, StrictEnforcer

if TYPE_CHECKING:
    from eatp import TrustOperations

    from care_platform.trust.eatp_bridge import EATPBridge
    from care_platform.trust.shadow_enforcer import ShadowEnforcer as CareShadowEnforcer

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _run_coroutine_sync(coro: Any) -> Any:
    """Run a coroutine from a synchronous context.

    Handles the case where an event loop is already running (e.g., Jupyter,
    ASGI frameworks) by executing in a separate thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()


class CareTrustOpsProvider:
    """Supplies EATP ``TrustOperations`` from a CARE ``EATPBridge``.

    This provider lazily retrieves the TrustOperations instance from the
    bridge, ensuring the bridge has been initialized before any decorator
    attempts to use it.

    Args:
        bridge: The CARE Platform EATPBridge instance. Must be initialized
                (``await bridge.initialize()``) before any decorated
                function is called.
    """

    def __init__(self, bridge: EATPBridge) -> None:
        self._bridge = bridge

    @property
    def ops(self) -> TrustOperations:
        """Return the TrustOperations from the bridge.

        Raises:
            RuntimeError: If the bridge has not been initialized.
        """
        if self._bridge.ops is None:
            msg = (
                "EATPBridge has not been initialized. "
                "Call 'await bridge.initialize()' before using decorated functions."
            )
            raise RuntimeError(msg)
        return self._bridge.ops

    @property
    def bridge(self) -> EATPBridge:
        """Return the underlying bridge instance."""
        return self._bridge


def care_verified(
    action: str,
    provider: CareTrustOpsProvider,
    *,
    agent_id_param: str = "agent_id",
    level: VerificationLevel = VerificationLevel.STANDARD,
    on_held: HeldBehavior = HeldBehavior.RAISE,
) -> Callable[[F], F]:
    """CARE wrapper around EATP VERIFY + StrictEnforcer — pre-execution trust enforcement.

    Verifies the agent's trust chain before executing the function.
    Raises ``EATPBlockedError`` if verification fails, ``EATPHeldError``
    if the action requires human review (configurable via ``on_held``).

    The pipeline mirrors EATP's ``@verified`` decorator but extracts
    ``agent_id`` dynamically from function arguments, allowing a single
    decorated function to serve multiple agents.

    Args:
        action: The action string to verify (e.g., ``"read_data"``).
        provider: CareTrustOpsProvider supplying TrustOperations.
        agent_id_param: Name of the function parameter that holds the agent ID.
        level: Verification thoroughness (QUICK, STANDARD, FULL).
        on_held: Behavior when verification result is HELD.
    """
    enforcer = StrictEnforcer(on_held=on_held)

    def decorator(func: F) -> F:
        param_idx = _resolve_param_index(func, agent_id_param)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            agent_id = _extract_agent_id(args, kwargs, agent_id_param, param_idx)
            ops = provider.ops
            result = await ops.verify(agent_id=agent_id, action=action, level=level)
            enforcer.enforce(agent_id=agent_id, action=action, result=result)
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            agent_id = _extract_agent_id(args, kwargs, agent_id_param, param_idx)
            ops = provider.ops
            result = _run_coroutine_sync(ops.verify(agent_id=agent_id, action=action, level=level))
            enforcer.enforce(agent_id=agent_id, action=action, result=result)
            return func(*args, **kwargs)

        wrapper: Any = async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
        wrapper.enforcer = enforcer
        return wrapper

    return decorator  # type: ignore[return-value]


def care_audited(
    provider: CareTrustOpsProvider,
    *,
    agent_id_param: str = "agent_id",
) -> Callable[[F], F]:
    """CARE wrapper around EATP AUDIT — post-execution audit trail.

    Records an audit anchor after the function completes successfully,
    creating a cryptographic record of the action and its result.
    Uses the same hashing approach as EATP's ``@audited`` decorator.

    Args:
        provider: CareTrustOpsProvider supplying TrustOperations.
        agent_id_param: Name of the function parameter that holds the agent ID.
    """

    def decorator(func: F) -> F:
        param_idx = _resolve_param_index(func, agent_id_param)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            agent_id = _extract_agent_id(args, kwargs, agent_id_param, param_idx)
            result = await func(*args, **kwargs)

            ops = provider.ops
            await ops.audit(
                agent_id=agent_id,
                action=func.__qualname__,
                context_data={
                    "args_hash": _hash_args(args, kwargs),
                    "result_hash": _hash_result(result),
                    "function": func.__qualname__,
                    "module": func.__module__,
                },
            )
            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            agent_id = _extract_agent_id(args, kwargs, agent_id_param, param_idx)
            result = func(*args, **kwargs)

            ops = provider.ops
            _run_coroutine_sync(
                ops.audit(
                    agent_id=agent_id,
                    action=func.__qualname__,
                    context_data={
                        "args_hash": _hash_args(args, kwargs),
                        "result_hash": _hash_result(result),
                        "function": func.__qualname__,
                        "module": func.__module__,
                    },
                )
            )
            return result

        wrapper: Any = async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
        return wrapper

    return decorator  # type: ignore[return-value]


def care_shadow(
    action: str,
    provider: CareTrustOpsProvider,
    *,
    agent_id_param: str = "agent_id",
    level: VerificationLevel = VerificationLevel.STANDARD,
    care_shadow_enforcer: CareShadowEnforcer | None = None,
) -> Callable[[F], F]:
    """CARE wrapper around EATP shadow verification — non-blocking observation.

    Runs VERIFY in shadow mode: evaluates the action's trust status but
    never blocks execution. Results are recorded by an EATP ShadowEnforcer
    for metric collection.

    When ``care_shadow_enforcer`` is provided, the evaluation is also
    forwarded to CARE's governance-level ShadowEnforcer, which runs the
    full gradient + envelope pipeline. This produces the posture upgrade
    metrics that drive the shadow → audited → verified migration.

    Args:
        action: The action string to evaluate (e.g., ``"draft_content"``).
        provider: CareTrustOpsProvider supplying TrustOperations.
        agent_id_param: Name of the function parameter that holds the agent ID.
        level: Verification thoroughness (QUICK, STANDARD, FULL).
        care_shadow_enforcer: Optional CARE ShadowEnforcer for governance metrics.
    """
    eatp_shadow = EATPShadowEnforcer()

    def decorator(func: F) -> F:
        param_idx = _resolve_param_index(func, agent_id_param)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            agent_id = _extract_agent_id(args, kwargs, agent_id_param, param_idx)
            ops = provider.ops
            try:
                vr = await ops.verify(agent_id=agent_id, action=action, level=level)
                eatp_shadow.check(agent_id=agent_id, action=action, result=vr)
            except Exception:
                logger.warning(
                    "[SHADOW] Verification error for agent=%s action=%s. "
                    "Shadow observation skipped (fail-safe).",
                    agent_id,
                    action,
                )

            if care_shadow_enforcer is not None:
                _forward_to_care_shadow(care_shadow_enforcer, action, agent_id)

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            agent_id = _extract_agent_id(args, kwargs, agent_id_param, param_idx)
            ops = provider.ops
            try:
                vr = _run_coroutine_sync(ops.verify(agent_id=agent_id, action=action, level=level))
                eatp_shadow.check(agent_id=agent_id, action=action, result=vr)
            except Exception:
                logger.warning(
                    "[SHADOW] Verification error for agent=%s action=%s. "
                    "Shadow observation skipped (fail-safe).",
                    agent_id,
                    action,
                )

            if care_shadow_enforcer is not None:
                _forward_to_care_shadow(care_shadow_enforcer, action, agent_id)

            return func(*args, **kwargs)

        wrapper: Any = async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
        wrapper.eatp_shadow = eatp_shadow
        return wrapper

    return decorator  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


# Agent ID format: alphanumeric, hyphens, underscores, dots. Max 256 chars.
_AGENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")
_AGENT_ID_MAX_LEN = 256


def _validate_agent_id(value: str) -> str:
    """Validate and return a sanitized agent_id.

    Raises:
        ValueError: If the agent_id is empty, too long, or contains
                    invalid characters.
    """
    if not value:
        raise ValueError("agent_id must not be empty")
    if len(value) > _AGENT_ID_MAX_LEN:
        raise ValueError(f"agent_id exceeds maximum length of {_AGENT_ID_MAX_LEN} characters")
    if not _AGENT_ID_PATTERN.match(value):
        raise ValueError(
            "agent_id contains invalid characters. "
            "Only alphanumeric, hyphens, underscores, and dots are allowed."
        )
    return value


def _resolve_param_index(func: Callable[..., Any], param_name: str) -> int:
    """Resolve the positional index of a parameter in a function signature.

    Called once at decoration time, not per invocation.

    Returns:
        The index of the parameter.

    Raises:
        ValueError: If the parameter is not in the function signature.
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    try:
        return params.index(param_name)
    except ValueError:
        raise ValueError(
            f"Parameter '{param_name}' not found in function "
            f"'{func.__qualname__}'. "
            f"Set agent_id_param to the correct parameter name."
        ) from None


def _extract_agent_id(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    param_name: str,
    param_index: int,
) -> str:
    """Extract and validate the agent_id from function arguments.

    Looks in kwargs first, then falls back to positional args using a
    pre-resolved parameter index.

    Raises:
        ValueError: If the parameter is not provided or the value is invalid.
    """
    if param_name in kwargs:
        return _validate_agent_id(str(kwargs[param_name]))

    if param_index < len(args):
        return _validate_agent_id(str(args[param_index]))

    raise ValueError(
        f"Required parameter '{param_name}' not provided. "
        f"Pass it as a positional or keyword argument."
    )


def _forward_to_care_shadow(
    care_shadow: CareShadowEnforcer,
    action: str,
    agent_id: str,
) -> None:
    """Forward to CARE's governance ShadowEnforcer for posture metrics.

    The CARE ShadowEnforcer runs the full governance pipeline (gradient
    classification, envelope evaluation, posture escalation), producing
    the empirical evidence for posture upgrade decisions.

    Fail-safe: shadow observation must never block execution.
    """
    try:
        care_shadow.evaluate(action=action, agent_id=agent_id)
    except Exception as exc:
        logger.warning(
            "CARE ShadowEnforcer evaluation failed for action=%s agent=%s: %s. "
            "Shadow observation skipped (fail-safe).",
            action,
            agent_id,
            type(exc).__name__,
        )


def _hash_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Create a deterministic hash of function arguments.

    Uses JSON serialization for JSON-compatible values (deterministic),
    falls back to type + repr hash for non-serializable objects.
    Incremental hashing avoids large intermediate strings.
    """
    h = hashlib.sha256()
    h.update(b"args:")
    for i, arg in enumerate(args):
        h.update(f"{i}:".encode())
        h.update(_value_hash(arg))
    h.update(b"kwargs:")
    for key in sorted(kwargs.keys()):
        h.update(f"{key}:".encode())
        h.update(_value_hash(kwargs[key]))
    return h.hexdigest()


def _hash_result(result: Any) -> str:
    """Create a deterministic hash of function result.

    Uses JSON serialization for deterministic hashing.
    """
    h = hashlib.sha256()
    h.update(b"result:")
    h.update(_value_hash(result))
    return h.hexdigest()


def _value_hash(value: Any) -> bytes:
    """Produce a deterministic hash input for a single value.

    Tries JSON serialization first (deterministic for JSON-compatible
    types). Falls back to type name + repr for complex objects.
    Neither approach leaks raw values into intermediate strings longer
    than needed — the result is immediately fed into SHA-256.
    """
    import json

    try:
        serialized = json.dumps(value, sort_keys=True, default=str)
        return serialized.encode()
    except (TypeError, ValueError, OverflowError):
        # Non-serializable: use type + repr (deterministic for same object state)
        return f"{type(value).__qualname__}:{repr(value)}".encode()
