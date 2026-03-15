# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""FastAPI server for the CARE Platform.

Mounts all PlatformAPI handlers (Phase 1, M18 dashboard, and M36 bridge
management endpoints) as FastAPI routes. Includes CORS middleware for
frontend development, a health check endpoint, a readiness probe,
WebSocket authentication, and graceful shutdown handling.

Usage:
    python -m care_platform.api.server
"""

from __future__ import annotations

import hmac
import logging
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

from care_platform.api.endpoints import ApiResponse, PlatformAPI
from care_platform.api.events import event_bus
from care_platform.api.shutdown import ShutdownManager
from care_platform.config.env import EnvConfig, load_env_config
from care_platform.execution.approval import ApprovalQueue
from care_platform.execution.registry import AgentRegistry
from care_platform.persistence.cost_tracking import CostTracker
from care_platform.workspace.bridge import BridgeManager
from care_platform.workspace.models import WorkspaceRegistry

logger = logging.getLogger(__name__)


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


def _build_platform_api() -> PlatformAPI:
    """Build a PlatformAPI instance with default components.

    In production, these components would be populated from configuration
    and persistence layers. For development, empty/default instances are
    created.

    Returns:
        A fully wired PlatformAPI instance.
    """
    registry = AgentRegistry()
    approval_queue = ApprovalQueue()
    cost_tracker = CostTracker()
    workspace_registry = WorkspaceRegistry()
    bridge_manager = BridgeManager()

    return PlatformAPI(
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
_default_api: PlatformAPI | None = None


def create_app(
    platform_api: PlatformAPI | None = None,
    env_config: EnvConfig | None = None,
    trust_store: Any | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        platform_api: Optional PlatformAPI instance. When None, a default
            instance is created with empty components.
        env_config: Optional EnvConfig. When None, loaded from environment.
        trust_store: Optional trust store for readiness probe. When
            provided, the ``/ready`` endpoint checks store health.

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
        title="CARE Platform API",
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

    # Store shutdown manager on app state for access and testing
    app.state.shutdown_manager = shutdown_manager

    # CORS middleware — restricted methods and headers (H4)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.care_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Authentication: bearer token from CARE_API_TOKEN env var (C2/C3)
    _api_token = cfg.care_api_token
    _bearer_scheme = HTTPBearer(auto_error=False)

    async def verify_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    ) -> str:
        """Verify bearer token and return the authenticated identity.

        When CARE_API_TOKEN is not set (empty), auth is disabled for
        local development. In production, set CARE_API_TOKEN to require
        authentication on all mutating endpoints.
        """
        if not _api_token:
            # No token configured — dev mode, no auth required
            return "anonymous"
        if credentials is None or not hmac.compare_digest(credentials.credentials, _api_token):
            raise HTTPException(status_code=401, detail="Invalid or missing API token")
        return "authenticated"

    # Rate limit values from config
    _rate_get = cfg.care_rate_limit_get
    _rate_post = cfg.care_rate_limit_post

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    @app.get("/health")
    @limiter.limit(_rate_get)
    async def health(request: Request) -> dict[str, str]:
        """Health check endpoint for load balancers and monitoring."""
        return {"status": "healthy", "service": "care-platform"}

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
    # WebSocket for real-time updates
    # ------------------------------------------------------------------

    _max_ws_subscribers = cfg.care_max_ws_subscribers

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time platform event streaming.

        Authentication methods (checked in order):
        1. Sec-WebSocket-Protocol header with ``bearer.<token>`` subprotocol
           (preferred — token not in URL/logs)
        2. Query parameter ``?token=...`` (fallback — logged as warning)

        When CARE_API_TOKEN is not set and dev mode is enabled, auth is
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
    # Shutdown handler (I8)
    # ------------------------------------------------------------------

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        """Graceful shutdown — close all WebSocket connections."""
        shutdown_manager.trigger_shutdown()
        await shutdown_manager.close_all_connections()
        logger.info("CARE Platform API shutdown complete")

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
    logger.info("Starting CARE Platform API on %s:%d", cfg.care_api_host, cfg.care_api_port)
    app = get_app()
    uvicorn.run(
        app,
        host=cfg.care_api_host,
        port=cfg.care_api_port,
        reload=cfg.debug,
    )
