# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Notification delivery abstraction -- Protocol and webhook base class.

Provides:
- ``NotificationAdapter``: runtime-checkable Protocol for any notification backend
- ``WebhookAdapterBase``: shared webhook delivery with retry, rate limiting, and
  HMAC-SHA256 payload signing

All adapters (Slack, Discord, Teams) inherit from ``WebhookAdapterBase`` and
override ``_format_payload()`` to produce platform-specific message structures.

Usage:
    from pact_platform.integrations.notification_base import WebhookAdapterBase

    class MyAdapter(WebhookAdapterBase):
        def _format_payload(self, event_type: str, payload: dict) -> dict:
            return {"text": f"[{event_type}] {payload}"}
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import socket
import time
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

__all__ = [
    "NotificationAdapter",
    "WebhookAdapterBase",
    "validate_webhook_url",
]


@runtime_checkable
class NotificationAdapter(Protocol):
    """Protocol for notification delivery adapters.

    Any class with a matching ``send`` coroutine satisfies this protocol
    at runtime (``isinstance`` check) thanks to ``@runtime_checkable``.
    """

    async def send(self, event_type: str, payload: dict) -> None:
        """Deliver a governance event notification.

        Args:
            event_type: The governance event category (e.g. ``HELD``, ``BLOCKED``).
            payload: Event details as a JSON-serialisable dict.
        """
        ...


# ---------------------------------------------------------------------------
# SSRF prevention -- per rules/pact-governance.md PR2
# ---------------------------------------------------------------------------

# Private and reserved IP ranges that MUST NOT be targeted by webhooks.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("0.0.0.0/8"),  # "This" network
    ipaddress.ip_network("100.64.0.0/10"),  # Shared address space
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address falls within a blocked (private/reserved) range.

    Args:
        ip_str: IP address as a string.

    Returns:
        True if the address is private/reserved and should be blocked.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        # If we can't parse it, block it (fail-closed)
        return True

    for network in _BLOCKED_NETWORKS:
        if addr in network:
            return True
    return False


def validate_webhook_url(url: str) -> None:
    """Validate a webhook URL against SSRF attacks.

    Checks:
    1. URL scheme must be https:// (http:// only allowed for localhost in tests
       via explicit PACT_ALLOW_HTTP_WEBHOOKS env var, not implemented here).
    2. Hostname must resolve to a public IP address.
    3. Resolved IP must not fall within private/reserved ranges.

    Args:
        url: The webhook URL to validate.

    Raises:
        ValueError: If the URL is not safe for webhook delivery.
    """
    parsed = urlparse(url)

    # Scheme validation -- only HTTPS for production webhooks
    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Webhook URL must use https:// scheme, got {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Webhook URL must have a valid hostname")

    # Block obviously dangerous hostnames
    _blocked_hostnames = {"localhost", "127.0.0.1", "[::1]", "0.0.0.0"}
    if hostname.lower() in _blocked_hostnames:
        raise ValueError(
            f"Webhook URL must not target local/private hosts, " f"got hostname {hostname!r}"
        )

    # DNS resolution check -- resolve the hostname and verify the IP
    try:
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError(f"Webhook URL hostname {hostname!r} could not be resolved")

    for family, socktype, proto, canonname, sockaddr in resolved_ips:
        ip_str = sockaddr[0]
        if _is_private_ip(ip_str):
            raise ValueError(
                f"Webhook URL hostname {hostname!r} resolves to private/reserved "
                f"IP address {ip_str}. Webhook targets must be public endpoints."
            )


# ---------------------------------------------------------------------------
# Token-bucket rate limiter (no external dependencies)
# ---------------------------------------------------------------------------


