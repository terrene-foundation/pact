# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""EATP Bridge — connects CARE Platform models to EATP SDK operations.

This bridge layer translates between CARE Platform configuration models
(GenesisConfig, AgentConfig, ConstraintEnvelopeConfig) and the EATP SDK's
trust operations (ESTABLISH, DELEGATE, VERIFY, AUDIT).

The bridge maintains:
- An authority registry for organizational authorities
- A key manager for Ed25519 signing keys
- A trust store for trust lineage chains
- A mapping of agent IDs to their signing key IDs
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from eatp import InMemoryTrustStore, TrustKeyManager, TrustOperations, generate_keypair
from eatp.authority import (
    AuthorityPermission,
    AuthorityType,
    OrganizationalAuthority,
)
from eatp.chain import (
    ActionResult,
    AuditAnchor,
    CapabilityType,
    DelegationRecord,
    GenesisRecord,
    TrustLineageChain,
    VerificationLevel,
    VerificationResult,
)
from eatp.exceptions import TrustChainNotFoundError
from eatp.operations import CapabilityRequest
from eatp.store import TrustStore

from care_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    GenesisConfig,
)
from care_platform.trust.attestation import CapabilityAttestation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-Memory Authority Registry (satisfies AuthorityRegistryProtocol)
# ---------------------------------------------------------------------------


class InMemoryAuthorityRegistry:
    """Simple in-memory authority registry for CARE Platform.

    Satisfies the EATP SDK AuthorityRegistryProtocol. Production deployments
    would replace this with a DataFlow-backed implementation.
    """

    def __init__(self) -> None:
        self._authorities: dict[str, OrganizationalAuthority] = {}

    async def initialize(self) -> None:
        """No-op for in-memory implementation."""

    async def get_authority(
        self,
        authority_id: str,
        include_inactive: bool = False,
    ) -> OrganizationalAuthority:
        """Retrieve an authority by ID.

        Raises:
            KeyError: If authority not found.
        """
        auth = self._authorities.get(authority_id)
        if auth is None:
            msg = f"Authority not found: {authority_id}"
            raise KeyError(msg)
        if not auth.is_active and not include_inactive:
            msg = f"Authority is inactive: {authority_id}"
            raise KeyError(msg)
        return auth

    async def update_authority(self, authority: OrganizationalAuthority) -> None:
        """Store or update an authority."""
        self._authorities[authority.id] = authority

    def register(self, authority: OrganizationalAuthority) -> None:
        """Synchronous convenience method for registration."""
        self._authorities[authority.id] = authority


# ---------------------------------------------------------------------------
# Verification level mapping
# ---------------------------------------------------------------------------

_VERIFICATION_LEVEL_MAP: dict[str, VerificationLevel] = {
    "QUICK": VerificationLevel.QUICK,
    "STANDARD": VerificationLevel.STANDARD,
    "FULL": VerificationLevel.FULL,
}

# ---------------------------------------------------------------------------
# Action result mapping
# ---------------------------------------------------------------------------

_ACTION_RESULT_MAP: dict[str, ActionResult] = {
    "SUCCESS": ActionResult.SUCCESS,
    "FAILURE": ActionResult.FAILURE,
    "DENIED": ActionResult.DENIED,
    "PARTIAL": ActionResult.PARTIAL,
}


# ---------------------------------------------------------------------------
# EATP Bridge
# ---------------------------------------------------------------------------


