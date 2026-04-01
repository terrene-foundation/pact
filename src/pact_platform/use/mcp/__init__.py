# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""MCP governance integration for the PACT platform.

Bridges the L1 ``pact.mcp`` enforcer, middleware, and audit trail to the
platform's governance config, providing:

- ``PlatformMcpGovernance``: Configures the L1 enforcer with org-level
  tool policies and wraps evaluation results with platform audit logging.
- ``create_mcp_router``: FastAPI router for the MCP evaluate endpoint.
"""

from pact_platform.use.mcp.bridge import PlatformMcpGovernance

__all__ = ["PlatformMcpGovernance"]
