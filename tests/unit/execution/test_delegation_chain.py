# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for delegation chain verification and cascade revocation.

DC-1: Delegation chain verification during agent assignment.
DC-2: Chain-level cascade revocation.

Covers:
- Chain verification succeeds for valid genesis -> delegator -> delegatee chain
- Chain verification skips gracefully when no TrustStore is configured
- Chain verification skips gracefully when no delegation records exist
- Chain verification fails on broken chain (no inbound delegation)
- Chain verification fails on cycle detection
- Chain verification fails on revoked delegation link
- Chain verification fails on signature mismatch (fail-closed)
- Chain verification blocks agent assignment on failure
- Chain verification filters auto-selected agents
- Cascade revocation revokes downstream delegates
- Cascade revocation handles diamond-shaped delegation graphs
- Cascade revocation stores revocation records in TrustStore
- Cascade revocation persists posture change events
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.trust.store.store import MemoryStore
from pact_platform.use.execution.registry import AgentRegistry, AgentStatus
from pact_platform.use.execution.runtime import (
    ExecutionRuntime,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_delegation(
    delegator_id: str,
    delegatee_id: str,
    *,
    delegation_id: str = "",
    revoked: bool = False,
    include_signature: bool = False,
) -> dict[str, Any]:
    """Build a delegation record dict for testing."""
    d_id = delegation_id or f"del-{delegator_id}-{delegatee_id}"
    payload: dict[str, Any] = {
        "delegation_id": d_id,
        "delegator_id": delegator_id,
        "delegatee_id": delegatee_id,
        "revoked": revoked,
    }
    if include_signature:
        # Create a valid signature: SHA-256 of canonical signing payload
        signing_payload = {"delegator": delegator_id, "delegatee": delegatee_id}
        payload_bytes = json.dumps(signing_payload, sort_keys=True, separators=(",", ":")).encode()
        payload["signing_payload"] = signing_payload
        payload["signature"] = hashlib.sha256(payload_bytes).hexdigest()
    return payload


def _make_genesis(authority_id: str) -> dict[str, Any]:
    """Build a genesis record dict for testing."""
    return {
        "authority_id": authority_id,
        "public_key": f"pk-{authority_id}",
        "timestamp": "2026-01-01T00:00:00Z",
    }


def _setup_chain(
    store: MemoryStore,
    registry: AgentRegistry,
    *,
    include_signatures: bool = False,
) -> None:
    """Set up a simple genesis -> delegator -> delegatee chain.

    Chain: genesis-root -> agent-mid -> agent-leaf
    """
    store.store_genesis("genesis-root", _make_genesis("genesis-root"))
    store.store_delegation(
        "del-root-mid",
        _make_delegation(
            "genesis-root",
            "agent-mid",
            delegation_id="del-root-mid",
            include_signature=include_signatures,
        ),
    )
    store.store_delegation(
        "del-mid-leaf",
        _make_delegation(
            "agent-mid",
            "agent-leaf",
            delegation_id="del-mid-leaf",
            include_signature=include_signatures,
        ),
    )
    registry.register(agent_id="agent-leaf", name="Leaf Agent", role="analyst")
    registry.register(agent_id="agent-mid", name="Mid Agent", role="manager")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture()
def registry() -> AgentRegistry:
    return AgentRegistry()


@pytest.fixture()
def audit_chain() -> AuditChain:
    return AuditChain(chain_id="test-chain")


# ---------------------------------------------------------------------------
# DC-1: Delegation chain verification
# ---------------------------------------------------------------------------


class TestDelegationChainVerification:
    """DC-1: Verify delegation chain from agent back to genesis."""

    def test_valid_chain_to_genesis(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """A valid chain from delegatee to genesis should pass verification."""
        _setup_chain(store, registry)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("agent-leaf")

        assert valid is True
        assert "genesis" in reason

    def test_valid_chain_with_signatures(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Chain with valid signatures should pass verification."""
        _setup_chain(store, registry, include_signatures=True)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("agent-leaf")

        assert valid is True

    def test_no_store_skips_verification(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """No TrustStore configured -- verification should pass (backward compatible)."""
        registry.register(agent_id="agent-1", name="Agent 1", role="analyst")
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            # No trust_store
        )

        valid, reason = rt._verify_delegation_chain("agent-1")

        assert valid is True
        assert "skipped" in reason

    def test_no_delegation_records_skips(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Agent with no delegation records -- skip gracefully."""
        registry.register(agent_id="solo-agent", name="Solo", role="analyst")
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("solo-agent")

        assert valid is True
        assert "skipped" in reason

    def test_broken_chain_fails(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Delegation chain that doesn't reach genesis should fail."""
        # agent-leaf delegated from agent-mid, but agent-mid has no delegation
        # and is not a genesis authority.
        store.store_delegation(
            "del-mid-leaf",
            _make_delegation("agent-mid", "agent-leaf", delegation_id="del-mid-leaf"),
        )
        registry.register(agent_id="agent-leaf", name="Leaf", role="analyst")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("agent-leaf")

        assert valid is False
        assert "broken chain" in reason

    def test_cycle_detection(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Cyclic delegation graph should be detected and rejected."""
        # A -> B -> C -> A (cycle)
        store.store_delegation(
            "del-a-b", _make_delegation("agent-a", "agent-b", delegation_id="del-a-b")
        )
        store.store_delegation(
            "del-b-c", _make_delegation("agent-b", "agent-c", delegation_id="del-b-c")
        )
        store.store_delegation(
            "del-c-a", _make_delegation("agent-c", "agent-a", delegation_id="del-c-a")
        )
        registry.register(agent_id="agent-b", name="B", role="analyst")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("agent-b")

        assert valid is False
        assert "cycle" in reason

    def test_revoked_delegation_link_fails(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """A revoked delegation link should fail chain verification."""
        store.store_genesis("genesis-root", _make_genesis("genesis-root"))
        store.store_delegation(
            "del-root-agent",
            _make_delegation(
                "genesis-root",
                "agent-1",
                delegation_id="del-root-agent",
                revoked=True,
            ),
        )
        registry.register(agent_id="agent-1", name="Agent 1", role="analyst")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("agent-1")

        assert valid is False
        assert "revoked" in reason

    def test_signature_mismatch_fails(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Tampered signature should fail chain verification."""
        store.store_genesis("genesis-root", _make_genesis("genesis-root"))
        delegation = _make_delegation(
            "genesis-root",
            "agent-1",
            delegation_id="del-root-agent",
            include_signature=True,
        )
        # Tamper with the signature
        delegation["signature"] = "deadbeef" * 8
        store.store_delegation("del-root-agent", delegation)
        registry.register(agent_id="agent-1", name="Agent 1", role="analyst")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("agent-1")

        assert valid is False
        assert "signature mismatch" in reason

    def test_chain_failure_blocks_assignment(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Failed chain verification should prevent agent assignment."""
        # Broken chain: delegation exists but doesn't reach genesis
        store.store_delegation(
            "del-orphan",
            _make_delegation("unknown-parent", "agent-1", delegation_id="del-orphan"),
        )
        registry.register(agent_id="agent-1", name="Agent 1", role="analyst")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )
        task_id = rt.submit("test-action", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.result is not None
        assert task.result.error is not None
        assert "Delegation chain verification failed" in task.result.error

    def test_auto_select_filters_broken_chain(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Auto-selection should skip agents with invalid delegation chains."""
        # agent-bad has broken chain
        store.store_delegation(
            "del-orphan",
            _make_delegation("unknown-parent", "agent-bad", delegation_id="del-orphan"),
        )
        registry.register(agent_id="agent-bad", name="Bad Agent", role="analyst", team_id="team-a")

        # agent-good has no delegation records (passes via skip)
        registry.register(
            agent_id="agent-good", name="Good Agent", role="analyst", team_id="team-a"
        )

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )
        task_id = rt.submit("test-action", team_id="team-a")
        task = rt.process_next()

        assert task is not None
        assert task.assigned_agent_id == "agent-good"

    def test_genesis_agent_passes_directly(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """An agent that is itself a genesis authority should pass immediately."""
        store.store_genesis("agent-genesis", _make_genesis("agent-genesis"))
        registry.register(agent_id="agent-genesis", name="Genesis Agent", role="authority")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        valid, reason = rt._verify_delegation_chain("agent-genesis")

        assert valid is True
        assert "genesis" in reason


# ---------------------------------------------------------------------------
# DC-2: Cascade revocation
# ---------------------------------------------------------------------------


class TestCascadeRevocation:
    """DC-2: Chain-level cascade revocation."""

    def test_cascade_revokes_downstream(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Revoking a mid-chain agent should cascade to downstream delegates."""
        _setup_chain(store, registry)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        revoked = rt.revoke_delegation_chain("agent-mid", "trust breach")

        assert "agent-mid" in revoked
        assert "agent-leaf" in revoked
        # Both agents should be REVOKED in the registry
        mid = registry.get("agent-mid")
        leaf = registry.get("agent-leaf")
        assert mid is not None and mid.status == AgentStatus.REVOKED
        assert leaf is not None and leaf.status == AgentStatus.REVOKED

    def test_cascade_stores_revocation_records(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Cascade revocation should store revocation records in the TrustStore."""
        _setup_chain(store, registry)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        rt.revoke_delegation_chain("agent-mid", "policy violation")

        # Check revocation records for both agents
        mid_revocations = store.get_revocations("agent-mid")
        leaf_revocations = store.get_revocations("agent-leaf")
        assert len(mid_revocations) >= 1
        assert len(leaf_revocations) >= 1

        # The root revocation should be marked "direct"
        mid_rev = mid_revocations[0]
        assert mid_rev["trigger"] == "direct"
        assert mid_rev["cascade_root"] == "agent-mid"

        # The downstream revocation should be marked "cascade_revocation"
        leaf_rev = leaf_revocations[0]
        assert leaf_rev["trigger"] == "cascade_revocation"
        assert leaf_rev["cascade_root"] == "agent-mid"

    def test_cascade_persists_posture_changes(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Cascade revocation should persist posture change events."""
        _setup_chain(store, registry)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        rt.revoke_delegation_chain("agent-mid", "compromised key")

        # Both agents should have posture change events
        mid_history = store.get_posture_history("agent-mid")
        leaf_history = store.get_posture_history("agent-leaf")
        assert len(mid_history) >= 1
        assert len(leaf_history) >= 1
        assert mid_history[0]["event"] == "cascade_revocation"
        assert leaf_history[0]["event"] == "cascade_revocation"

    def test_cascade_handles_diamond_graph(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Diamond-shaped delegation graph should not cause duplicate revocations.

        Graph:
            root -> A -> C
            root -> B -> C
        Revoking root should revoke A, B, C exactly once each.
        """
        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation("d-root-a", _make_delegation("root", "agent-a"))
        store.store_delegation("d-root-b", _make_delegation("root", "agent-b"))
        store.store_delegation("d-a-c", _make_delegation("agent-a", "agent-c"))
        store.store_delegation("d-b-c", _make_delegation("agent-b", "agent-c"))

        registry.register(agent_id="agent-a", name="A", role="analyst")
        registry.register(agent_id="agent-b", name="B", role="analyst")
        registry.register(agent_id="agent-c", name="C", role="analyst")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        revoked = rt.revoke_delegation_chain("root", "full revocation")

        # root itself is not in registry, but A, B, C should all be revoked
        assert "root" in revoked
        assert "agent-a" in revoked
        assert "agent-b" in revoked
        assert "agent-c" in revoked
        # No duplicates
        assert len(revoked) == len(set(revoked))

    def test_cascade_no_store(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Cascade revocation without a TrustStore should still revoke in registry."""
        registry.register(agent_id="agent-1", name="Agent 1", role="analyst")
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            # No trust_store
        )

        revoked = rt.revoke_delegation_chain("agent-1", "manual revocation")

        assert "agent-1" in revoked
        agent = registry.get("agent-1")
        assert agent is not None and agent.status == AgentStatus.REVOKED

    def test_cascade_empty_reason_raises(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Empty reason should raise ValueError."""
        registry.register(agent_id="agent-1", name="Agent 1", role="analyst")
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
        )

        with pytest.raises(ValueError, match="must not be empty"):
            rt.revoke_delegation_chain("agent-1", "")

    def test_revoked_agent_blocked_from_assignment(
        self,
        store: MemoryStore,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """After cascade revocation, agents should not be assignable."""
        _setup_chain(store, registry)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            trust_store=store,
        )

        rt.revoke_delegation_chain("agent-mid", "compromised")

        # Now try to submit a task for the revoked leaf agent
        task_id = rt.submit("test-action", agent_id="agent-leaf")
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.result is not None
        assert task.result.error is not None
        assert "revoked" in task.result.error.lower()
