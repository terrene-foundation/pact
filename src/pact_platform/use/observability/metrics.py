# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Prometheus metrics for the PACT — Task 5025.

Defines four core metrics for monitoring the PACT:
- care_requests_total: Counter tracking total API requests by method, endpoint, status
- care_request_duration_seconds: Histogram measuring request latency
- care_approval_queue_depth: Gauge showing current approval queue size
- care_active_agents: Gauge showing number of active agents

The metrics endpoint (GET /metrics) is mounted in the FastAPI server and
does NOT require authentication — this is standard practice for Prometheus
scraping endpoints.

Usage:
    from pact_platform.use.observability.metrics import (
        REQUESTS_TOTAL,
        REQUEST_DURATION,
        APPROVAL_QUEUE_DEPTH,
        ACTIVE_AGENTS,
    )

    # Increment request counter
    REQUESTS_TOTAL.labels(method="GET", endpoint="/health", status="200").inc()

    # Observe request duration
    REQUEST_DURATION.labels(method="GET", endpoint="/health").observe(0.042)

    # Set gauge values
    APPROVAL_QUEUE_DEPTH.set(5)
    ACTIVE_AGENTS.set(3)
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ---------------------------------------------------------------------------
# Metrics definitions
# ---------------------------------------------------------------------------

REQUESTS_TOTAL = Counter(
    name="care_requests_total",
    documentation="Total API requests by method, endpoint, and status",
    labelnames=["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    name="care_request_duration_seconds",
    documentation="Request latency in seconds",
    labelnames=["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

APPROVAL_QUEUE_DEPTH = Gauge(
    name="care_approval_queue_depth",
    documentation="Current number of held actions awaiting approval",
)

ACTIVE_AGENTS = Gauge(
    name="care_active_agents",
    documentation="Number of currently active agents",
)


# ---------------------------------------------------------------------------
# Endpoint response generator
# ---------------------------------------------------------------------------


def get_metrics_endpoint_response() -> str:
    """Generate Prometheus text format output for the /metrics endpoint.

    Returns:
        Prometheus exposition format as a string.
    """
    return generate_latest().decode("utf-8")


def get_metrics_content_type() -> str:
    """Return the content type for Prometheus metrics responses.

    Returns:
        The Prometheus content type string (text/plain with version parameter).
    """
    return CONTENT_TYPE_LATEST
