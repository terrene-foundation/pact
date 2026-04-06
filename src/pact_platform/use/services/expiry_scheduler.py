# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared expiry scheduler for time-limited governance records.

Polls registered models on a configurable interval and transitions
records past their expires_at deadline. Used by:
- Bootstrap mode (BootstrapRecord)
- Task envelopes (TaskEnvelopeRecord)
- Decision timeout (AgenticDecision)
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Callable, Awaitable

if TYPE_CHECKING:
    from dataflow import DataFlow

logger = logging.getLogger(__name__)

__all__ = ["ExpiryScheduler", "ExpiryHandler", "ExpiryResult"]


@dataclass(frozen=True)
class ExpiryHandler:
    """Configuration for a single model's expiry behaviour.

    Attributes:
        model_name: DataFlow model name (e.g. ``"BootstrapRecord"``).
        status_field: Field holding the record's lifecycle status.
        expires_field: Field holding the ISO 8601 expiry timestamp.
        active_status: Status value that marks a record as eligible for
            expiry (e.g. ``"active"``).
        expired_status: Status value to transition to once expired
            (e.g. ``"expired"``).
        on_expire_callback: Optional async callback invoked after each
            record is transitioned.  Receives the full record dict.
    """

    model_name: str
    status_field: str
    expires_field: str
    active_status: str
    expired_status: str
    on_expire_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None


@dataclass
class ExpiryResult:
    """Summary returned by a single ``poll()`` cycle.

    Attributes:
        total_expired: Number of records transitioned across all models.
        per_model: Mapping from model name to the count expired in that
            model during this cycle.
        errors: Number of individual record transitions that failed.
    """

    total_expired: int = 0
    per_model: dict[str, int] = field(default_factory=dict)
    errors: int = 0


