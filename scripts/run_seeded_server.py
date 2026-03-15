#!/usr/bin/env python3
# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Launch the CARE Platform API server with demo seed data pre-loaded.

Usage:
    python scripts/run_seeded_server.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Seed data, create the app with seeded components, and run uvicorn."""
    from scripts.seed_demo import main as seed_main

    logger.info("Seeding demo data...")
    components = seed_main()

    if components is None:
        logger.error("Seed script returned None — cannot start server")
        sys.exit(1)

    # Build PlatformAPI from seeded components
    from care_platform.api.endpoints import PlatformAPI

    platform_api = PlatformAPI(
        registry=components["registry"],
        approval_queue=components["approval_queue"],
        cost_tracker=components["cost_tracker"],
        workspace_registry=components["workspace_registry"],
        bridge_manager=components["bridge_manager"],
    )

    # Create the app with the seeded PlatformAPI
    from care_platform.api.server import create_app

    os.environ.setdefault("CARE_DEV_MODE", "true")
    os.environ.setdefault("CARE_API_HOST", "0.0.0.0")
    os.environ.setdefault("CARE_API_PORT", "8000")

    app = create_app(platform_api=platform_api)

    logger.info("Starting CARE Platform API with seeded data on http://localhost:8000")

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
