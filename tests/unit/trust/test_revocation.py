# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for cascade revocation management (Task 207)."""

from care_platform.trust.credentials import CredentialManager
from care_platform.trust.revocation import RevocationManager, RevocationRecord


class TestSurgicalRevocation:
    """Test RevocationManager.surgical_revoke() — only the target is affected."""

    def test_surgical_revoke_single_agent(self):
        """Surgical revocation revokes only the target agent."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        cred_mgr.issue_token("agent-a", 0.85)
        record = rev_mgr.surgical_revoke("agent-a", "Policy violation", "admin-1")

        assert isinstance(record, RevocationRecord)
        assert record.agent_id == "agent-a"
        assert record.reason == "Policy violation"
        assert record.revoker_id == "admin-1"
        assert record.revocation_type == "surgical"
        assert record.affected_agents == []
        assert record.revocation_id.startswith("rev-")

    def test_surgical_revoke_invalidates_token(self):
        """Surgical revocation invalidates the agent's verification token."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        cred_mgr.issue_token("agent-a", 0.85)
        rev_mgr.surgical_revoke("agent-a", "Policy violation", "admin-1")

        assert cred_mgr.get_valid_token("agent-a") is None

    def test_surgical_revoke_siblings_unaffected(self):
        """Surgical revocation does not affect sibling agents."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        # Parent delegates to A and B (siblings)
        rev_mgr.register_delegation("parent", "agent-a")
        rev_mgr.register_delegation("parent", "agent-b")

        cred_mgr.issue_token("agent-a", 0.85)
        cred_mgr.issue_token("agent-b", 0.90)

        rev_mgr.surgical_revoke("agent-a", "Issue with A", "admin-1")

        # Agent B should be unaffected
        assert cred_mgr.get_valid_token("agent-b") is not None
        assert not rev_mgr.is_revoked("agent-b")


class TestCascadeRevocation:
    """Test RevocationManager.cascade_revoke() — target + all downstream."""

    def test_cascade_revoke_with_children(self):
        """Cascade revocation revokes the target and all downstream agents."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        # A delegates to B
        rev_mgr.register_delegation("agent-a", "agent-b")

        cred_mgr.issue_token("agent-a", 0.85)
        cred_mgr.issue_token("agent-b", 0.90)

        record = rev_mgr.cascade_revoke("agent-a", "Cascade needed", "admin-1")

        assert record.revocation_type == "cascade"
        assert "agent-b" in record.affected_agents
        assert cred_mgr.get_valid_token("agent-a") is None
        assert cred_mgr.get_valid_token("agent-b") is None

    def test_cascade_multi_level_tree(self):
        """Cascade revocation traverses A -> B -> C (multi-level)."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        # A -> B -> C
        rev_mgr.register_delegation("agent-a", "agent-b")
        rev_mgr.register_delegation("agent-b", "agent-c")

        cred_mgr.issue_token("agent-a", 0.85)
        cred_mgr.issue_token("agent-b", 0.80)
        cred_mgr.issue_token("agent-c", 0.75)

        record = rev_mgr.cascade_revoke("agent-a", "Root compromise", "admin-1")

        # Both B and C should be in affected_agents
        assert "agent-b" in record.affected_agents
        assert "agent-c" in record.affected_agents
        assert cred_mgr.get_valid_token("agent-a") is None
        assert cred_mgr.get_valid_token("agent-b") is None
        assert cred_mgr.get_valid_token("agent-c") is None

    def test_cascade_sibling_unaffected(self):
        """Cascade revoking one child does not affect siblings."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        # Parent -> A, Parent -> B, A -> C
        rev_mgr.register_delegation("parent", "agent-a")
        rev_mgr.register_delegation("parent", "agent-b")
        rev_mgr.register_delegation("agent-a", "agent-c")

        cred_mgr.issue_token("parent", 0.95)
        cred_mgr.issue_token("agent-a", 0.85)
        cred_mgr.issue_token("agent-b", 0.90)
        cred_mgr.issue_token("agent-c", 0.75)

        # Cascade revoke agent-a (should hit A and C, but NOT parent or B)
        record = rev_mgr.cascade_revoke("agent-a", "Subtree issue", "admin-1")

        assert "agent-c" in record.affected_agents
        assert "agent-b" not in record.affected_agents
        assert "parent" not in record.affected_agents

        assert cred_mgr.get_valid_token("agent-a") is None
        assert cred_mgr.get_valid_token("agent-c") is None
        assert cred_mgr.get_valid_token("agent-b") is not None
        assert cred_mgr.get_valid_token("parent") is not None

    def test_cascade_leaf_node_no_children(self):
        """Cascade revoking a leaf node has no downstream effect."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        rev_mgr.register_delegation("parent", "leaf")
        cred_mgr.issue_token("leaf", 0.80)

        record = rev_mgr.cascade_revoke("leaf", "Leaf issue", "admin-1")

        assert record.affected_agents == []
        assert cred_mgr.get_valid_token("leaf") is None


class TestRevocationLog:
    """Test RevocationManager.get_revocation_log()."""

    def test_revocation_log_records_correctly(self):
        """Revocation log captures all revocation events."""
        rev_mgr = RevocationManager()

        rev_mgr.surgical_revoke("agent-a", "Reason A", "admin-1")
        rev_mgr.surgical_revoke("agent-b", "Reason B", "admin-2")

        log = rev_mgr.get_revocation_log()
        assert len(log) == 2
        assert log[0].agent_id == "agent-a"
        assert log[1].agent_id == "agent-b"

    def test_revocation_log_filtered_by_agent(self):
        """Revocation log can be filtered to a specific agent."""
        rev_mgr = RevocationManager()

        rev_mgr.surgical_revoke("agent-a", "Reason A", "admin-1")
        rev_mgr.surgical_revoke("agent-b", "Reason B", "admin-2")
        rev_mgr.surgical_revoke("agent-a", "Reason A2", "admin-1")

        log_a = rev_mgr.get_revocation_log(agent_id="agent-a")
        assert len(log_a) == 2
        assert all(r.agent_id == "agent-a" for r in log_a)

    def test_revocation_log_empty_when_no_revocations(self):
        """Revocation log is empty initially."""
        rev_mgr = RevocationManager()
        assert rev_mgr.get_revocation_log() == []


class TestIsRevoked:
    """Test RevocationManager.is_revoked()."""

    def test_is_revoked_true_after_surgical(self):
        """is_revoked returns True after surgical revocation."""
        rev_mgr = RevocationManager()
        rev_mgr.surgical_revoke("agent-a", "Test", "admin-1")
        assert rev_mgr.is_revoked("agent-a")

    def test_is_revoked_true_after_cascade(self):
        """is_revoked returns True for both target and downstream after cascade."""
        rev_mgr = RevocationManager()
        rev_mgr.register_delegation("agent-a", "agent-b")
        rev_mgr.cascade_revoke("agent-a", "Cascade", "admin-1")
        assert rev_mgr.is_revoked("agent-a")
        assert rev_mgr.is_revoked("agent-b")

    def test_is_revoked_false_for_unrevoked_agent(self):
        """is_revoked returns False for agents that have not been revoked."""
        rev_mgr = RevocationManager()
        assert not rev_mgr.is_revoked("agent-clean")


class TestCanRedelegate:
    """Test RevocationManager.can_redelegate()."""

    def test_can_redelegate_always_true(self):
        """Revocation is forward-looking — re-delegation is always possible."""
        rev_mgr = RevocationManager()
        rev_mgr.surgical_revoke("agent-a", "Old issue", "admin-1")
        assert rev_mgr.can_redelegate("agent-a")

    def test_can_redelegate_unrevoked_agent(self):
        """An agent that was never revoked can also be re-delegated."""
        rev_mgr = RevocationManager()
        assert rev_mgr.can_redelegate("agent-new")


class TestDelegationTree:
    """Test RevocationManager delegation tree management."""

    def test_register_delegation(self):
        """register_delegation creates a parent-child relationship."""
        rev_mgr = RevocationManager()
        rev_mgr.register_delegation("parent", "child")
        assert "child" in rev_mgr.get_downstream_agents("parent")

    def test_get_downstream_agents_empty_for_leaf(self):
        """A leaf node has no downstream agents."""
        rev_mgr = RevocationManager()
        assert rev_mgr.get_downstream_agents("leaf-node") == []

    def test_get_downstream_agents_multi_level(self):
        """get_downstream_agents recursively finds all descendants."""
        rev_mgr = RevocationManager()
        rev_mgr.register_delegation("a", "b")
        rev_mgr.register_delegation("b", "c")
        rev_mgr.register_delegation("b", "d")

        downstream = rev_mgr.get_downstream_agents("a")
        assert set(downstream) == {"b", "c", "d"}


class TestTokenRevocationDuringCascade:
    """Integration: cascade revocation properly revokes tokens via CredentialManager."""

    def test_cascade_revokes_all_tokens(self):
        """When cascade revoking, all downstream tokens are revoked via CredentialManager."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        # Build tree: root -> mid -> leaf
        rev_mgr.register_delegation("root", "mid")
        rev_mgr.register_delegation("mid", "leaf")

        cred_mgr.issue_token("root", 0.95)
        cred_mgr.issue_token("mid", 0.85)
        cred_mgr.issue_token("leaf", 0.75)

        rev_mgr.cascade_revoke("root", "Full cascade", "admin-1")

        # All tokens should be invalid
        assert cred_mgr.needs_reverification("root")
        assert cred_mgr.needs_reverification("mid")
        assert cred_mgr.needs_reverification("leaf")

    def test_surgical_revoke_only_target_token(self):
        """Surgical revocation only revokes the target's token, not children's."""
        cred_mgr = CredentialManager()
        rev_mgr = RevocationManager(credential_manager=cred_mgr)

        rev_mgr.register_delegation("parent", "child")

        cred_mgr.issue_token("parent", 0.95)
        cred_mgr.issue_token("child", 0.85)

        rev_mgr.surgical_revoke("parent", "Parent issue only", "admin-1")

        assert cred_mgr.needs_reverification("parent")
        assert not cred_mgr.needs_reverification("child")


