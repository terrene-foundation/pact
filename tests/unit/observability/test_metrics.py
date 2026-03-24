# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Prometheus metrics (Task 5025).

Validates that:
- care_requests_total Counter exists and increments
- care_request_duration_seconds Histogram exists and observes values
- care_approval_queue_depth Gauge exists and can be set
- care_active_agents Gauge exists and can be set
- All metrics are properly typed (Counter, Histogram, Gauge)
- GET /metrics endpoint returns Prometheus text format
- GET /metrics does NOT require authentication
"""

import pytest

from pact_platform.use.observability.metrics import (
    ACTIVE_AGENTS,
    APPROVAL_QUEUE_DEPTH,
    REQUEST_DURATION,
    REQUESTS_TOTAL,
    get_metrics_endpoint_response,
)


class TestRequestsTotalCounter:
    """care_requests_total must be a Counter that tracks total API requests."""

    def test_requests_total_exists(self):
        """The REQUESTS_TOTAL metric must be defined."""
        assert REQUESTS_TOTAL is not None

    def test_requests_total_has_correct_name(self):
        """The Counter must be named care_requests_total."""
        # prometheus_client Counter strips _total suffix from _name internally
        assert "care_requests" in REQUESTS_TOTAL._name

    def test_requests_total_can_increment(self):
        """The Counter must support labels and incrementing."""
        # Counters support .labels().inc() — just verify it does not raise
        REQUESTS_TOTAL.labels(method="GET", endpoint="/health", status="200").inc()


class TestRequestDurationHistogram:
    """care_request_duration_seconds must be a Histogram for request latency."""

    def test_request_duration_exists(self):
        """The REQUEST_DURATION metric must be defined."""
        assert REQUEST_DURATION is not None

    def test_request_duration_has_correct_name(self):
        """The Histogram must be named care_request_duration_seconds."""
        assert REQUEST_DURATION._name == "care_request_duration_seconds"

    def test_request_duration_can_observe(self):
        """The Histogram must support observing duration values."""
        REQUEST_DURATION.labels(method="GET", endpoint="/health").observe(0.042)


class TestApprovalQueueDepthGauge:
    """care_approval_queue_depth must be a Gauge for approval queue size."""

    def test_approval_queue_depth_exists(self):
        """The APPROVAL_QUEUE_DEPTH metric must be defined."""
        assert APPROVAL_QUEUE_DEPTH is not None

    def test_approval_queue_depth_has_correct_name(self):
        """The Gauge must be named care_approval_queue_depth."""
        assert APPROVAL_QUEUE_DEPTH._name == "care_approval_queue_depth"

    def test_approval_queue_depth_can_set(self):
        """The Gauge must support setting a value."""
        APPROVAL_QUEUE_DEPTH.set(5)

    def test_approval_queue_depth_can_inc_dec(self):
        """The Gauge must support inc() and dec()."""
        APPROVAL_QUEUE_DEPTH.set(0)
        APPROVAL_QUEUE_DEPTH.inc()
        APPROVAL_QUEUE_DEPTH.dec()


class TestActiveAgentsGauge:
    """care_active_agents must be a Gauge for active agent count."""

    def test_active_agents_exists(self):
        """The ACTIVE_AGENTS metric must be defined."""
        assert ACTIVE_AGENTS is not None

    def test_active_agents_has_correct_name(self):
        """The Gauge must be named care_active_agents."""
        assert ACTIVE_AGENTS._name == "care_active_agents"

    def test_active_agents_can_set(self):
        """The Gauge must support setting a value."""
        ACTIVE_AGENTS.set(3)


class TestMetricsEndpointResponse:
    """get_metrics_endpoint_response must return Prometheus text format."""

    def test_returns_string(self):
        """The response must be a string."""
        response = get_metrics_endpoint_response()
        assert isinstance(response, str)

    def test_contains_metric_names(self):
        """The response must contain the defined metric names."""
        # Increment a counter so it appears in output
        REQUESTS_TOTAL.labels(method="GET", endpoint="/test", status="200").inc()
        response = get_metrics_endpoint_response()
        assert "care_requests_total" in response
        assert "care_request_duration_seconds" in response
        assert "care_approval_queue_depth" in response
        assert "care_active_agents" in response

    def test_contains_help_lines(self):
        """The response must include HELP lines for each metric."""
        response = get_metrics_endpoint_response()
        assert "# HELP care_requests_total" in response
        assert "# HELP care_request_duration_seconds" in response
        assert "# HELP care_approval_queue_depth" in response
        assert "# HELP care_active_agents" in response

    def test_contains_type_lines(self):
        """The response must include TYPE lines for each metric."""
        response = get_metrics_endpoint_response()
        assert "# TYPE care_requests_total counter" in response
        assert "# TYPE care_request_duration_seconds histogram" in response
        assert "# TYPE care_approval_queue_depth gauge" in response
        assert "# TYPE care_active_agents gauge" in response


class TestMetricsEndpointInServer:
    """GET /metrics must be mounted in the FastAPI server and not require auth."""

    @pytest.fixture
    def client(self):
        """Create a test client for the PACT API."""
        import os

        os.environ.setdefault("PACT_DEV_MODE", "true")

        from httpx import ASGITransport, AsyncClient

        from pact_platform.build.config.env import load_env_config
        from pact_platform.use.api.server import create_app

        env_config = load_env_config(load_dotenv=False)
        app = create_app(env_config=env_config)
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_200(self, client):
        """GET /metrics must return HTTP 200."""
        response = await client.get("/metrics")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint_no_auth_required(self, client):
        """GET /metrics must NOT require authentication (standard for Prometheus scraping)."""
        # No Authorization header — should still return 200
        response = await client.get("/metrics")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_prometheus_content_type(self, client):
        """GET /metrics must return text/plain content type (Prometheus format)."""
        response = await client.get("/metrics")
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_metric_data(self, client):
        """GET /metrics must return parseable Prometheus metrics."""
        response = await client.get("/metrics")
        body = response.text
        assert "care_requests_total" in body or "care_active_agents" in body
