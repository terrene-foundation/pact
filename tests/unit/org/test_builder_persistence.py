# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for OrgBuilder persistence — save/load (Task 1604).

Validates that:
- OrgBuilder.save() persists an OrgDefinition to a TrustStore
- OrgBuilder.load() restores an OrgDefinition from a TrustStore
- Round-trip: save then load produces an equivalent OrgDefinition
- store_org_definition() / get_org_definition() work on all store implementations
- Missing org definition returns None
- Invalid/corrupt data raises clear errors
"""

import pytest

from pact_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    TeamConfig,
    WorkspaceConfig,
)
from pact_platform.build.org.builder import OrgBuilder, OrgDefinition
from pact_platform.trust.store.sqlite_store import SQLiteTrustStore
from pact_platform.trust.store.store import FilesystemStore, MemoryStore


def _make_org() -> OrgDefinition:
    """Create a valid OrgDefinition for testing."""
    return (
        OrgBuilder("test-org", "Test Organization")
        .add_workspace(WorkspaceConfig(id="ws-1", path="workspaces/test/"))
        .add_envelope(ConstraintEnvelopeConfig(id="env-1"))
        .add_agent(
            AgentConfig(
                id="agent-1",
                name="Agent One",
                role="Testing",
                constraint_envelope="env-1",
            )
        )
        .add_team(
            TeamConfig(
                id="team-1",
                name="Team One",
                workspace="ws-1",
                agents=["agent-1"],
            )
        )
        .build()
    )


class TestOrgBuilderSave:
    """OrgBuilder.save() persists OrgDefinition to a TrustStore."""

    def test_save_to_memory_store(self):
        """save() stores the org definition in a MemoryStore."""
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        stored = store.get_org_definition(org.org_id)
        assert stored is not None

    def test_save_to_filesystem_store(self, tmp_path):
        """save() stores the org definition in a FilesystemStore."""
        org = _make_org()
        store = FilesystemStore(tmp_path)
        OrgBuilder.save(org, store)
        stored = store.get_org_definition(org.org_id)
        assert stored is not None

    def test_save_to_sqlite_store(self):
        """save() stores the org definition in a SQLiteTrustStore."""
        org = _make_org()
        store = SQLiteTrustStore()
        OrgBuilder.save(org, store)
        stored = store.get_org_definition(org.org_id)
        assert stored is not None

    def test_save_requires_valid_store(self):
        """save() raises if store is None."""
        org = _make_org()
        with pytest.raises((TypeError, ValueError, AttributeError)):
            OrgBuilder.save(org, None)


class TestOrgBuilderLoad:
    """OrgBuilder.load() restores OrgDefinition from a TrustStore."""

    def test_load_from_memory_store(self):
        """load() retrieves and reconstructs OrgDefinition from MemoryStore."""
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert isinstance(loaded, OrgDefinition)

    def test_load_nonexistent_returns_none(self):
        """load() returns None when org is not found."""
        store = MemoryStore()
        result = OrgBuilder.load("nonexistent-org", store)
        assert result is None


class TestOrgBuilderRoundTrip:
    """Save then load produces an equivalent OrgDefinition."""

    def test_round_trip_preserves_org_id(self):
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert loaded.org_id == org.org_id

    def test_round_trip_preserves_name(self):
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert loaded.name == org.name

    def test_round_trip_preserves_agents(self):
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert len(loaded.agents) == len(org.agents)
        assert loaded.agents[0].id == org.agents[0].id

    def test_round_trip_preserves_teams(self):
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert len(loaded.teams) == len(org.teams)
        assert loaded.teams[0].id == org.teams[0].id

    def test_round_trip_preserves_envelopes(self):
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert len(loaded.envelopes) == len(org.envelopes)
        assert loaded.envelopes[0].id == org.envelopes[0].id

    def test_round_trip_preserves_workspaces(self):
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert len(loaded.workspaces) == len(org.workspaces)
        assert loaded.workspaces[0].id == org.workspaces[0].id

    def test_round_trip_with_filesystem_store(self, tmp_path):
        """Round-trip works with FilesystemStore."""
        org = _make_org()
        store = FilesystemStore(tmp_path)
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert loaded.org_id == org.org_id
        assert len(loaded.agents) == len(org.agents)

    def test_round_trip_with_sqlite_store(self):
        """Round-trip works with SQLiteTrustStore."""
        org = _make_org()
        store = SQLiteTrustStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        assert loaded.org_id == org.org_id
        assert len(loaded.agents) == len(org.agents)

    def test_round_trip_loaded_org_validates(self):
        """Loaded OrgDefinition passes validation."""
        org = _make_org()
        store = MemoryStore()
        OrgBuilder.save(org, store)
        loaded = OrgBuilder.load(org.org_id, store)
        assert loaded is not None
        valid, errors = loaded.validate_org()
        assert valid is True, f"Loaded org invalid: {errors}"


class TestStoreOrgDefinition:
    """store_org_definition() / get_org_definition() on store implementations."""

    def test_memory_store_stores_and_retrieves(self):
        store = MemoryStore()
        store.store_org_definition("org-1", {"org_id": "org-1", "name": "Org"})
        data = store.get_org_definition("org-1")
        assert data is not None
        assert data["org_id"] == "org-1"

    def test_memory_store_missing_returns_none(self):
        store = MemoryStore()
        assert store.get_org_definition("nonexistent") is None

    def test_filesystem_store_stores_and_retrieves(self, tmp_path):
        store = FilesystemStore(tmp_path)
        store.store_org_definition("org-1", {"org_id": "org-1", "name": "Org"})
        data = store.get_org_definition("org-1")
        assert data is not None
        assert data["org_id"] == "org-1"

    def test_sqlite_store_stores_and_retrieves(self):
        store = SQLiteTrustStore()
        store.store_org_definition("org-1", {"org_id": "org-1", "name": "Org"})
        data = store.get_org_definition("org-1")
        assert data is not None
        assert data["org_id"] == "org-1"

    def test_overwrite_existing_org(self):
        """Storing with the same ID overwrites the previous definition."""
        store = MemoryStore()
        store.store_org_definition("org-1", {"org_id": "org-1", "name": "V1"})
        store.store_org_definition("org-1", {"org_id": "org-1", "name": "V2"})
        data = store.get_org_definition("org-1")
        assert data is not None
        assert data["name"] == "V2"