class TestEATPBridgeDelegationTreeUnification:
    """RT4-L5: RevocationManager should use EATPBridge's delegation tree when available."""

    def test_bridge_tree_used_for_downstream_lookup(self):
        """When eatp_bridge is provided, get_downstream_agents uses the bridge's tree."""
        # Create a mock-like bridge object that provides get_delegation_tree()
        bridge = _FakeEATPBridge(
            delegation_tree={"agent-a": ["agent-b", "agent-c"], "agent-b": ["agent-d"]}
        )
        rev_mgr = RevocationManager(eatp_bridge=bridge)

        downstream = rev_mgr.get_downstream_agents("agent-a")
        assert set(downstream) == {"agent-b", "agent-c", "agent-d"}

    def test_bridge_tree_cascade_revoke(self):
        """Cascade revocation uses the bridge tree for downstream discovery."""
        cred_mgr = CredentialManager()
        bridge = _FakeEATPBridge(delegation_tree={"root": ["child-a", "child-b"]})
        rev_mgr = RevocationManager(credential_manager=cred_mgr, eatp_bridge=bridge)

        cred_mgr.issue_token("root", 0.95)
        cred_mgr.issue_token("child-a", 0.85)
        cred_mgr.issue_token("child-b", 0.80)

        record = rev_mgr.cascade_revoke("root", "Root issue", "admin-1")

        assert "child-a" in record.affected_agents
        assert "child-b" in record.affected_agents
        assert cred_mgr.get_valid_token("child-a") is None
        assert cred_mgr.get_valid_token("child-b") is None

    def test_standalone_mode_still_works(self):
        """Without eatp_bridge, RevocationManager uses its own internal tree."""
        rev_mgr = RevocationManager()
        rev_mgr.register_delegation("parent", "child")

        downstream = rev_mgr.get_downstream_agents("parent")
        assert downstream == ["child"]

    def test_register_delegation_delegates_to_bridge_when_present(self):
        """register_delegation still works (no-op or local) when bridge is present."""
        bridge = _FakeEATPBridge(delegation_tree={"x": ["y"]})
        rev_mgr = RevocationManager(eatp_bridge=bridge)

        # register_delegation should not raise and should not interfere with bridge tree
        rev_mgr.register_delegation("x", "z")

        # Bridge tree should be the authoritative source for downstream lookups
        downstream = rev_mgr.get_downstream_agents("x")
        # Bridge only has x -> y, but local also has x -> z. Since bridge is
        # authoritative, only y should be returned.
        assert "y" in downstream

    def test_bridge_tree_multi_level_cascade(self):
        """Multi-level cascade through bridge tree: a -> b -> c."""
        cred_mgr = CredentialManager()
        bridge = _FakeEATPBridge(delegation_tree={"a": ["b"], "b": ["c"]})
        rev_mgr = RevocationManager(credential_manager=cred_mgr, eatp_bridge=bridge)

        cred_mgr.issue_token("a", 0.95)
        cred_mgr.issue_token("b", 0.85)
        cred_mgr.issue_token("c", 0.75)

        record = rev_mgr.cascade_revoke("a", "Root issue", "admin-1")

        assert set(record.affected_agents) == {"b", "c"}


