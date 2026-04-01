# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared rate limiter for all API routers.

SlowAPI requires the limiter instance to be accessible at decorator time.
This module provides a singleton that server.py attaches to the app and
all routers import for @limiter.limit() decorators.

Rate limit strings are resolved lazily to avoid import-time env config
loading that can interfere with test fixtures.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

# Default rate limits — overridden by env config at server startup.
# These values match the EnvConfig defaults.
RATE_GET = "60/minute"
RATE_POST = "30/minute"
