# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for DataFlowEngine integration in pact_platform.models.

Verifies that the DataFlowEngine wrapper is properly configured
alongside the bare DataFlow primitive, providing enterprise features
(query monitoring, validation hooks) without breaking existing code.
"""

from __future__ import annotations

import pytest
from dataflow.engine import DataFlowEngine, QueryEngine


class TestDataFlowEngineSetup:
    """Verify DataFlowEngine is properly configured in models."""

    def test_db_engine_importable(self):
        """db_engine is exported from pact_platform.models."""
        from pact_platform.models import db_engine

        assert isinstance(db_engine, DataFlowEngine)

    def test_db_engine_wraps_db(self):
        """db_engine.dataflow is the same instance as db."""
        from pact_platform.models import db, db_engine

        assert db_engine.dataflow is db

    def test_db_engine_has_query_engine(self):
        """db_engine has a QueryEngine with configurable threshold."""
        from pact_platform.models import db_engine

        assert db_engine.query_engine is not None
        assert isinstance(db_engine.query_engine, QueryEngine)

    def test_db_engine_in_all(self):
        """db_engine is in __all__."""
        from pact_platform import models

        assert "db_engine" in models.__all__

    def test_express_sync_still_works_through_db(self):
        """Existing express_sync API works unchanged via db."""
        from pact_platform.models import db

        # Create a record via the existing pattern
        result = db.express_sync.create(
            "Run",
            {
                "id": "test-engine-run-1",
                "agent_address": "D1-R1",
                "run_type": "llm",
                "status": "completed",
            },
        )
        assert result is not None

        # Read back
        record = db.express_sync.read("Run", "test-engine-run-1")
        assert record is not None
        assert record["agent_address"] == "D1-R1"

        # Cleanup
        db.express_sync.delete("Run", "test-engine-run-1")

    def test_express_sync_works_through_engine_dataflow(self):
        """Express CRUD also works via db_engine.dataflow."""
        from pact_platform.models import db_engine

        result = db_engine.dataflow.express_sync.create(
            "Run",
            {
                "id": "test-engine-run-2",
                "agent_address": "D2-R1",
                "run_type": "tool",
                "status": "running",
            },
        )
        assert result is not None

        record = db_engine.dataflow.express_sync.read("Run", "test-engine-run-2")
        assert record is not None
        assert record["agent_address"] == "D2-R1"

        db_engine.dataflow.express_sync.delete("Run", "test-engine-run-2")


class TestQueryEngineConfiguration:
    """Verify QueryEngine configuration."""

    def test_default_slow_query_threshold(self):
        """Default threshold is 1.0 seconds."""
        qe = QueryEngine(slow_query_threshold=1.0)
        assert qe.slow_query_threshold == 1.0

    def test_custom_slow_query_threshold(self):
        """Custom threshold is respected."""
        qe = QueryEngine(slow_query_threshold=0.5)
        assert qe.slow_query_threshold == 0.5