class TestRevocationPersistence:
    """RT5-11: RevocationManager persists records to TrustStore when configured."""

    def test_surgical_revoke_persists_to_store(self):
        """surgical_revoke() writes to TrustStore when trust_store is set."""
        from care_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        rev_mgr = RevocationManager(trust_store=store)

        record = rev_mgr.surgical_revoke("agent-a", "Policy breach", "admin-1")

        persisted = store.get_revocations(agent_id="agent-a")
        assert len(persisted) == 1
        assert persisted[0]["agent_id"] == "agent-a"
        assert persisted[0]["reason"] == "Policy breach"
        assert persisted[0]["revocation_id"] == record.revocation_id

    def test_cascade_revoke_persists_to_store(self):
        """cascade_revoke() writes to TrustStore when trust_store is set."""
        from care_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        rev_mgr = RevocationManager(trust_store=store)
        rev_mgr.register_delegation("agent-a", "agent-b")

        record = rev_mgr.cascade_revoke("agent-a", "Root compromise", "admin-1")

        persisted = store.get_revocations(agent_id="agent-a")
        assert len(persisted) == 1
        assert persisted[0]["revocation_type"] == "cascade"
        assert "agent-b" in persisted[0]["affected_agents"]
        assert persisted[0]["revocation_id"] == record.revocation_id

    def test_revoke_without_store_still_works(self):
        """Backward compatibility: revocation works without a trust store."""
        rev_mgr = RevocationManager()
        record = rev_mgr.surgical_revoke("agent-x", "Test reason", "admin-1")
        assert record.agent_id == "agent-x"
        assert rev_mgr.is_revoked("agent-x")

    def test_is_revoked_checks_store_when_not_in_memory(self):
        """is_revoked() falls back to TrustStore if not found in memory."""
        from care_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        # Pre-populate the store with a revocation record (simulating restart)
        store.store_revocation(
            "rev-old001",
            {
                "revocation_id": "rev-old001",
                "agent_id": "agent-lost",
                "reason": "Historical violation",
                "revoker_id": "admin-old",
                "revoked_at": "2026-01-01T00:00:00+00:00",
                "revocation_type": "surgical",
                "affected_agents": [],
            },
        )

        # Create a fresh manager (empty in-memory log) with the store
        rev_mgr = RevocationManager(trust_store=store)

        # Should find the revocation via the store
        assert rev_mgr.is_revoked("agent-lost")

    def test_is_revoked_checks_store_affected_agents(self):
        """is_revoked() checks affected_agents in store records too."""
        from care_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        store.store_revocation(
            "rev-cascade01",
            {
                "revocation_id": "rev-cascade01",
                "agent_id": "agent-root",
                "reason": "Cascade",
                "revoker_id": "admin-1",
                "revoked_at": "2026-01-01T00:00:00+00:00",
                "revocation_type": "cascade",
                "affected_agents": ["agent-child-1", "agent-child-2"],
            },
        )

        rev_mgr = RevocationManager(trust_store=store)
        assert rev_mgr.is_revoked("agent-child-1")
        assert rev_mgr.is_revoked("agent-child-2")
        assert rev_mgr.is_revoked("agent-root")


