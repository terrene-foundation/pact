# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""FastAPI server for the PACT.

Mounts all PactAPI handlers (Phase 1, M18 dashboard, and M36 bridge
management endpoints) as FastAPI routes. Includes CORS middleware for
frontend development, a health check endpoint, a readiness probe,
WebSocket authentication, and graceful shutdown handling.

Usage:
    python -m pact.use.api.server
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

import pact
from pact_platform import __version__ as _platform_version
from pact_platform.build.config.env import EnvConfig, load_env_config
from pact_platform.build.workspace.bridge import BridgeManager
from pact_platform.build.workspace.models import WorkspaceRegistry
from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.use.api.endpoints import ApiResponse, PactAPI
from pact_platform.use.api.events import event_bus
from pact_platform.use.api.shutdown import ShutdownManager
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.registry import AgentRegistry

logger = logging.getLogger(__name__)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds a configurable maximum.

    Returns 413 Payload Too Large with an informative JSON body when the
    declared Content-Length exceeds the limit. The limit defaults to 1MB
    (1048576 bytes) and can be overridden via the ``PACT_MAX_BODY_SIZE``
    environment variable.
    """

    def __init__(self, app, max_body_size: int = 1_048_576) -> None:  # noqa: ANN001
        super().__init__(app)
        self._max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        """Check Content-Length and reject oversized requests."""
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid Content-Length header",
                        "detail": f"Content-Length must be a valid integer, got: {content_length!r}",
                    },
                )
            if length > self._max_body_size:
                logger.warning(
                    "Request body too large: Content-Length=%d exceeds limit=%d for %s %s",
                    length,
                    self._max_body_size,
                    request.method,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Payload Too Large",
                        "detail": (
                            f"Request body size ({length} bytes) exceeds the maximum "
                            f"allowed size ({self._max_body_size} bytes)"
                        ),
                    },
                )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security response headers to every HTTP response.

    Headers applied:
    - Content-Security-Policy: restricts resource loading to same origin
    - X-Frame-Options: prevents clickjacking via iframe embedding
    - X-Content-Type-Options: prevents MIME-type sniffing
    - Referrer-Policy: limits referrer information leakage
    - Permissions-Policy: disables camera, microphone, geolocation
    """

    _SECURITY_HEADERS: dict[str, str] = {
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-XSS-Protection": "0",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        """Process request and attach security headers to the response."""
        response: Response = await call_next(request)
        for header, value in self._SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


# Module-level env config, loaded once on first access
_env_config: EnvConfig | None = None


def _get_env_config() -> EnvConfig:
    """Get or load the environment configuration."""
    global _env_config
    if _env_config is None:
        _env_config = load_env_config()
    return _env_config


def _build_platform_api() -> PactAPI:
    """Build a PactAPI instance with default components.

    In production, these components would be populated from configuration
    and persistence layers. For development, empty/default instances are
    created.

    Logs a warning that the API is running without seed data, since
    dashboard endpoints (verification_stats, dashboard_trends, etc.)
    will return empty results.

    Returns:
        A fully wired PactAPI instance.
    """
    logger.warning(
        "Building PactAPI without seed data — dashboard endpoints will "
        "return empty results. Run 'python scripts/run_seeded_server.py' for "
        "a fully populated demo experience."
    )
    registry = AgentRegistry()
    approval_queue = ApprovalQueue()
    cost_tracker = CostTracker()
    workspace_registry = WorkspaceRegistry()
    bridge_manager = BridgeManager()

    return PactAPI(
        registry=registry,
        approval_queue=approval_queue,
        cost_tracker=cost_tracker,
        workspace_registry=workspace_registry,
        bridge_manager=bridge_manager,
        envelope_registry={},
        verification_stats={},
    )


# Module-level API instance, created at import time for simple wiring.
# Override via create_app(platform_api=...) for testing or custom setups.
_default_api: PactAPI | None = None


def create_app(
    platform_api: PactAPI | None = None,
    env_config: EnvConfig | None = None,
    trust_store: Any | None = None,
    dm_runner: Any | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        platform_api: Optional PactAPI instance. When None, a default
            instance is created with empty components.
        env_config: Optional EnvConfig. When None, loaded from environment.
        trust_store: Optional trust store for readiness probe. When
            provided, the ``/ready`` endpoint checks store health.
        dm_runner: Optional DMTeamRunner instance for DM team endpoints.
            When provided, mounts POST/GET /api/v1/dm/tasks and
            GET /api/v1/dm/status endpoints.

    Returns:
        Configured FastAPI application with all routes mounted.
    """
    global _default_api

    cfg = env_config or _get_env_config()

    if platform_api is not None:
        _default_api = platform_api
    elif _default_api is None:
        _default_api = _build_platform_api()

    api = _default_api

    # Shutdown manager for graceful connection cleanup (I8)
    shutdown_manager = ShutdownManager()

    # Rate limiter (M35-3503) — key by remote IP address
    limiter = Limiter(key_func=get_remote_address)

    app = FastAPI(
        title="PACT API",
        description=(
            "Governed operational model for running organizations with AI agents "
            "under EATP trust governance, CO methodology, and CARE philosophy."
        ),
        version="0.1.0",
    )

    # Attach limiter to app state (required by slowapi)
    app.state.limiter = limiter

    # Rate limit exceeded handler — returns 429 with JSON body
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "detail": str(exc.detail)},
        )

    # SlowAPI rate limiting middleware
    app.add_middleware(SlowAPIMiddleware)

    # Security response headers middleware (M35-3504)
    app.add_middleware(SecurityHeadersMiddleware)

    # L6: Request body size limit middleware — rejects oversized payloads with 413
    _max_body_size_str = os.environ.get("PACT_MAX_BODY_SIZE", "")
    _max_body_size = 1_048_576  # Default: 1MB
    if _max_body_size_str:
        try:
            _max_body_size = int(_max_body_size_str)
        except ValueError:
            logger.warning(
                "Invalid PACT_MAX_BODY_SIZE='%s', using default %d bytes",
                _max_body_size_str,
                _max_body_size,
            )
    app.add_middleware(BodySizeLimitMiddleware, max_body_size=_max_body_size)

    # Store shutdown manager on app state for access and testing
    app.state.shutdown_manager = shutdown_manager

    # L5: CORS origin validation — in production, require HTTPS and reject wildcard
    cors_origins = list(cfg.pact_cors_origins)
    if cfg.is_production:
        validated_origins: list[str] = []
        rejected_origins: list[str] = []
        for origin in cors_origins:
            if origin == "*" or not origin.startswith("https://"):
                rejected_origins.append(origin)
            else:
                validated_origins.append(origin)
        if rejected_origins:
            logger.warning(
                "CORS origins rejected in production mode (must use HTTPS, no wildcard): %s. "
                "Falling back to validated origins only: %s",
                rejected_origins,
                validated_origins if validated_origins else "(empty list)",
            )
        cors_origins = validated_origins

    # CORS middleware — restricted methods and headers (H4)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Authentication: Firebase ID token (primary) + static PACT_API_TOKEN (fallback)
    _api_token = cfg.pact_api_token
    _bearer_scheme = HTTPBearer(auto_error=False)

    # Lazy-import Firebase verification to avoid hard dependency
    _firebase_verify = None

    def _get_firebase_verify():  # noqa: ANN202
        nonlocal _firebase_verify
        if _firebase_verify is None:
            try:
                from pact_platform.trust.auth.firebase_admin import verify_firebase_id_token

                _firebase_verify = verify_firebase_id_token
            except ImportError:
                _firebase_verify = lambda _token: None  # noqa: E731
        return _firebase_verify

    async def verify_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    ) -> str:
        """Verify bearer token and return the authenticated identity.

        Authentication is checked in this order:
        1. Firebase ID token -- verified via Firebase Admin SDK. Returns
           the user's UID as identity. Used by the web dashboard SSO.
        2. Static PACT_API_TOKEN -- compared via constant-time comparison.
           Used by CLI, scripts, and API-only access.
        3. Dev mode bypass -- when PACT_API_TOKEN is not set (empty),
           auth is disabled for local development.

        Returns the authenticated identity string (Firebase UID, "authenticated",
        or "anonymous" in dev mode).
        """
        if not _api_token and not credentials:
            # No token configured and no credentials provided — dev mode
            return "anonymous"

        if credentials is None:
            if not _api_token:
                return "anonymous"
            raise HTTPException(status_code=401, detail="Invalid or missing API token")

        bearer_token = credentials.credentials

        # Method 1: Try Firebase ID token verification
        firebase_verify = _get_firebase_verify()
        firebase_user = firebase_verify(bearer_token)
        if firebase_user is not None:
            return f"firebase:{firebase_user['uid']}"

        # Method 2: Try static token comparison
        if _api_token and hmac.compare_digest(bearer_token, _api_token):
            return "authenticated"

        # Method 3: Dev mode bypass (no token configured)
        if not _api_token:
            return "anonymous"

        raise HTTPException(status_code=401, detail="Invalid or missing API token")

    # Rate limit values from config
    _rate_get = cfg.pact_rate_limit_get
    _rate_post = cfg.pact_rate_limit_post

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    @app.get("/health")
    @limiter.limit(_rate_get)
    async def health(request: Request) -> dict[str, Any]:
        """Health check endpoint for load balancers and monitoring.

        Returns service status, version, and component-level health.
        """
        return {
            "status": "healthy",
            "service": "pact",
            "version": _platform_version,
            "components": {
                "api": "ok",
                "trust_store": "ok",
                "database": "ok",
            },
        }

    # ------------------------------------------------------------------
    # Readiness probe (I2)
    # ------------------------------------------------------------------

    @app.get("/ready")
    @limiter.limit(_rate_get)
    async def readiness(request: Request) -> JSONResponse:
        """Readiness probe — checks whether the platform is ready to serve.

        Checks trust store accessibility when configured. Returns HTTP 200
        with ``{"status": "ready"}`` when healthy, or HTTP 503 with
        ``{"status": "not_ready", "reason": "..."}`` when not ready.
        """
        if trust_store is not None:
            try:
                is_healthy = trust_store.health_check()
                if not is_healthy:
                    return JSONResponse(
                        status_code=503,
                        content={
                            "status": "not_ready",
                            "reason": "Trust store health check failed",
                        },
                    )
            except Exception as exc:
                logger.warning("Readiness probe failed: trust store error: %s", exc)
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "not_ready",
                        "reason": "Trust store unreachable",
                    },
                )
        return JSONResponse(
            status_code=200,
            content={"status": "ready"},
        )

    # ------------------------------------------------------------------
    # Phase 1 endpoints
    # ------------------------------------------------------------------

    @app.get("/api/v1/teams")
    @limiter.limit(_rate_get)
    async def list_teams(request: Request, _token: str = Depends(verify_token)) -> ApiResponse:
        """List all active teams. Requires authentication."""
        return api.list_teams()

    @app.get("/api/v1/teams/{team_id}/agents")
    @limiter.limit(_rate_get)
    async def list_agents(
        request: Request, team_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """List agents in a team. Requires authentication."""
        return api.list_agents(team_id)

    @app.get("/api/v1/agents/{agent_id}/status")
    @limiter.limit(_rate_get)
    async def agent_status(
        request: Request, agent_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get agent status and posture. Requires authentication."""
        return api.agent_status(agent_id)

    @app.post("/api/v1/agents/{agent_id}/approve/{action_id}")
    @limiter.limit(_rate_post)
    async def approve_action(
        request: Request,
        agent_id: str,
        action_id: str,
        approver_id: str = Query(description="ID of the approving human"),
        reason: str = Query(default="", description="Reason for approval"),
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Approve a held action. Requires authentication."""
        return api.approve_action(agent_id, action_id, approver_id, reason)

    @app.post("/api/v1/agents/{agent_id}/reject/{action_id}")
    @limiter.limit(_rate_post)
    async def reject_action(
        request: Request,
        agent_id: str,
        action_id: str,
        approver_id: str = Query(description="ID of the rejecting human"),
        reason: str = Query(default="", description="Reason for rejection"),
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Reject a held action. Requires authentication."""
        return api.reject_action(agent_id, action_id, approver_id, reason)

    @app.get("/api/v1/held-actions")
    @limiter.limit(_rate_get)
    async def held_actions(request: Request, _token: str = Depends(verify_token)) -> ApiResponse:
        """List all pending approval actions. Requires authentication."""
        return api.held_actions()

    @app.get("/api/v1/cost/report")
    @limiter.limit(_rate_get)
    async def cost_report(
        request: Request,
        team_id: str | None = Query(default=None, description="Filter by team"),
        agent_id: str | None = Query(default=None, description="Filter by agent"),
        days: int = Query(default=30, ge=1, le=365, description="Number of days to include"),
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Get API cost report. Requires authentication."""
        return api.cost_report(team_id=team_id, agent_id=agent_id, days=days)

    # ------------------------------------------------------------------
    # M18 Dashboard endpoints
    # ------------------------------------------------------------------

    @app.get("/api/v1/trust-chains")
    @limiter.limit(_rate_get)
    async def list_trust_chains(
        request: Request, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """List all trust chains with status. Requires authentication."""
        return api.list_trust_chains()

    @app.get("/api/v1/trust-chains/{agent_id}")
    @limiter.limit(_rate_get)
    async def get_trust_chain_detail(
        request: Request, agent_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get trust chain detail for an agent. Requires authentication."""
        return api.get_trust_chain_detail(agent_id)

    @app.get("/api/v1/envelopes/{envelope_id}")
    @limiter.limit(_rate_get)
    async def get_envelope(
        request: Request, envelope_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get constraint envelope with all five CARE dimensions. Requires authentication."""
        return api.get_envelope(envelope_id)

    @app.get("/api/v1/workspaces")
    @limiter.limit(_rate_get)
    async def list_workspaces(request: Request, _token: str = Depends(verify_token)) -> ApiResponse:
        """List all workspaces with state and phase. Requires authentication."""
        return api.list_workspaces()

    @app.get("/api/v1/bridges")
    @limiter.limit(_rate_get)
    async def list_bridges(request: Request, _token: str = Depends(verify_token)) -> ApiResponse:
        """List all cross-functional bridges with status. Requires authentication."""
        return api.list_bridges()

    @app.get("/api/v1/verification/stats")
    @limiter.limit(_rate_get)
    async def verification_stats(
        request: Request, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get verification gradient counts by level. Requires authentication."""
        return api.verification_stats_report()

    @app.get("/api/v1/dashboard/trends")
    @limiter.limit(_rate_get)
    async def dashboard_trends(
        request: Request, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get 7-day verification gradient trends for sparklines. Requires authentication."""
        return api.dashboard_trends()

    @app.get("/api/v1/agents/{agent_id}/posture-history")
    @limiter.limit(_rate_get)
    async def posture_history(
        request: Request, agent_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get posture change history for an agent. Requires authentication."""
        return api.posture_history(agent_id)

    # ------------------------------------------------------------------
    # M42 Upgrade Evidence endpoint
    # ------------------------------------------------------------------

    @app.get("/api/v1/agents/{agent_id}/upgrade-evidence")
    @limiter.limit(_rate_get)
    async def upgrade_evidence(
        request: Request, agent_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get upgrade evidence for posture upgrade evaluation. Requires authentication."""
        return api.upgrade_evidence(agent_id)

    # ------------------------------------------------------------------
    # M36 Bridge management endpoints
    # ------------------------------------------------------------------

    @app.post("/api/v1/bridges")
    @limiter.limit(_rate_post)
    async def create_bridge(
        request: Request,
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Create a cross-functional bridge. Requires authentication."""
        body: dict[str, Any] = await request.json()
        return api.create_bridge(body)

    @app.get("/api/v1/bridges/team/{team_id}")
    @limiter.limit(_rate_get)
    async def list_bridges_by_team(
        request: Request,
        team_id: str,
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """List bridges for a specific team. Requires authentication."""
        return api.list_bridges_by_team(team_id)

    @app.get("/api/v1/bridges/{bridge_id}/audit")
    @limiter.limit(_rate_get)
    async def bridge_audit(
        request: Request,
        bridge_id: str,
        start_date: str | None = Query(default=None, description="ISO date filter start"),
        end_date: str | None = Query(default=None, description="ISO date filter end"),
        limit: int = Query(default=100, ge=1, le=1000, description="Max records"),
        offset: int = Query(default=0, ge=0, description="Pagination offset"),
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Get bridge audit trail. Requires authentication."""
        return api.bridge_audit(
            bridge_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/v1/bridges/{bridge_id}")
    @limiter.limit(_rate_get)
    async def get_bridge(
        request: Request,
        bridge_id: str,
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Get bridge detail by ID. Requires authentication."""
        return api.get_bridge(bridge_id)

    @app.put("/api/v1/bridges/{bridge_id}/approve")
    @limiter.limit(_rate_post)
    async def approve_bridge(
        request: Request,
        bridge_id: str,
        side: str = Query(description="'source' or 'target'"),
        approver_id: str = Query(description="ID of the approver"),
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Approve a bridge on source or target side. Requires authentication."""
        return api.approve_bridge(bridge_id, side, approver_id)

    @app.post("/api/v1/bridges/{bridge_id}/suspend")
    @limiter.limit(_rate_post)
    async def suspend_bridge(
        request: Request,
        bridge_id: str,
        reason: str = Query(description="Reason for suspension"),
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Suspend an active bridge. Requires authentication."""
        return api.suspend_bridge_action(bridge_id, reason)

    @app.post("/api/v1/bridges/{bridge_id}/close")
    @limiter.limit(_rate_post)
    async def close_bridge(
        request: Request,
        bridge_id: str,
        reason: str = Query(description="Reason for closure"),
        _token: str = Depends(verify_token),
    ) -> ApiResponse:
        """Close a bridge. Requires authentication."""
        return api.close_bridge_action(bridge_id, reason)

    # ------------------------------------------------------------------
    # M13 ShadowEnforcer endpoints
    # ------------------------------------------------------------------

    @app.get("/api/v1/shadow/{agent_id}/metrics")
    @limiter.limit(_rate_get)
    async def shadow_metrics(
        request: Request, agent_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get shadow enforcement metrics for an agent. Requires authentication."""
        return api.shadow_metrics(agent_id)

    @app.get("/api/v1/shadow/{agent_id}/report")
    @limiter.limit(_rate_get)
    async def shadow_report(
        request: Request, agent_id: str, _token: str = Depends(verify_token)
    ) -> ApiResponse:
        """Get shadow enforcement posture upgrade report. Requires authentication."""
        return api.shadow_report(agent_id)

    # ------------------------------------------------------------------
    # WebSocket for real-time updates
    # ------------------------------------------------------------------

    _max_ws_subscribers = cfg.pact_max_ws_subscribers

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time platform event streaming.

        Authentication methods (checked in order):
        1. Sec-WebSocket-Protocol header with ``bearer.<token>`` subprotocol
           (preferred — token not in URL/logs)
        2. Query parameter ``?token=...`` (fallback — logged as warning)

        When PACT_API_TOKEN is not set and dev mode is enabled, auth is
        skipped (same policy as REST endpoints).

        Clients connect to /ws and receive JSON-encoded PlatformEvent
        messages as they occur. The connection remains open until the
        client disconnects. Max subscribers limited to prevent resource
        exhaustion (H5).
        """
        # RT11-H2 / RT13: Prefer Sec-WebSocket-Protocol header over query param
        _ws_authed = False
        if _api_token:
            # Method 1: Check Sec-WebSocket-Protocol header for bearer.<token>
            protocols = websocket.headers.get("sec-websocket-protocol", "")
            for protocol in protocols.split(","):
                protocol = protocol.strip()
                if protocol.startswith("bearer."):
                    header_token = protocol[7:]  # strip "bearer." prefix
                    if hmac.compare_digest(header_token, _api_token):
                        _ws_authed = True
                        break

            # Method 2: Fallback to query param (with warning)
            if not _ws_authed:
                ws_token = websocket.query_params.get("token", "")
                if ws_token and hmac.compare_digest(ws_token, _api_token):
                    _ws_authed = True
                    logger.warning(
                        "WebSocket auth via query parameter — consider using "
                        "Sec-WebSocket-Protocol: bearer.<token> instead to "
                        "avoid token exposure in URL/logs"
                    )

            if not _ws_authed:
                await websocket.close(code=4001, reason="Authentication required")
                return

        # I8: Reject new connections during shutdown
        if not shutdown_manager.should_accept_connection():
            await websocket.close(code=1001, reason="Server shutting down")
            return

        if event_bus.subscriber_count >= _max_ws_subscribers:
            await websocket.close(code=1013, reason="Too many subscribers")
            return
        await websocket.accept()
        shutdown_manager.register_connection(websocket)
        queue = await event_bus.subscribe()
        logger.info("WebSocket client connected (subscribers: %d)", event_bus.subscriber_count)
        try:
            while True:
                event = await queue.get()
                await websocket.send_text(event.to_json())
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        finally:
            shutdown_manager.unregister_connection(websocket)
            await event_bus.unsubscribe(queue)

    # ------------------------------------------------------------------
    # M23 DM Team endpoints (Task 5052)
    # ------------------------------------------------------------------

    if dm_runner is not None:

        @app.post("/api/v1/dm/tasks")
        @limiter.limit(_rate_post)
        async def dm_submit_task(
            request: Request,
            _token: str = Depends(verify_token),
        ) -> ApiResponse:
            """Submit a DM team task. Auto-routes by keyword matching."""
            body: dict[str, Any] = await request.json()
            description = body.get("description", "")
            target_agent = body.get("target_agent")

            if not description:
                return ApiResponse(
                    status="error",
                    error="Missing required field 'description' in request body",
                )

            # L3-FIX: Reject oversized task descriptions to prevent memory exhaustion.
            if len(description) > 10000:
                return ApiResponse(
                    status="error",
                    error="Task description exceeds maximum length of 10,000 characters",
                )

            # Validate target agent if specified
            if target_agent and target_agent not in dm_runner.registered_agents:
                return ApiResponse(
                    status="error",
                    error=(
                        f"Agent '{target_agent}' is not a valid DM team agent. "
                        f"Available: {dm_runner.registered_agents}"
                    ),
                )

            result = dm_runner.submit_task(
                description=description,
                target_agent=target_agent,
            )

            task_id = result.metadata.get("task_id", "")
            routed_to = result.metadata.get("routed_to", "")

            if result.error and not result.metadata.get("held"):
                return ApiResponse(
                    status="ok",
                    data={
                        "task_id": task_id,
                        "routed_to": routed_to,
                        "status": "blocked" if "BLOCKED" in (result.error or "") else "error",
                        "error": result.error,
                        "verification_level": result.metadata.get("verification_level"),
                    },
                )

            return ApiResponse(
                status="ok",
                data={
                    "task_id": task_id,
                    "routed_to": routed_to,
                    "status": "held" if result.metadata.get("held") else "completed",
                    "output": result.output,
                    "verification_level": result.metadata.get("verification_level"),
                },
            )

        @app.get("/api/v1/dm/tasks/{task_id}")
        @limiter.limit(_rate_get)
        async def dm_get_task(
            request: Request,
            task_id: str,
            _token: str = Depends(verify_token),
        ) -> ApiResponse:
            """Get DM task result and lifecycle by task_id."""
            result = dm_runner.get_task_result(task_id)
            if result is None:
                return ApiResponse(
                    status="error",
                    error=f"Task '{task_id}' not found",
                )

            return ApiResponse(
                status="ok",
                data={
                    "task_id": task_id,
                    "output": result.output,
                    "error": result.error,
                    "verification_level": result.metadata.get("verification_level"),
                    "routed_to": result.metadata.get("routed_to"),
                    "lifecycle": result.metadata.get("lifecycle"),
                },
            )

        @app.get("/api/v1/dm/status")
        @limiter.limit(_rate_get)
        async def dm_status(
            request: Request,
            _token: str = Depends(verify_token),
        ) -> ApiResponse:
            """Get all 5 DM agents' postures and task stats."""
            stats = dm_runner.get_agent_stats()
            agents_data = []
            for agent_id in dm_runner.registered_agents:
                record = dm_runner.get_agent_record(agent_id)
                agent_stats = stats.get(agent_id, {})
                agents_data.append(
                    {
                        "agent_id": agent_id,
                        "name": record.name if record else agent_id,
                        "role": record.role if record else "",
                        "posture": record.current_posture if record else "unknown",
                        "status": record.status.value if record else "unknown",
                        "tasks_submitted": agent_stats.get("tasks_submitted", 0),
                        "tasks_completed": agent_stats.get("tasks_completed", 0),
                        "tasks_held": agent_stats.get("tasks_held", 0),
                        "tasks_blocked": agent_stats.get("tasks_blocked", 0),
                    }
                )

            return ApiResponse(
                status="ok",
                data={
                    "team_id": "dm-team",
                    "agents": agents_data,
                    "total_agents": len(agents_data),
                },
            )

        @app.get("/api/v1/shadow/{agent_id}/upgrade-recommendation")
        @limiter.limit(_rate_get)
        async def shadow_upgrade_recommendation(
            request: Request,
            agent_id: str,
            _token: str = Depends(verify_token),
        ) -> ApiResponse:
            """Get posture upgrade recommendation for an agent."""
            try:
                rec = dm_runner.get_upgrade_recommendation(agent_id)
                return ApiResponse(status="ok", data=rec)
            except KeyError as exc:
                logger.exception("get_upgrade_recommendation failed for agent_id=%s", agent_id)
                return ApiResponse(
                    status="error", error="Upgrade recommendation not found for agent"
                )

    # ------------------------------------------------------------------
    # Prometheus metrics endpoint (Task 5025)
    # ------------------------------------------------------------------

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(request: Request) -> Response:
        """Prometheus metrics endpoint — standard scraping target.

        Returns all registered metrics in Prometheus text exposition format.
        This endpoint does NOT require authentication, which is standard
        practice for Prometheus scraping.
        """
        from pact_platform.use.observability.metrics import (
            get_metrics_content_type,
            get_metrics_endpoint_response,
        )

        return Response(
            content=get_metrics_endpoint_response(),
            media_type=get_metrics_content_type(),
        )

    # ------------------------------------------------------------------
    # Shutdown handler (I8)
    # ------------------------------------------------------------------

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        """Graceful shutdown — close all WebSocket connections."""
        shutdown_manager.trigger_shutdown()
        await shutdown_manager.close_all_connections()
        logger.info("PACT API shutdown complete")

    # --- Work management routers (M2) ---
    from pact_platform.use.api.routers import (
        decisions_router,
        metrics_router,
        objectives_router,
        pools_router,
        requests_router,
        reviews_router,
        sessions_router,
    )

    _auth_deps = [Depends(verify_token)]
    app.include_router(objectives_router, dependencies=_auth_deps)
    app.include_router(requests_router, dependencies=_auth_deps)
    app.include_router(sessions_router, dependencies=_auth_deps)
    app.include_router(decisions_router, dependencies=_auth_deps)
    app.include_router(pools_router, dependencies=_auth_deps)
    app.include_router(reviews_router, dependencies=_auth_deps)
    app.include_router(metrics_router, dependencies=_auth_deps)

    return app


# Lazy app creation — only instantiated when accessed, not at import time (L5)
app: FastAPI | None = None


def get_app() -> FastAPI:
    """Get or create the default app instance."""
    global app
    if app is None:
        app = create_app()
    return app


if __name__ == "__main__":
    import uvicorn

    cfg = _get_env_config()
    logger.info("Starting PACT API on %s:%d", cfg.pact_api_host, cfg.pact_api_port)
    app = get_app()
    uvicorn.run(
        app,
        host=cfg.pact_api_host,
        port=cfg.pact_api_port,
        reload=cfg.debug,
    )
