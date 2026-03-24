# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Bootstrap and initialization — establish trust hierarchy from configuration.

Provides the ``PlatformBootstrap`` class that takes a PactConfig (or YAML path)
and initializes the complete trust hierarchy:

1. Creates genesis record (root of trust)
2. Discovers workspaces from disk
3. Registers agents and teams
4. Creates constraint envelopes for each agent
5. Stores delegation records linking agents to genesis
6. Persists all trust state via TrustStore

The bootstrap is idempotent — re-running updates existing records without
duplicating. This is the ``care init`` equivalent.

Usage:
    config = PactConfig.model_validate(yaml.safe_load(config_yaml))
    bootstrap = PlatformBootstrap(store=SQLiteTrustStore("care.db"))
    result = bootstrap.initialize(config)
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from pact_platform.build.config.env import _load_dotenv
from pact_platform.build.config.schema import (
    AgentConfig,
    PactConfig,
    TeamConfig,
    WorkspaceConfig,
)
from pact_platform.build.workspace.discovery import WorkspaceDiscovery
from pact_platform.trust.store.sqlite_store import GenesisAlreadyExistsError
from pact_platform.trust.store.store import TrustStore

logger = logging.getLogger(__name__)

# Ensure .env is loaded when bootstrap is used as a module entry point
_load_dotenv()


class _NoCommitProxy:
    """Proxy around a ``sqlite3.Connection`` that suppresses auto-commit.

    Store methods use ``with conn:`` which calls ``conn.commit()`` on exit.
    During a bootstrap transaction we need those commits to be no-ops so that
    the entire bootstrap sequence lives inside a single explicit transaction.
    This proxy delegates every attribute/method to the real connection but
    overrides ``__enter__``/``__exit__`` to suppress the implicit commit.
    """

    def __init__(self, real_conn: sqlite3.Connection) -> None:
        object.__setattr__(self, "_real", real_conn)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_real"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_real":
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_real"), name, value)

    def __enter__(self) -> sqlite3.Connection:
        return object.__getattribute__(self, "_real")

    def __exit__(self, *args: object) -> bool:
        # Suppress commit/rollback — the outer transaction manages it.
        return False


class BootstrapResult(BaseModel):
    """Result of a bootstrap initialization."""

    genesis_authority: str = Field(description="Authority ID for the genesis record")
    workspaces_registered: int = Field(default=0, description="Number of workspaces registered")
    workspaces_discovered: int = Field(
        default=0, description="Number of workspaces auto-discovered"
    )
    agents_registered: int = Field(default=0, description="Number of agents registered")
    teams_registered: int = Field(default=0, description="Number of teams registered")
    envelopes_created: int = Field(default=0, description="Number of constraint envelopes created")
    delegations_created: int = Field(default=0, description="Number of delegation records created")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    errors: list[str] = Field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        return len(self.errors) == 0