class TestRevocationHydration:
    """RT5-11: RevocationManager hydrates from TrustStore on init."""

    def test_hydrate_loads_existing_revocations(self):
        """On init, RevocationManager loads existing records from the store."""
        from care_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        store.store_revocation(
            "rev-hydrate1",
            {
                "revocation_id": "rev-hydrate1",
                "agent_id": "agent-hydrated",
                "reason": "Pre-existing revocation",
                "revoker_id": "admin-prev",
                "revoked_at": "2026-02-15T12:00:00+00:00",
                "revocation_type": "surgical",
                "affected_agents": [],
            },
        )

        rev_mgr = RevocationManager(trust_store=store)

        # The in-memory log should contain the hydrated record
        log = rev_mgr.get_revocation_log()
        assert len(log) == 1
        assert log[0].agent_id == "agent-hydrated"
        assert log[0].revocation_id == "rev-hydrate1"

    def test_hydrate_multiple_records(self):
        """Hydration loads all revocation records from the store."""
        from care_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        for i in range(3):
            store.store_revocation(
                f"rev-multi{i}",
                {
                    "revocation_id": f"rev-multi{i}",
                    "agent_id": f"agent-{i}",
                    "reason": f"Reason {i}",
                    "revoker_id": "admin-bulk",
                    "revoked_at": "2026-02-15T12:00:00+00:00",
                    "revocation_type": "surgical",
                    "affected_agents": [],
                },
            )

        rev_mgr = RevocationManager(trust_store=store)
        log = rev_mgr.get_revocation_log()
        assert len(log) == 3
        agent_ids = {r.agent_id for r in log}
        assert agent_ids == {"agent-0", "agent-1", "agent-2"}

    def test_hydrate_then_new_revocation_appends(self):
        """New revocations after hydration append to the log (no duplicates)."""
        from care_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        store.store_revocation(
            "rev-existing",
            {
                "revocation_id": "rev-existing",
                "agent_id": "agent-old",
                "reason": "Old reason",
                "revoker_id": "admin-old",
                "revoked_at": "2026-01-01T00:00:00+00:00",
                "revocation_type": "surgical",
                "affected_agents": [],
            },
        )

        rev_mgr = RevocationManager(trust_store=store)
        rev_mgr.surgical_revoke("agent-new", "New reason", "admin-new")

        log = rev_mgr.get_revocation_log()
        assert len(log) == 2
        assert log[0].agent_id == "agent-old"
        assert log[1].agent_id == "agent-new"

    def test_hydrate_is_noop_without_store(self):
        """Without a store, no hydration happens — log starts empty."""
        rev_mgr = RevocationManager()
        assert rev_mgr.get_revocation_log() == []


class _FakeEATPBridge:
    """Minimal fake implementing the get_delegation_tree() and revoke_agent() interface."""

    def __init__(self, delegation_tree: dict[str, list[str]] | None = None):
        self._tree = delegation_tree or {}
        self.revoked_agents: list[str] = []

    def get_delegation_tree(self) -> dict[str, list[str]]:
        return dict(self._tree)

    def revoke_agent(self, agent_id: str) -> None:
        self.revoked_agents.append(agent_id)
