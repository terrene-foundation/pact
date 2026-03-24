# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust store backup and restore.

Exports all trust data from a TrustStore to a JSON file and imports
it back. Preserves append-only semantics — the backup includes the full
audit trail (all audit anchors, posture changes). Data integrity is
validated on restore.

Usage::

    from pact_platform.trust.store.backup import backup_store, restore_store
    from pact_platform.trust.store.sqlite_store import SQLiteTrustStore

    store = SQLiteTrustStore("care.db")
    backup_store(store, "backup.json")

    new_store = SQLiteTrustStore("care_restored.db")
    restore_store(new_store, "backup.json")
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Backup format version — increment when the format changes
_BACKUP_FORMAT_VERSION = 1

# Required top-level keys in a valid backup file
_REQUIRED_KEYS = frozenset(
    {
        "metadata",
        "envelopes",
        "audit_anchors",
        "posture_changes",
        "revocations",
        "genesis_records",
        "delegations",
        "attestations",
        "org_definitions",
    }
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BackupError(Exception):
    """Raised when a backup operation fails."""

    pass


class RestoreError(Exception):
    """Raised when a restore operation fails."""

    pass


# ---------------------------------------------------------------------------
# Internal: extract data from a store
# ---------------------------------------------------------------------------


def _extract_all_data(store: object) -> dict:
    """Extract all trust data from a store into a serializable dict.

    This reads data through the TrustStore protocol methods. Because
    posture_changes are keyed by agent_id and there is no ``list_all_agents``
    method, we extract what we can. For stores that support direct table
    access (SQLite, PostgreSQL), we use that; otherwise we use the
    public API with known agent IDs from other entity types.
    """
    # Envelopes
    envelopes = store.list_envelopes()

    # Audit anchors — query with no filters, high limit
    audit_anchors = store.query_anchors(limit=1_000_000)

    # Revocations
    revocations = store.get_revocations()

    # Collect all known agent IDs from envelopes, anchors, revocations
    agent_ids: set[str] = set()
    for env in envelopes:
        aid = env.get("agent_id")
        if aid:
            agent_ids.add(aid)
    for anc in audit_anchors:
        aid = anc.get("agent_id")
        if aid:
            agent_ids.add(aid)
    for rev in revocations:
        aid = rev.get("agent_id")
        if aid:
            agent_ids.add(aid)

    # Posture changes per agent
    posture_changes: dict[str, list[dict]] = {}
    for agent_id in agent_ids:
        history = store.get_posture_history(agent_id)
        if history:
            posture_changes[agent_id] = history

    # Genesis records — we need to try known authority IDs
    # Collect from delegations
    genesis_records: list[dict] = []
    delegations: list[dict] = []
    attestations: list[dict] = []
    org_definitions: list[dict] = []

    # For delegations and attestations, we need to iterate known agents
    for agent_id in agent_ids:
        for deleg in store.get_delegations_for(agent_id):
            # Avoid duplicates by checking delegation_id
            if not any(d.get("delegation_id") == deleg.get("delegation_id") for d in delegations):
                delegations.append(deleg)
        for att in store.get_attestations_for(agent_id):
            if not any(a.get("attestation_id") == att.get("attestation_id") for a in attestations):
                attestations.append(att)

    # Collect authority IDs from delegations for genesis records
    authority_ids: set[str] = set()
    for deleg in delegations:
        for key in ("delegator_id", "delegatee_id"):
            aid = deleg.get(key)
            if aid:
                authority_ids.add(aid)
    # Also add all known agent IDs as potential authority IDs
    authority_ids.update(agent_ids)

    for auth_id in authority_ids:
        genesis = store.get_genesis(auth_id)
        if genesis is not None:
            genesis_records.append(genesis)

    # Org definitions — try to get from known org IDs
    # Check if store has a way to list org IDs; if not, try from data
    for env in envelopes:
        org_id = env.get("org_id")
        if org_id:
            org_def = store.get_org_definition(org_id)
            if org_def and not any(o.get("org_id") == org_id for o in org_definitions):
                org_definitions.append(org_def)

    # For SQLite/PG stores, try direct table access for completeness
    if hasattr(store, "_get_connection"):
        try:
            conn = store._get_connection()
            # Genesis records
            rows = conn.execute("SELECT data FROM genesis_records").fetchall()
            for row in rows:
                data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if not any(
                    g.get("authority_id") == data.get("authority_id") for g in genesis_records
                ):
                    genesis_records.append(data)
            # Org definitions
            rows = conn.execute("SELECT data FROM org_definitions").fetchall()
            for row in rows:
                data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if not any(o.get("org_id") == data.get("org_id") for o in org_definitions):
                    org_definitions.append(data)
            # Posture changes — get all agent_ids directly
            rows = conn.execute("SELECT DISTINCT agent_id FROM posture_changes").fetchall()
            for row in rows:
                aid = row[0]
                if aid not in posture_changes:
                    history = store.get_posture_history(aid)
                    if history:
                        posture_changes[aid] = history
            # Delegations — get all
            rows = conn.execute("SELECT data FROM delegations").fetchall()
            for row in rows:
                data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if not any(
                    d.get("delegation_id") == data.get("delegation_id") for d in delegations
                ):
                    delegations.append(data)
            # Attestations — get all
            rows = conn.execute("SELECT data FROM attestations").fetchall()
            for row in rows:
                data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if not any(
                    a.get("attestation_id") == data.get("attestation_id") for a in attestations
                ):
                    attestations.append(data)
        except Exception as exc:
            logger.debug("Direct table access not available: %s", exc)

    # For MemoryStore — access internal state if available
    if hasattr(store, "_genesis"):
        for auth_id, data in store._genesis.items():
            if not any(g.get("authority_id") == auth_id for g in genesis_records):
                genesis_records.append(data)
    if hasattr(store, "_org_definitions"):
        for org_id, data in store._org_definitions.items():
            if not any(o.get("org_id") == org_id for o in org_definitions):
                org_definitions.append(data)
    if hasattr(store, "_delegations"):
        for del_id, data in store._delegations.items():
            if not any(d.get("delegation_id") == del_id for d in delegations):
                delegations.append(data)
    if hasattr(store, "_attestations"):
        for att_id, data in store._attestations.items():
            if not any(a.get("attestation_id") == att_id for a in attestations):
                attestations.append(data)
    if hasattr(store, "_posture"):
        for agent_id, changes in store._posture.items():
            if agent_id not in posture_changes and changes:
                posture_changes[agent_id] = changes

    return {
        "metadata": {
            "version": _BACKUP_FORMAT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
        },
        "envelopes": envelopes,
        "audit_anchors": audit_anchors,
        "posture_changes": posture_changes,
        "revocations": revocations,
        "genesis_records": genesis_records,
        "delegations": delegations,
        "attestations": attestations,
        "org_definitions": org_definitions,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def backup_store(store: object, output_path: str | Path) -> None:
    """Export all trust data from *store* to a JSON file at *output_path*.

    Args:
        store: A TrustStore implementation (MemoryStore, SQLiteTrustStore, etc.).
        output_path: Path where the backup JSON file will be written.

    Raises:
        BackupError: If the backup file cannot be written.
    """
    output_path = Path(output_path)
    try:
        data = _extract_all_data(store)
        output_path.write_text(json.dumps(data, default=str, indent=2))
        logger.info("Backup written to %s", output_path)
    except Exception as exc:
        raise BackupError(f"Failed to write backup to {output_path}: {exc}") from exc


def restore_store(store: object, input_path: str | Path) -> None:
    """Import trust data from a JSON backup file into *store*.

    Preserves append-only semantics: audit anchors and posture changes
    are appended, genesis records respect write-once.

    Args:
        store: A TrustStore implementation to restore into.
        input_path: Path to the JSON backup file.

    Raises:
        RestoreError: If the file is missing, corrupt, or has invalid structure.
        FileNotFoundError: If input_path does not exist.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Backup file not found: {input_path}")

    try:
        raw = input_path.read_text()
    except OSError as exc:
        raise RestoreError(f"Failed to read backup file {input_path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RestoreError(f"Backup file is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise RestoreError(f"Invalid backup structure: expected dict, got {type(data).__name__}")

    # Validate required keys
    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise RestoreError(f"Invalid backup structure: missing required keys: {sorted(missing)}")

    # Validate metadata
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        raise RestoreError("Invalid backup: metadata must be a dict")
    if "version" not in metadata:
        raise RestoreError("Invalid backup: metadata missing 'version'")
    if "created_at" not in metadata:
        raise RestoreError("Invalid backup: metadata missing 'created_at'")

    logger.info(
        "Restoring from backup v%s created at %s",
        metadata.get("version"),
        metadata.get("created_at"),
    )

    # Restore in dependency order: genesis first (trust roots), then delegations,
    # then envelopes, then the rest.

    # Genesis records (write-once — store_genesis respects this)
    for genesis in data.get("genesis_records", []):
        authority_id = genesis.get("authority_id")
        if not authority_id:
            logger.warning("Skipping genesis record with no authority_id: %s", genesis)
            continue
        store.store_genesis(authority_id, genesis)

    # Delegation records
    for delegation in data.get("delegations", []):
        delegation_id = delegation.get("delegation_id")
        if not delegation_id:
            logger.warning("Skipping delegation with no delegation_id: %s", delegation)
            continue
        store.store_delegation(delegation_id, delegation)

    # Envelopes
    for envelope in data.get("envelopes", []):
        envelope_id = envelope.get("envelope_id")
        if not envelope_id:
            logger.warning("Skipping envelope with no envelope_id: %s", envelope)
            continue
        store.store_envelope(envelope_id, envelope)

    # Audit anchors (append-only — store_audit_anchor uses INSERT OR IGNORE)
    for anchor in data.get("audit_anchors", []):
        anchor_id = anchor.get("anchor_id")
        if not anchor_id:
            logger.warning("Skipping anchor with no anchor_id: %s", anchor)
            continue
        store.store_audit_anchor(anchor_id, anchor)

    # Posture changes (append-only)
    for agent_id, changes in data.get("posture_changes", {}).items():
        for change in changes:
            store.store_posture_change(agent_id, change)

    # Revocations
    for revocation in data.get("revocations", []):
        revocation_id = revocation.get("revocation_id")
        if not revocation_id:
            logger.warning("Skipping revocation with no revocation_id: %s", revocation)
            continue
        store.store_revocation(revocation_id, revocation)

    # Attestations
    for attestation in data.get("attestations", []):
        attestation_id = attestation.get("attestation_id")
        if not attestation_id:
            logger.warning("Skipping attestation with no attestation_id: %s", attestation)
            continue
        store.store_attestation(attestation_id, attestation)

    # Org definitions
    for org_def in data.get("org_definitions", []):
        org_id = org_def.get("org_id")
        if not org_id:
            logger.warning("Skipping org definition with no org_id: %s", org_def)
            continue
        store.store_org_definition(org_id, org_def)

    logger.info("Restore complete")