class PlatformBootstrap:
    """Initializes the PACT trust hierarchy from configuration.

    Given a PactConfig and a TrustStore, creates the complete trust
    hierarchy: genesis → delegations → envelopes → agent registrations.

    The bootstrap is idempotent — calling initialize() multiple times with
    the same config updates existing records without creating duplicates.
    """

    def __init__(self, store: TrustStore) -> None:
        """Initialize with a TrustStore.

        Args:
            store: The TrustStore to persist trust state into. Can be
                MemoryStore, FilesystemStore, or SQLiteTrustStore.
        """
        self._store = store

    @staticmethod
    def load_config(config_path: str | Path) -> PactConfig:
        """Load a PactConfig from a YAML file.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            Parsed and validated PactConfig.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            ValueError: If the YAML is invalid or doesn't match the schema.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with path.open() as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(
                f"Configuration file must contain a YAML mapping, got {type(raw).__name__}"
            )

        return PactConfig.model_validate(raw)

    def initialize(
        self,
        config: PactConfig,
        *,
        workspace_root: str | Path | None = None,
        discover_workspaces: bool = True,
    ) -> BootstrapResult:
        """Initialize the platform trust hierarchy from configuration.

        This is the main entry point. It performs these steps in order:
        1. Create genesis record (root of trust)
        2. Discover workspaces from disk (optional)
        3. Register configured workspaces
        4. Create constraint envelopes
        5. Create delegation records for each agent
        6. Store bootstrap completion marker
        7. Persist all state to the TrustStore

        If the store supports ``_get_connection()`` (e.g. SQLiteTrustStore),
        the entire sequence is wrapped in a single SQLite transaction for
        atomicity. Otherwise (MemoryStore, FilesystemStore) each step commits
        independently.

        Args:
            config: The platform configuration to initialize from.
            workspace_root: Optional root directory for workspace discovery.
                If not provided, workspace discovery is skipped even if
                discover_workspaces is True.
            discover_workspaces: Whether to auto-discover workspaces from
                disk. Requires workspace_root.

        Returns:
            BootstrapResult describing what was created/updated.
        """
        authority = config.genesis.authority
        result = BootstrapResult(genesis_authority=authority)

        # RT4-H7: Check for existing bootstrap completion marker
        marker_key = f"bootstrap:complete:{authority}"
        existing_marker = self._store.get_envelope(marker_key)
        if existing_marker is not None:
            logger.info(
                "Bootstrap has been run before for authority '%s' "
                "(previous run at %s). Re-running bootstrap.",
                authority,
                existing_marker.get("timestamp", "unknown"),
            )

        # RT4-C4: Wrap in a single SQLite transaction when supported.
        # When the store exposes _get_connection() (SQLiteTrustStore) we
        # wrap the entire bootstrap in an explicit BEGIN/COMMIT and inject
        # a _NoCommitProxy so that the store methods' ``with conn:`` blocks
        # do not auto-commit after each operation.
        use_transaction = hasattr(self._store, "_get_connection")
        real_conn: sqlite3.Connection | None = None
        prev_isolation_level: str | None = None

        if use_transaction:
            real_conn = self._store._get_connection()  # type: ignore[attr-defined]
            prev_isolation_level = real_conn.isolation_level
            real_conn.isolation_level = None  # manual commit mode
            real_conn.execute("BEGIN")
            # Replace the cached connection with a proxy that suppresses
            # the auto-commit in ``with conn:`` blocks.
            self._store._local.conn = _NoCommitProxy(real_conn)  # type: ignore[attr-defined]

        try:
            self._execute_bootstrap_steps(config, result, workspace_root, discover_workspaces)

            # RT4-H7: Store bootstrap completion marker
            if result.is_successful:
                marker_data: dict[str, Any] = {
                    "status": "complete",
                    "authority": authority,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "agents_registered": result.agents_registered,
                    "delegations_created": result.delegations_created,
                }
                self._store.store_envelope(marker_key, marker_data)

            if use_transaction and real_conn is not None:
                real_conn.execute("COMMIT")
        except Exception:
            if use_transaction and real_conn is not None:
                real_conn.execute("ROLLBACK")
                logger.error(
                    "Bootstrap transaction rolled back for authority '%s'",
                    authority,
                )
            raise
        finally:
            if use_transaction and real_conn is not None:
                # Restore the real connection and isolation level.
                self._store._local.conn = real_conn  # type: ignore[attr-defined]
                if prev_isolation_level is not None:
                    real_conn.isolation_level = prev_isolation_level

        if result.is_successful:
            logger.info(
                "Bootstrap complete: authority='%s' agents=%d teams=%d workspaces=%d",
                authority,
                result.agents_registered,
                result.teams_registered,
                result.workspaces_registered,
            )
        else:
            logger.warning(
                "Bootstrap completed with %d error(s): %s",
                len(result.errors),
                "; ".join(result.errors),
            )

        return result

    def _execute_bootstrap_steps(
        self,
        config: PactConfig,
        result: BootstrapResult,
        workspace_root: str | Path | None,
        discover_workspaces: bool,
    ) -> None:
        """Execute all bootstrap steps (called within transaction boundary).

        RT5-15: Each step is wrapped in exception handling so that a failure
        in one step is recorded in ``result.errors`` and does not prevent
        subsequent steps from running. This avoids leaving the store in an
        inconsistent state when a single step fails.
        """
        # Step 1: Genesis record
        try:
            self._create_genesis(config, result)
        except Exception as exc:
            error_msg = f"Genesis creation failed for authority '{config.genesis.authority}': {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        # Step 2: Discover workspaces from disk
        all_workspaces = list(config.workspaces)
        if discover_workspaces and workspace_root is not None:
            try:
                discovered = self._discover_workspaces(workspace_root, config, result)
                all_workspaces.extend(discovered)
            except Exception as exc:
                error_msg = f"Workspace discovery failed: {exc}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Step 3: Register workspaces
        try:
            self._register_workspaces(all_workspaces, config, result)
        except Exception as exc:
            error_msg = f"Workspace registration failed: {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        # Step 4: Create constraint envelopes
        try:
            self._create_envelopes(config, result)
        except Exception as exc:
            error_msg = f"Envelope creation failed: {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        # Step 5: Create delegation records for each agent
        try:
            self._create_delegations(config, result)
        except Exception as exc:
            error_msg = f"Delegation creation failed: {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    def _create_genesis(self, config: PactConfig, result: BootstrapResult) -> None:
        """Create the genesis record (root of trust).

        RT5-14: Genesis records are write-once. If the record already exists
        (idempotent re-run), we log it and continue. If the store raises
        ``GenesisAlreadyExistsError``, we catch it gracefully since
        re-running bootstrap on the same authority is expected behavior.
        """
        genesis_data: dict[str, Any] = {
            "authority_id": config.genesis.authority,
            "authority_name": config.genesis.authority_name,
            "policy_reference": config.genesis.policy_reference,
            "platform_name": config.name,
            "config_version": config.version,
            "created_at": datetime.now(UTC).isoformat(),
        }

        # RT4-H5: Call TrustStore protocol methods directly (no hasattr duck-typing)
        try:
            self._store.store_genesis(config.genesis.authority, genesis_data)
            logger.info("Genesis record created for authority '%s'", config.genesis.authority)
        except GenesisAlreadyExistsError:
            logger.info(
                "Genesis record already exists for authority '%s' (idempotent re-run)",
                config.genesis.authority,
            )

    def _discover_workspaces(
        self,
        workspace_root: str | Path,
        config: PactConfig,
        result: BootstrapResult,
    ) -> list[WorkspaceConfig]:
        """Discover workspaces from disk and return configs for new ones."""
        discovery = WorkspaceDiscovery(scan_depth=2)
        try:
            discovered = discovery.discover(workspace_root)
        except (ValueError, OSError) as exc:
            result.errors.append(f"Workspace discovery failed: {exc}")
            return []

        # Filter out workspaces already in config
        existing_ids = {ws.id for ws in config.workspaces}
        new_workspaces: list[WorkspaceConfig] = []

        for dw in discovered:
            if dw.config.id not in existing_ids:
                new_workspaces.append(dw.config)
                result.workspaces_discovered += 1
                logger.info(
                    "Discovered workspace '%s' (%s) at %s",
                    dw.config.id,
                    dw.discovery_method,
                    dw.config.path,
                )

        return new_workspaces

    def _register_workspaces(
        self,
        workspaces: list[WorkspaceConfig],
        config: PactConfig,
        result: BootstrapResult,
    ) -> None:
        """Register workspaces in the trust store."""
        for ws in workspaces:
            ws_data: dict[str, Any] = {
                "workspace_id": ws.id,
                "path": ws.path,
                "description": ws.description,
                "knowledge_base_paths": ws.knowledge_base_paths,
                "authority": config.genesis.authority,
            }
            self._store.store_envelope(f"workspace:{ws.id}", ws_data)
            result.workspaces_registered += 1

    def _create_envelopes(self, config: PactConfig, result: BootstrapResult) -> None:
        """Create constraint envelopes in the trust store."""
        for envelope_config in config.constraint_envelopes:
            envelope_data = envelope_config.model_dump(mode="json")
            envelope_data["authority"] = config.genesis.authority
            envelope_data["created_at"] = datetime.now(UTC).isoformat()
            self._store.store_envelope(envelope_config.id, envelope_data)
            result.envelopes_created += 1

    def _create_delegations(self, config: PactConfig, result: BootstrapResult) -> None:
        """Create delegation records linking agents to genesis authority."""
        authority = config.genesis.authority

        # Register teams
        for team_config in config.teams:
            self._register_team(team_config, authority, result)

        # Register agents and create delegations
        for agent_config in config.agents:
            self._register_agent(agent_config, authority, config, result)

    def _register_team(
        self,
        team_config: TeamConfig,
        authority: str,
        result: BootstrapResult,
    ) -> None:
        """Register a team in the trust store."""
        team_data: dict[str, Any] = {
            "team_id": team_config.id,
            "name": team_config.name,
            "workspace": team_config.workspace,
            "agents": team_config.agents,
            "authority": authority,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._store.store_envelope(f"team:{team_config.id}", team_data)
        result.teams_registered += 1

    def _register_agent(
        self,
        agent_config: AgentConfig,
        authority: str,
        config: PactConfig,
        result: BootstrapResult,
    ) -> None:
        """Register an agent and create its delegation record."""
        # Find which team this agent belongs to
        team_id = ""
        for team in config.teams:
            if agent_config.id in team.agents:
                team_id = team.id
                break

        # Delegation record: authority delegates to this agent
        now = datetime.now(UTC)
        delegation_id = _delegation_id(authority, agent_config.id)
        delegation_data: dict[str, Any] = {
            "delegation_id": delegation_id,
            "delegator_id": authority,
            "delegatee_id": agent_config.id,
            "agent_name": agent_config.name,
            "agent_role": agent_config.role,
            "team_id": team_id,
            "envelope_id": agent_config.constraint_envelope,
            "initial_posture": agent_config.initial_posture.value,
            "capabilities": agent_config.capabilities,
            "created_at": now.isoformat(),
            # RT4-M6: Delegation expiry — default 365 days from creation
            "expires_at": (now + timedelta(days=365)).isoformat(),
        }

        # RT4-H5: Call TrustStore protocol methods directly (no hasattr duck-typing)
        self._store.store_delegation(delegation_id, delegation_data)

        result.agents_registered += 1
        result.delegations_created += 1

        # Store attestation for agent capabilities
        if agent_config.capabilities:
            attestation_id = f"att:{agent_config.id}"
            attestation_data: dict[str, Any] = {
                "attestation_id": attestation_id,
                "agent_id": agent_config.id,
                "capabilities": agent_config.capabilities,
                "authority": authority,
                # RT4-M3: Proper CapabilityAttestation format
                "attestation_type": "capability",
                "delegator_id": authority,
                "delegation_id": delegation_id,
                "created_at": now.isoformat(),
            }
            self._store.store_attestation(attestation_id, attestation_data)


def _delegation_id(delegator_id: str, delegatee_id: str) -> str:
    """Generate a deterministic delegation ID for idempotent bootstrap."""
    content = f"{delegator_id}:{delegatee_id}"
    return f"del-{hashlib.sha256(content.encode()).hexdigest()[:12]}"