class ExpiryScheduler:
    """Background polling service that expires time-limited records.

    Thread-safe: handler registration is protected by a lock.  The
    background loop runs in an ``asyncio.Task`` and is safe to start
    from any coroutine.

    Args:
        db: DataFlow instance for Express CRUD operations.
    """

    def __init__(self, db: DataFlow) -> None:
        self._db = db
        self._handlers: list[ExpiryHandler] = []
        self._lock = threading.Lock()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register_handler(
        self,
        model_name: str,
        status_field: str,
        expires_field: str,
        active_status: str,
        expired_status: str,
        on_expire_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        """Register a model for expiry polling.

        Args:
            model_name: DataFlow model name.
            status_field: Name of the status field on the model.
            expires_field: Name of the ISO 8601 expiry timestamp field.
            active_status: Status value that marks records as eligible.
            expired_status: Status value to set when a record expires.
            on_expire_callback: Optional async callback invoked after
                each record transition, receiving the record dict.

        Raises:
            ValueError: On empty *model_name*, *status_field*, or
                *expires_field*.
        """
        if not model_name:
            raise ValueError("model_name must not be empty")
        if not status_field:
            raise ValueError("status_field must not be empty")
        if not expires_field:
            raise ValueError("expires_field must not be empty")

        handler = ExpiryHandler(
            model_name=model_name,
            status_field=status_field,
            expires_field=expires_field,
            active_status=active_status,
            expired_status=expired_status,
            on_expire_callback=on_expire_callback,
        )

        with self._lock:
            self._handlers.append(handler)

        logger.info(
            "Registered expiry handler: model=%s active=%s -> expired=%s (field=%s)",
            model_name,
            active_status,
            expired_status,
            expires_field,
        )

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    async def poll(self) -> ExpiryResult:
        """Run one expiry cycle across all registered handlers.

        Queries each registered model for records whose *status_field*
        equals *active_status* and whose *expires_field* is in the past,
        then transitions them to *expired_status*.

        Returns:
            An ``ExpiryResult`` summarising the cycle.
        """
        result = ExpiryResult()

        with self._lock:
            handlers = list(self._handlers)

        now = datetime.now(UTC)

        for handler in handlers:
            model_expired = 0
            try:
                records = await self._db.express.list(
                    handler.model_name,
                    {handler.status_field: handler.active_status},
                    limit=10000,
                )

                for record in records:
                    expires_value = record.get(handler.expires_field)
                    if not expires_value:
                        # No expiry timestamp -- record never expires.
                        continue

                    # Parse to datetime for robust comparison across
                    # timezone formats (Z vs +00:00 vs naive).
                    try:
                        expires_dt = datetime.fromisoformat(str(expires_value))
                        if expires_dt.tzinfo is None:
                            expires_dt = expires_dt.replace(tzinfo=UTC)
                    except (ValueError, TypeError):
                        logger.warning(
                            "Unparseable expires_at %r in %s record %s — skipping",
                            expires_value,
                            handler.model_name,
                            record.get("id", "?"),
                        )
                        continue

                    if expires_dt >= now:
                        # Not yet expired.
                        continue

                    record_id = record.get("id", "")
                    try:
                        # Re-read to verify status hasn't changed since the
                        # batch query (H6 fix: prevent overwriting legitimate
                        # state transitions like "ended_early" or "acknowledged")
                        fresh = await self._db.express.read(handler.model_name, record_id)
                        if (
                            not fresh
                            or fresh.get("found") is False
                            or fresh.get(handler.status_field) != handler.active_status
                        ):
                            continue  # Status changed since batch read — skip

                        await self._db.express.update(
                            handler.model_name,
                            record_id,
                            {handler.status_field: handler.expired_status},
                        )
                        model_expired += 1

                        logger.info(
                            "Expired %s record %s (expires_at=%s, now=%s)",
                            handler.model_name,
                            record_id,
                            expires_dt.isoformat(),
                            now.isoformat(),
                        )

                        # Fire callback if registered.
                        if handler.on_expire_callback is not None:
                            try:
                                await handler.on_expire_callback(record)
                            except Exception:
                                logger.exception(
                                    "on_expire_callback failed for %s record %s",
                                    handler.model_name,
                                    record_id,
                                )
                                # Callback failure does not prevent
                                # the record from being marked expired.
                    except Exception:
                        logger.exception(
                            "Failed to expire %s record %s",
                            handler.model_name,
                            record_id,
                        )
                        result.errors += 1

            except Exception:
                logger.exception(
                    "Failed to query %s for expired records",
                    handler.model_name,
                )
                result.errors += 1

            result.per_model[handler.model_name] = model_expired
            result.total_expired += model_expired

        if result.total_expired > 0:
            logger.info(
                "Expiry poll complete: %d record(s) expired across %d model(s), %d error(s)",
                result.total_expired,
                len(handlers),
                result.errors,
            )

        return result

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    async def start(self, interval_seconds: float = 60.0) -> None:
        """Start the background polling loop.

        The loop calls ``poll()`` every *interval_seconds* until
        ``stop()`` is called.  Safe to call multiple times -- subsequent
        calls are no-ops while the loop is running.

        Args:
            interval_seconds: Seconds between poll cycles. Must be
                positive.

        Raises:
            ValueError: If *interval_seconds* is not positive.
        """
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        if self._running:
            logger.warning("ExpiryScheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop(interval_seconds))
        logger.info(
            "ExpiryScheduler started (interval=%ss, handlers=%d)",
            interval_seconds,
            len(self._handlers),
        )

    async def stop(self) -> None:
        """Cancel the background polling loop.

        Idempotent -- safe to call when the loop is not running.
        """
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("ExpiryScheduler stopped")

    @property
    def running(self) -> bool:
        """Whether the background loop is currently active."""
        return self._running

    async def _loop(self, interval_seconds: float) -> None:
        """Internal loop that runs ``poll()`` at regular intervals."""
        try:
            while self._running:
                try:
                    await self.poll()
                except Exception:
                    logger.exception("Unhandled error in expiry poll cycle")
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            # Normal shutdown via stop().
            pass
        finally:
            self._running = False
