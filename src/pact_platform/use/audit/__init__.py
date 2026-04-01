# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Audit utilities for the PACT platform USE plane.

Provides post-execution audit tools including TOCTOU (Time-of-Check /
Time-of-Use) comparison for governance envelope drift detection.
"""

from pact_platform.use.audit.toctou import audit_toctou_check

__all__ = ["audit_toctou_check"]
