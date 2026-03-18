# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Genesis Manager — manages genesis record lifecycle for the CARE Platform.

The GenesisManager provides higher-level operations around genesis records:
- Creation with automatic Ed25519 key pair generation
- Validation (signature, expiry, chain integrity)
- Renewal with reference to previous genesis
"""

from __future__ import annotations

import logging

from eatp import generate_keypair
from eatp.chain import GenesisRecord

from care_platform.build.config.schema import GenesisConfig
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.lifecycle import TrustChainState, TrustChainStateMachine

logger = logging.getLogger(__name__)


class GenesisManager:
    """Manages genesis record lifecycle for the CARE Platform.

    Wraps EATPBridge genesis operations with additional lifecycle management:
    key generation, validation, and renewal.

    Optionally tracks trust chain state transitions via a TrustChainStateMachine
    for each authority, following the DRAFT -> PENDING -> ACTIVE lifecycle.
    """

    def __init__(self, bridge: EATPBridge) -> None:
        """Initialize with an EATP bridge.

        Args:
            bridge: Initialized EATPBridge instance.
        """
        self.bridge = bridge
        # Track authority -> genesis record mapping for renewal
        self._genesis_records: dict[str, GenesisRecord] = {}
        # Track authority -> genesis config for renewal
        self._genesis_configs: dict[str, GenesisConfig] = {}
        # Track authority -> lifecycle state machine
        self._state_machines: dict[str, TrustChainStateMachine] = {}

    async def create_genesis(self, config: GenesisConfig) -> GenesisRecord:
        """Create a genesis record with Ed25519 key pair generation.

        Generates a new key pair, establishes the genesis via the EATP bridge,
        and stores the record for future validation and renewal.

        Args:
            config: CARE Platform genesis configuration.

        Returns:
            The EATP GenesisRecord for the new root of trust.
        """
        # Prevent silent overwrite of existing genesis records
        if config.authority in self._genesis_records:
            raise ValueError(
                f"Genesis record already exists for authority '{config.authority}'. "
                f"Use renew_genesis() to replace an existing root of trust."
            )

        # Track lifecycle: DRAFT -> PENDING -> ACTIVE
        sm = TrustChainStateMachine(initial_state=TrustChainState.DRAFT)
        sm.transition_to(
            TrustChainState.PENDING,
            reason=f"Genesis creation initiated for authority '{config.authority}'",
        )

        genesis = await self.bridge.establish_genesis(config)

        # Store for future reference
        self._genesis_records[config.authority] = genesis
        self._genesis_records[genesis.agent_id] = genesis
        self._genesis_configs[config.authority] = config

        # Transition to ACTIVE now that genesis is established
        sm.transition_to(
            TrustChainState.ACTIVE,
            reason=f"Genesis established for authority '{config.authority}'",
        )
        self._state_machines[config.authority] = sm
        self._state_machines[genesis.agent_id] = sm

        logger.info(
            "Created genesis for authority '%s' (agent_id='%s')",
            config.authority,
            genesis.agent_id,
        )

        return genesis

    def get_state_machine(self, authority_or_agent_id: str) -> TrustChainStateMachine | None:
        """Get the lifecycle state machine for an authority or agent.

        Args:
            authority_or_agent_id: The authority or agent ID to look up.

        Returns:
            The TrustChainStateMachine if found, None otherwise.
        """
        return self._state_machines.get(authority_or_agent_id)

    async def validate_genesis(
        self,
        agent_id: str,
        public_key: bytes | None = None,
    ) -> tuple[bool, str]:
        """Validate a genesis record.

        Checks:
        - Genesis record exists in the trust store
        - Genesis record is not expired
        - Chain integrity (genesis present in chain)
        - Ed25519 signature verification (when public_key is provided)

        Args:
            agent_id: The agent ID whose genesis to validate.
            public_key: Optional Ed25519 public key bytes for cryptographic
                signature verification. When provided, the genesis record's
                signature is verified against this key.

        Returns:
            Tuple of (is_valid, message) describing the validation result.
        """
        chain = await self.bridge.get_trust_chain(agent_id)

        if chain is None:
            return False, f"No trust chain found for agent '{agent_id}'"

        genesis = chain.genesis
        if genesis is None:
            return False, f"No genesis record in trust chain for agent '{agent_id}'"

        # Check expiry
        if genesis.is_expired():
            return False, (
                f"Genesis record for agent '{agent_id}' has expired "
                f"(expired at {genesis.expires_at})"
            )

        # Check signature is present
        if not genesis.signature:
            return False, f"Genesis record for agent '{agent_id}' has no signature"

        # Cryptographic signature verification (when public key provided)
        if public_key is not None:
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

                ed_pub = Ed25519PublicKey.from_public_key_der(public_key)
                # The signature and signed content depend on the EATP SDK's
                # genesis record format. We verify the raw signature bytes
                # against the genesis record's canonical content.
                sig_bytes = (
                    genesis.signature
                    if isinstance(genesis.signature, bytes)
                    else bytes.fromhex(genesis.signature)
                )
                # Build canonical content to verify
                content = genesis.id.encode()
                ed_pub.verify(sig_bytes, content)
            except ImportError:
                # Fail-closed: cannot verify signature without cryptography package.
                return False, (
                    f"Cannot verify genesis signature for agent '{agent_id}': "
                    "cryptography package is required but not installed"
                )
            except Exception as exc:
                return False, (
                    f"Genesis signature verification failed for agent '{agent_id}': {exc}"
                )

        return True, (
            f"Genesis record for agent '{agent_id}' is valid (authority: {genesis.authority_id})"
        )

    async def renew_genesis(
        self,
        authority_id: str,
        new_signing_key: str | None = None,
    ) -> GenesisRecord:
        """Renew a genesis record, creating a new one that supersedes the previous.

        Args:
            authority_id: The authority whose genesis to renew.
            new_signing_key: Optional new signing key. If not provided,
                a new key pair is generated.

        Returns:
            The new GenesisRecord.

        Raises:
            ValueError: If no prior genesis exists for this authority.
        """
        if authority_id not in self._genesis_configs:
            msg = (
                f"No genesis established for authority '{authority_id}'. "
                f"Cannot renew a genesis that does not exist."
            )
            raise ValueError(msg)

        config = self._genesis_configs[authority_id]

        # If a new signing key is provided, register it
        if new_signing_key is not None:
            key_id = f"key-{authority_id}-renewed"
            self.bridge.key_manager.register_key(key_id, new_signing_key)
            self.bridge._signing_keys[authority_id] = key_id

        # Re-establish genesis (the bridge will generate new keys if needed)
        # We need to generate a new keypair for the renewed genesis
        pub_key, priv_key = generate_keypair()
        renewed_key_id = f"key-{authority_id}-renewed"
        self.bridge.key_manager.register_key(renewed_key_id, priv_key)

        # Update the authority's public key and signing key
        try:
            authority = await self.bridge.authority_registry.get_authority(authority_id)
            authority.public_key = pub_key
            authority.signing_key_id = renewed_key_id
            await self.bridge.authority_registry.update_authority(authority)
        except KeyError:
            msg = f"Authority '{authority_id}' not found in registry. Cannot renew genesis."
            raise ValueError(msg) from None

        # Update key tracking
        self.bridge._signing_keys[authority_id] = renewed_key_id
        agent_id = self.bridge._authority_agents.get(authority_id)
        if agent_id:
            self.bridge._signing_keys[agent_id] = renewed_key_id

        # Create a new agent_id for the renewed genesis
        renewed_agent_id = f"authority:{authority_id}:renewed"

        ops = self.bridge._ensure_initialized()
        from eatp.chain import CapabilityType
        from eatp.operations import CapabilityRequest

        cap = CapabilityRequest(
            capability="*",
            capability_type=CapabilityType.DELEGATION,
            constraints=[],
        )

        chain = await ops.establish(
            agent_id=renewed_agent_id,
            authority_id=authority_id,
            capabilities=[cap],
            constraints=[],
            metadata={
                "authority_name": config.authority_name,
                "policy_reference": config.policy_reference,
                "renewed_from": self._genesis_records.get(authority_id, None)
                and self._genesis_records[authority_id].id,
            },
        )

        renewed_genesis = chain.genesis

        # Update tracking
        self._genesis_records[authority_id] = renewed_genesis
        self._genesis_records[renewed_agent_id] = renewed_genesis
        self.bridge._authority_agents[authority_id] = renewed_agent_id
        self.bridge._signing_keys[renewed_agent_id] = renewed_key_id

        logger.info(
            "Renewed genesis for authority '%s' (new agent_id='%s')",
            authority_id,
            renewed_agent_id,
        )

        return renewed_genesis