class _TokenBucket:
    """Simple token-bucket rate limiter using ``time.monotonic()``.

    Not thread-safe -- designed for single-threaded async contexts. Each
    ``consume()`` call refills tokens based on elapsed time, then tries to
    consume one token. Returns ``True`` if the request is allowed.

    Args:
        rate_per_minute: Maximum requests per minute.
    """

    def __init__(self, rate_per_minute: int) -> None:
        self._rate = rate_per_minute
        self._tokens = float(rate_per_minute)
        self._max_tokens = float(rate_per_minute)
        self._last_refill = time.monotonic()

    def consume(self) -> bool:
        """Try to consume one token.

        Returns:
            ``True`` if the request is allowed, ``False`` if rate-limited.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now

        # Refill: tokens_per_second * elapsed
        self._tokens = min(
            self._max_tokens,
            self._tokens + (self._rate / 60.0) * elapsed,
        )

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


# ---------------------------------------------------------------------------
# WebhookAdapterBase -- shared delivery logic
# ---------------------------------------------------------------------------


class WebhookAdapterBase:
    """Base class for webhook notification adapters.

    Provides:
    - SSRF prevention (validates webhook URL against private IP ranges)
    - HMAC-SHA256 payload signing (when ``secret`` is provided)
    - Exponential backoff retry on transient HTTP failures
    - Token-bucket rate limiting (no external dependencies)

    Subclasses override ``_format_payload()`` to produce platform-specific
    message bodies. The ``send()`` method handles serialisation, signing,
    retry, and rate limiting.

    Args:
        webhook_url: Target webhook endpoint URL.
        secret: Shared secret for HMAC-SHA256 payload signing. Empty string
            disables signing.
        max_retries: Maximum number of delivery attempts (includes the initial
            attempt). Must be >= 1.
        rate_limit_per_minute: Maximum webhook deliveries per minute. Must be >= 1.
        skip_url_validation: If True, skip SSRF validation (for testing only).
    """

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        max_retries: int = 3,
        rate_limit_per_minute: int = 60,
        skip_url_validation: bool = False,
    ) -> None:
        if not webhook_url:
            raise ValueError(
                "webhook_url is required. Cannot create a webhook adapter "
                "without a delivery target."
            )
        if max_retries < 1:
            raise ValueError(f"max_retries must be >= 1, got {max_retries}")
        if rate_limit_per_minute < 1:
            raise ValueError(f"rate_limit_per_minute must be >= 1, got {rate_limit_per_minute}")

        # H1 fix: SSRF prevention -- validate URL before storing
        if not skip_url_validation:
            validate_webhook_url(webhook_url)

        self._webhook_url = webhook_url
        self._secret = secret
        self._max_retries = max_retries
        self._bucket = _TokenBucket(rate_limit_per_minute)

    async def send(self, event_type: str, payload: dict) -> None:
        """Send a governance event notification with retry and rate limiting.

        Formats the payload via ``_format_payload()``, serialises to JSON,
        computes an optional HMAC-SHA256 signature, and delivers via httpx
        with exponential backoff.

        Args:
            event_type: The governance event category.
            payload: Event details dict.

        Raises:
            RuntimeError: If delivery fails after all retry attempts.
            RuntimeError: If the request is rate-limited.
        """
        if not self._bucket.consume():
            logger.warning(
                "Webhook rate-limited: url=%s event_type=%s",
                self._webhook_url,
                event_type,
            )
            raise RuntimeError(
                f"Rate limit exceeded for webhook {self._webhook_url}. " f"Event type: {event_type}"
            )

        formatted = self._format_payload(event_type, payload)

        try:
            import json

            body = json.dumps(formatted).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Failed to serialise payload for event '{event_type}': {exc}"
            ) from exc

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._secret:
            headers["X-Signature-256"] = f"sha256={self._sign_payload(body)}"

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                await self._deliver(body, headers)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s, ...
                    import asyncio

                    delay = 2**attempt
                    logger.warning(
                        "Webhook delivery attempt %d/%d failed (url=%s): %s. " "Retrying in %ds.",
                        attempt + 1,
                        self._max_retries,
                        self._webhook_url,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Webhook delivery failed after {self._max_retries} attempts "
            f"(url={self._webhook_url}): {last_exc}"
        )

    def _format_payload(self, event_type: str, payload: dict) -> dict:
        """Format the payload for the target platform.

        Override in subclasses to produce Slack Block Kit, Discord embeds,
        Teams Adaptive Cards, etc. The default implementation wraps the
        event in a generic envelope.

        Args:
            event_type: The governance event category.
            payload: Event details dict.

        Returns:
            Platform-specific message body as a dict.
        """
        return {
            "event_type": event_type,
            "payload": payload,
        }

    def _sign_payload(self, body: bytes) -> str:
        """Compute HMAC-SHA256 signature for webhook verification.

        Uses ``hmac.compare_digest``-compatible hex output. The receiver
        should recompute the HMAC and compare using ``hmac.compare_digest()``
        to avoid timing side-channels.

        Args:
            body: Raw JSON body bytes.

        Returns:
            Hex-encoded HMAC-SHA256 digest.
        """
        return hmac.new(
            self._secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

    async def _deliver(self, body: bytes, headers: dict[str, str]) -> None:
        """Send the HTTP POST request via httpx.

        Args:
            body: Serialised JSON body.
            headers: HTTP headers including Content-Type and optional signature.

        Raises:
            httpx.HTTPStatusError: If the server returns a 4xx/5xx response.
            httpx.TransportError: On network-level failures.
        """
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "httpx is required for webhook delivery. " "Install it with: pip install httpx"
            ) from exc

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self._webhook_url,
                content=body,
                headers=headers,
            )
            response.raise_for_status()

    @staticmethod
    def verify_signature(
        body: bytes,
        secret: str,
        received_signature: str,
    ) -> bool:
        """Verify an incoming webhook's HMAC-SHA256 signature.

        Uses ``hmac.compare_digest`` for constant-time comparison to prevent
        timing side-channel attacks (per rules/trust-plane-security.md Rule MUST NOT 1).

        Args:
            body: Raw request body bytes.
            secret: Shared secret for HMAC computation.
            received_signature: The ``sha256=<hex>`` signature from the header.

        Returns:
            ``True`` if the signature is valid.
        """
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        # Strip "sha256=" prefix if present
        received_hex = received_signature
        if received_hex.startswith("sha256="):
            received_hex = received_hex[7:]

        return hmac.compare_digest(expected, received_hex)
