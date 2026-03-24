# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Platform trust layer — constraint enforcement, audit, stores, and resilience.

Modules deleted during M0 (now in kailash.trust or kailash-pact):
  attestation, delegation, genesis, lifecycle, posture, scoring, reasoning,
  decorators, dual_binding, revocation, integrity, messaging, uncertainty,
  jcs, sd_jwt, eatp_bridge, credentials, bridge_trust, bridge_posture,
  authorization, shadow_enforcer, shadow_enforcer_live

Kept modules (platform-specific):
  constraint/ — envelope evaluation, gradient engine, enforcement pipeline
  audit/ — audit anchors, pipeline, bridge audit
  store/ — SQLite/PostgreSQL stores, backup, health, cost tracking
  store_isolation/ — data isolation, management, violations
  resilience/ — failure modes
  auth/ — Firebase admin auth
"""

from __future__ import annotations

__all__: list[str] = []