class EATPBridge:
    """Bridge between CARE Platform and EATP SDK.

    Translates CARE Platform configuration models into EATP SDK operations,
    managing the full trust lifecycle: ESTABLISH, DELEGATE, VERIFY, AUDIT.
    """

    def __init__(self, store: TrustStore | None = None) -> None:
        """Initialize with optional EATP SDK trust store.

        Args:
            store: Trust store for persisting chains. Defaults to InMemoryTrustStore.
        """
        self.store: TrustStore = store or InMemoryTrustStore()
        self.key_manager: TrustKeyManager = TrustKeyManager()
        self.authority_registry: InMemoryAuthorityRegistry = InMemoryAuthorityRegistry()
        self.ops: TrustOperations | None = None

        # Internal state tracking
        self._signing_keys: dict[str, str] = {}  # authority/agent_id -> key_id
        self._authority_agents: dict[str, str] = {}  # authority_id -> agent_id (genesis)
        self._delegation_parents: dict[str, str] = {}  # delegatee_id -> delegator_id
        self._genesis_agents: set[str] = set()  # agent_ids that are genesis roots
        self._revoked_agents: set[str] = set()  # agent_ids that have been revoked
        # RT-26: Capability attestation registry
        self._attestations: dict[str, CapabilityAttestation] = {}  # agent_id -> attestation

    async def initialize(self) -> None:
        """Initialize the bridge components (store, registry, operations)."""
        await self.store.initialize()
        await self.authority_registry.initialize()
        self.ops = TrustOperations(
            authority_registry=self.authority_registry,
            key_manager=self.key_manager,
            trust_store=self.store,
        )

    def _ensure_initialized(self) -> TrustOperations:
        """Ensure the bridge has been initialized.

        Returns:
            The TrustOperations instance.

        Raises:
            RuntimeError: If initialize() has not been called.
        """
        if self.ops is None:
            msg = (
                "EATPBridge has not been initialized. "
                "Call 'await bridge.initialize()' before using bridge operations."
            )
            raise RuntimeError(msg)
        return self.ops

    # ------------------------------------------------------------------
    # Constraint Mapping
    # ------------------------------------------------------------------

    def map_envelope_to_constraints(self, config: ConstraintEnvelopeConfig) -> list[str]:
        """Map a CARE ConstraintEnvelopeConfig to EATP constraint strings.

        The five CARE constraint dimensions map to EATP constraints:
        - Financial   -> "budget:{max_spend_usd}"
        - Operational -> "allow:{action}" for each allowed action
        - Temporal    -> "time:{start}-{end}"
        - Data Access -> "read:{path}" / "write:{path}"
        - Communication -> "comm:internal_only" or "channel:{name}"

        Args:
            config: CARE Platform constraint envelope configuration.

        Returns:
            List of EATP constraint strings.
        """
        constraints: list[str] = []

        # Financial (M23/2301: financial config may be None)
        if config.financial is not None:
            constraints.append(f"budget:{config.financial.max_spend_usd}")
            if config.financial.requires_approval_above_usd is not None:
                constraints.append(
                    f"approval_threshold:{config.financial.requires_approval_above_usd}"
                )
            # RT-12: Include cumulative API budget
            if config.financial.api_cost_budget_usd is not None:
                constraints.append(f"api_budget:{config.financial.api_cost_budget_usd}")

        # Operational
        for action in config.operational.allowed_actions:
            constraints.append(f"allow:{action}")
        for action in config.operational.blocked_actions:
            constraints.append(f"block:{action}")
        if config.operational.max_actions_per_day is not None:
            constraints.append(f"rate_limit:{config.operational.max_actions_per_day}")

        # Temporal
        if config.temporal.active_hours_start and config.temporal.active_hours_end:
            constraints.append(
                f"time:{config.temporal.active_hours_start}-{config.temporal.active_hours_end}"
            )
        if config.temporal.timezone and config.temporal.timezone != "UTC":
            constraints.append(f"timezone:{config.temporal.timezone}")
        # RT-12: Include blackout periods
        for period in config.temporal.blackout_periods:
            constraints.append(f"blackout:{period}")

        # Data Access
        for path in config.data_access.read_paths:
            constraints.append(f"read:{path}")
        for path in config.data_access.write_paths:
            constraints.append(f"write:{path}")
        # RT-12: Include blocked data types
        for dtype in config.data_access.blocked_data_types:
            constraints.append(f"block_data:{dtype}")

        # Communication
        if config.communication.internal_only:
            constraints.append("comm:internal_only")
        for channel in config.communication.allowed_channels:
            constraints.append(f"channel:{channel}")
        if config.communication.external_requires_approval:
            constraints.append("comm:external_requires_approval")

        return constraints

    # ------------------------------------------------------------------
    # ESTABLISH
    # ------------------------------------------------------------------

    async def establish_genesis(
        self,
        genesis_config: GenesisConfig,
    ) -> GenesisRecord:
        """Create a genesis record from a CARE Platform GenesisConfig.

        Generates an Ed25519 key pair, registers the authority, and
        calls EATP SDK establish to create the root of trust.

        Args:
            genesis_config: CARE Platform genesis configuration.

        Returns:
            The EATP GenesisRecord for the established authority.
        """
        ops = self._ensure_initialized()

        # Generate key pair for the authority
        pub_key, priv_key = generate_keypair()
        key_id = f"key-{genesis_config.authority}"

        self.key_manager.register_key(key_id, priv_key)
        self._signing_keys[genesis_config.authority] = key_id

        # Create and register the organizational authority
        authority = OrganizationalAuthority(
            id=genesis_config.authority,
            name=genesis_config.authority_name,
            authority_type=AuthorityType.ORGANIZATION,
            public_key=pub_key,
            signing_key_id=key_id,
            permissions=[
                AuthorityPermission.CREATE_AGENTS,
                AuthorityPermission.DELEGATE_TRUST,
                AuthorityPermission.GRANT_CAPABILITIES,
                AuthorityPermission.REVOKE_CAPABILITIES,
            ],
            metadata={
                "policy_reference": genesis_config.policy_reference,
            },
        )
        self.authority_registry.register(authority)

        # Build the agent_id for the genesis authority
        agent_id = f"authority:{genesis_config.authority}"

        # The genesis authority (trust root) uses wildcard capabilities so it
        # can delegate any capability downstream. This is acceptable for the
        # root — RT-11 restricts wildcards in *delegatee* capabilities only.
        caps = [
            CapabilityRequest(
                capability="*",
                capability_type=CapabilityType.DELEGATION,
                constraints=[],
            ),
            CapabilityRequest(
                capability="*",
                capability_type=CapabilityType.ACTION,
                constraints=[],
            ),
            CapabilityRequest(
                capability="*",
                capability_type=CapabilityType.ACCESS,
                constraints=[],
            ),
        ]

        chain = await ops.establish(
            agent_id=agent_id,
            authority_id=genesis_config.authority,
            capabilities=caps,
            constraints=[],
            metadata={
                "authority_name": genesis_config.authority_name,
                "policy_reference": genesis_config.policy_reference,
            },
        )

        # Track the authority -> agent mapping
        self._authority_agents[genesis_config.authority] = agent_id
        # Also map the agent_id to the key_id so delegation can find it
        self._signing_keys[agent_id] = key_id
        # Mark as genesis root (depth 0)
        self._genesis_agents.add(agent_id)

        logger.info(
            "Established genesis for authority '%s' with agent_id '%s'",
            genesis_config.authority,
            agent_id,
        )

        return chain.genesis

    # ------------------------------------------------------------------
    # DELEGATE
    # ------------------------------------------------------------------

    async def delegate(
        self,
        delegator_id: str,
        delegate_agent_config: AgentConfig,
        envelope_config: ConstraintEnvelopeConfig,
    ) -> DelegationRecord:
        """Create a delegation from a CARE Platform agent/authority to another agent.

        Maps the CARE constraint envelope to EATP constraints and delegates
        the specified capabilities.

        Args:
            delegator_id: ID of the delegating agent/authority.
            delegate_agent_config: Configuration of the agent receiving delegation.
            envelope_config: Constraint envelope governing the delegatee.

        Returns:
            The EATP DelegationRecord.

        Raises:
            ValueError: If the delegator has no signing key (not established).
        """
        ops = self._ensure_initialized()

        # Ensure the delegator has a signing key
        if delegator_id not in self._signing_keys:
            msg = (
                f"No signing key found for delegator '{delegator_id}'. "
                f"The delegator must be established or delegated before they can delegate."
            )
            raise ValueError(msg)

        # Map CARE constraints to EATP constraints
        constraints = self.map_envelope_to_constraints(envelope_config)

        # Generate a key pair for the delegatee
        pub_key, priv_key = generate_keypair()
        delegatee_key_id = f"key-{delegate_agent_config.id}"
        self.key_manager.register_key(delegatee_key_id, priv_key)
        self._signing_keys[delegate_agent_config.id] = delegatee_key_id

        # RT-11: Build explicit capability list from agent config.
        # Never inject wildcards — capabilities are derived from the agent
        # configuration and constraint envelope, not granted blanket access.
        capabilities_to_delegate = list(delegate_agent_config.capabilities)

        # Delegate via EATP SDK
        delegation = await ops.delegate(
            delegator_id=delegator_id,
            delegatee_id=delegate_agent_config.id,
            task_id=f"task-{delegate_agent_config.id}-{uuid4().hex[:8]}",
            capabilities=capabilities_to_delegate,
            additional_constraints=constraints,
            metadata={
                "agent_name": delegate_agent_config.name,
                "agent_role": delegate_agent_config.role,
                "envelope_id": envelope_config.id,
            },
        )

        # Track the delegation parent relationship for chain walking
        self._delegation_parents[delegate_agent_config.id] = delegator_id

        # RT-26: Create and store a CapabilityAttestation for the delegatee
        # RT2-20: Use real delegation record ID, not synthetic
        attestation = CapabilityAttestation(
            attestation_id=f"att-{delegate_agent_config.id}",
            agent_id=delegate_agent_config.id,
            delegation_id=delegation.id,
            constraint_envelope_id=envelope_config.id,
            capabilities=list(delegate_agent_config.capabilities),
            issuer_id=delegator_id,
        )
        self._attestations[delegate_agent_config.id] = attestation

        logger.info(
            "Delegated from '%s' to '%s' with %d capabilities and %d constraints (attestation %s)",
            delegator_id,
            delegate_agent_config.id,
            len(delegate_agent_config.capabilities),
            len(constraints),
            attestation.attestation_id,
        )

        return delegation

    # ------------------------------------------------------------------
    # REVOCATION
    # ------------------------------------------------------------------

    def revoke_agent(self, agent_id: str) -> None:
        """Mark an agent as revoked. Revoked agents will fail verification.

        Also revokes the agent's capability attestation if one exists.

        Args:
            agent_id: The agent to revoke.
        """
        self._revoked_agents.add(agent_id)
        # RT-26: Also revoke the agent's attestation
        att = self._attestations.get(agent_id)
        if att is not None and not att.revoked:
            att.revoke(f"Agent {agent_id} revoked")
        logger.info("Agent '%s' revoked in EATP bridge", agent_id)

    # ------------------------------------------------------------------
    # RT-26: Attestation queries
    # ------------------------------------------------------------------

    def get_attestation(self, agent_id: str) -> CapabilityAttestation | None:
        """Get the capability attestation for an agent.

        Args:
            agent_id: The agent whose attestation to retrieve.

        Returns:
            The CapabilityAttestation if found, None otherwise.
        """
        return self._attestations.get(agent_id)

    def verify_capability(self, agent_id: str, capability: str) -> bool:
        """Check if an agent has an attested capability that is still valid.

        Args:
            agent_id: The agent to check.
            capability: The capability to verify.

        Returns:
            True if the agent has a valid attestation including the capability.
        """
        att = self._attestations.get(agent_id)
        if att is None:
            return False
        if not att.is_valid:
            return False
        return att.has_capability(capability)

    # ------------------------------------------------------------------
    # VERIFY
    # ------------------------------------------------------------------

    async def verify_action(
        self,
        agent_id: str,
        action: str,
        resource: str = "",
        level: str = "STANDARD",
    ) -> VerificationResult:
        """Verify an agent action through the EATP SDK.

        Checks revocation status before EATP verification. Revoked agents
        are rejected immediately without consulting the trust chain.

        Args:
            agent_id: The agent attempting the action.
            action: The action being attempted.
            resource: The resource being acted upon (optional).
            level: Verification level - "QUICK", "STANDARD", or "FULL".

        Returns:
            EATP VerificationResult with valid/invalid status and reason.
        """
        ops = self._ensure_initialized()

        # Check revocation before EATP verification
        if agent_id in self._revoked_agents:
            verification_level = _VERIFICATION_LEVEL_MAP.get(
                level.upper(), VerificationLevel.STANDARD
            )
            logger.warning(
                "Verification rejected for revoked agent '%s' action '%s'",
                agent_id,
                action,
            )
            return VerificationResult(
                valid=False,
                level=verification_level,
                reason=f"Agent '{agent_id}' has been revoked",
            )

        verification_level = _VERIFICATION_LEVEL_MAP.get(level.upper())
        if verification_level is None:
            msg = (
                f"Invalid verification level '{level}'. "
                f"Must be one of: {', '.join(_VERIFICATION_LEVEL_MAP.keys())}"
            )
            raise ValueError(msg)

        try:
            result = await ops.verify(
                agent_id=agent_id,
                action=action,
                resource=resource or None,
                level=verification_level,
            )
        except Exception as exc:
            logger.warning(
                "Verification failed for agent '%s' action '%s': %s",
                agent_id,
                action,
                exc,
            )
            return VerificationResult(
                valid=False,
                level=verification_level,
                reason=f"Verification error: {exc}",
            )

        return result

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------

    async def record_audit(
        self,
        agent_id: str,
        action: str,
        resource: str,
        result: str,
        reasoning: str = "",
    ) -> AuditAnchor:
        """Record an audit anchor through the EATP SDK.

        Args:
            agent_id: The agent that performed the action.
            action: The action performed.
            resource: The resource acted upon.
            result: Action result - "SUCCESS", "FAILURE", "DENIED", or "PARTIAL".
            reasoning: Optional reasoning trace for the action.

        Returns:
            EATP AuditAnchor recording the action.

        Raises:
            ValueError: If the result string is not a valid ActionResult.
        """
        ops = self._ensure_initialized()

        action_result = _ACTION_RESULT_MAP.get(result.upper())
        if action_result is None:
            msg = (
                f"Invalid action result '{result}'. "
                f"Must be one of: {', '.join(_ACTION_RESULT_MAP.keys())}"
            )
            raise ValueError(msg)

        context_data: dict[str, Any] = {}
        if reasoning:
            context_data["reasoning"] = reasoning

        anchor = await ops.audit(
            agent_id=agent_id,
            action=action,
            resource=resource or None,
            result=action_result,
            context_data=context_data if context_data else None,
        )

        logger.info(
            "Recorded audit anchor for agent '%s' action '%s' result '%s'",
            agent_id,
            action,
            result,
        )

        return anchor

    # ------------------------------------------------------------------
    # Trust Chain Retrieval
    # ------------------------------------------------------------------

    async def get_trust_chain(self, agent_id: str) -> TrustLineageChain | None:
        """Get an agent's full trust lineage chain.

        Args:
            agent_id: The agent whose chain to retrieve.

        Returns:
            The TrustLineageChain if found, None otherwise.
        """
        try:
            chain = await self.store.get_chain(agent_id)
            return chain
        except TrustChainNotFoundError:
            # Agent has no trust chain — legitimate "not found" case
            return None
        except Exception as exc:
            # Fail-closed: store errors (network, corruption, etc.) are not
            # "chain not found". Re-raise so callers treat this as a trust
            # failure, not as "chain doesn't exist".
            logger.error(
                "Trust store error retrieving chain for agent '%s': %s. "
                "Fail-closed: treating as trust failure.",
                agent_id,
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Key Management Helpers
    # ------------------------------------------------------------------

    def has_signing_key(self, identifier: str) -> bool:
        """Check if a signing key exists for the given identifier.

        Args:
            identifier: Authority ID or agent ID to check.

        Returns:
            True if a signing key is registered.
        """
        return identifier in self._signing_keys

    def get_transitive_depth(self, agent_id: str) -> int:
        """Get the transitive delegation depth from genesis to this agent.

        Walks the _delegation_parents map to count hops from a genesis root.
        Genesis agents have depth 0, direct delegates depth 1, etc.

        Args:
            agent_id: The agent whose depth to calculate.

        Returns:
            The delegation depth (0 if genesis or unknown).
        """
        depth = 0
        current = agent_id
        visited: set[str] = set()
        while current in self._delegation_parents:
            if current in visited:
                logger.warning("Cycle detected in delegation chain at '%s'", current)
                break
            visited.add(current)
            current = self._delegation_parents[current]
            depth += 1
        return depth

    def get_delegation_tree(self) -> dict[str, list[str]]:
        """RT2-21: Get the delegation tree in parent -> [children] format.

        Returns the inverted delegation parent map as a tree structure
        compatible with RevocationManager.register_delegation(). This allows
        the RevocationManager to synchronize its delegation tree from the
        EATP bridge's authoritative source, eliminating dual bookkeeping.

        Returns:
            Dictionary mapping delegator_id to list of delegatee_ids.
        """
        tree: dict[str, list[str]] = {}
        for delegatee, delegator in self._delegation_parents.items():
            if delegator not in tree:
                tree[delegator] = []
            if delegatee not in tree[delegator]:
                tree[delegator].append(delegatee)
        return tree

    def get_delegation_ancestors(self, agent_id: str) -> list[str]:
        """Get the list of ancestors from this agent back to genesis.

        Returns a list starting with the agent_id and ending with the
        genesis root. Useful for chain walking.

        Args:
            agent_id: The agent whose ancestors to retrieve.

        Returns:
            List of agent IDs from the agent back to the genesis root.
        """
        ancestors: list[str] = [agent_id]
        current = agent_id
        visited: set[str] = set()
        while current in self._delegation_parents:
            if current in visited:
                break
            visited.add(current)
            current = self._delegation_parents[current]
            ancestors.append(current)
        return ancestors
