# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Storage protocol and implementations for trust objects.

Provides a TrustStore protocol (abstract interface) with two implementations:
- MemoryStore: In-memory dict-based storage for development/testing
- FilesystemStore: JSON file-based storage for single-instance persistence

DataFlow integration can be added as a third implementation.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class TrustStore(Protocol):
    """Abstract storage interface for trust objects.

    All methods accept and return plain dicts (JSON-serializable) so that
    callers are not tied to a specific serialization format. Filtering
    uses ISO-8601 timestamp strings stored in the ``timestamp`` field.
    """

    # --- Envelopes ---

    def store_envelope(self, envelope_id: str, data: dict) -> None: ...

    def get_envelope(self, envelope_id: str) -> dict | None: ...

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]: ...

    # --- Audit Anchors ---

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None: ...

    def get_audit_anchor(self, anchor_id: str) -> dict | None: ...

    def query_anchors(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        verification_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]: ...

    # --- Posture Changes ---

    def store_posture_change(self, agent_id: str, data: dict) -> None: ...

    def get_posture_history(self, agent_id: str) -> list[dict]: ...

    # --- Revocations ---

    def store_revocation(self, revocation_id: str, data: dict) -> None: ...

    def get_revocations(self, agent_id: str | None = None) -> list[dict]: ...

    # --- Genesis Records ---

    def store_genesis(self, authority_id: str, data: dict) -> None: ...

    def get_genesis(self, authority_id: str) -> dict | None: ...

    # --- Delegation Records ---

    def store_delegation(self, delegation_id: str, data: dict) -> None: ...

    def get_delegation(self, delegation_id: str) -> dict | None: ...

    def get_delegations_for(self, agent_id: str) -> list[dict]: ...

    # --- Attestations ---

    def store_attestation(self, attestation_id: str, data: dict) -> None: ...

    def get_attestation(self, attestation_id: str) -> dict | None: ...

    def get_attestations_for(self, agent_id: str) -> list[dict]: ...

    # --- Org Definitions ---

    def store_org_definition(self, org_id: str, data: dict) -> None: ...

    def get_org_definition(self, org_id: str) -> dict | None: ...

    # --- Health ---

    def health_check(self) -> bool: ...


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty(value: str, name: str) -> None:
    """Raise ValueError if *value* is empty or blank."""
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _parse_timestamp(raw: str | datetime | None) -> datetime | None:
    """Parse an ISO-8601 string into a timezone-aware datetime.

    Returns ``None`` when *raw* is ``None``.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to parse timestamp %r: %s", raw, exc)
        return None
    # Attach UTC if the string was naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _matches_filters(
    data: dict,
    *,
    agent_id: str | None,
    action: str | None,
    since: datetime | None,
    until: datetime | None,
    verification_level: str | None,
) -> bool:
    """Return True if *data* satisfies every supplied filter."""
    if agent_id is not None and data.get("agent_id") != agent_id:
        return False
    if action is not None and data.get("action") != action:
        return False
    if verification_level is not None and data.get("verification_level") != verification_level:
        return False

    if since is not None or until is not None:
        ts = _parse_timestamp(data.get("timestamp"))
        if ts is None:
            return False
        if since is not None and ts < since:
            return False
        if until is not None and ts > until:
            return False

    return True


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class MemoryStore:
    """In-memory implementation of TrustStore (for development/testing).

    Data is stored in plain dicts and lost when the process exits.
    """

    def __init__(self) -> None:
        self._envelopes: dict[str, dict] = {}
        self._anchors: dict[str, dict] = {}
        self._posture: dict[str, list[dict]] = {}  # agent_id -> [changes]
        self._revocations: list[dict] = []
        self._genesis: dict[str, dict] = {}
        self._delegations: dict[str, dict] = {}
        self._attestations: dict[str, dict] = {}
        self._org_definitions: dict[str, dict] = {}

    # --- Envelopes ---

    def store_envelope(self, envelope_id: str, data: dict) -> None:
        _require_non_empty(envelope_id, "envelope_id")
        self._envelopes[envelope_id] = data

    def get_envelope(self, envelope_id: str) -> dict | None:
        return self._envelopes.get(envelope_id)

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]:
        envelopes = list(self._envelopes.values())
        if agent_id is not None:
            envelopes = [e for e in envelopes if e.get("agent_id") == agent_id]
        return envelopes

    # --- Audit Anchors ---

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None:
        _require_non_empty(anchor_id, "anchor_id")
        self._anchors[anchor_id] = data

    def get_audit_anchor(self, anchor_id: str) -> dict | None:
        return self._anchors.get(anchor_id)

    def query_anchors(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        verification_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        results: list[dict] = []
        for anchor in self._anchors.values():
            if _matches_filters(
                anchor,
                agent_id=agent_id,
                action=action,
                since=since,
                until=until,
                verification_level=verification_level,
            ):
                results.append(anchor)
                if len(results) >= limit:
                    break
        return results

    # --- Posture Changes ---

    def store_posture_change(self, agent_id: str, data: dict) -> None:
        _require_non_empty(agent_id, "agent_id")
        self._posture.setdefault(agent_id, []).append(data)

    def get_posture_history(self, agent_id: str) -> list[dict]:
        return list(self._posture.get(agent_id, []))

    # --- Revocations ---

    def store_revocation(self, revocation_id: str, data: dict) -> None:
        _require_non_empty(revocation_id, "revocation_id")
        self._revocations.append(data)

    def get_revocations(self, agent_id: str | None = None) -> list[dict]:
        if agent_id is None:
            return list(self._revocations)
        return [r for r in self._revocations if r.get("agent_id") == agent_id]

    # --- Genesis Records ---

    def store_genesis(self, authority_id: str, data: dict) -> None:
        _require_non_empty(authority_id, "authority_id")
        if authority_id in self._genesis:
            from pact_platform.trust.store.sqlite_store import GenesisAlreadyExistsError

            raise GenesisAlreadyExistsError(authority_id)
        self._genesis[authority_id] = data

    def get_genesis(self, authority_id: str) -> dict | None:
        return self._genesis.get(authority_id)

    # --- Delegation Records ---

    def store_delegation(self, delegation_id: str, data: dict) -> None:
        _require_non_empty(delegation_id, "delegation_id")
        self._delegations[delegation_id] = data

    def get_delegation(self, delegation_id: str) -> dict | None:
        return self._delegations.get(delegation_id)

    def get_delegations_for(self, agent_id: str) -> list[dict]:
        return [
            d
            for d in self._delegations.values()
            if d.get("delegator_id") == agent_id or d.get("delegatee_id") == agent_id
        ]

    # --- Attestations ---

    def store_attestation(self, attestation_id: str, data: dict) -> None:
        _require_non_empty(attestation_id, "attestation_id")
        self._attestations[attestation_id] = data

    def get_attestation(self, attestation_id: str) -> dict | None:
        return self._attestations.get(attestation_id)

    def get_attestations_for(self, agent_id: str) -> list[dict]:
        return [a for a in self._attestations.values() if a.get("agent_id") == agent_id]

    # --- Org Definitions ---

    def store_org_definition(self, org_id: str, data: dict) -> None:
        _require_non_empty(org_id, "org_id")
        self._org_definitions[org_id] = data

    def get_org_definition(self, org_id: str) -> dict | None:
        return self._org_definitions.get(org_id)

    # --- Health ---

    def health_check(self) -> bool:
        """In-memory store is always healthy."""
        return True


# ---------------------------------------------------------------------------
# FilesystemStore
# ---------------------------------------------------------------------------


class FilesystemStore:
    """JSON file-based implementation of TrustStore.

    Creates subdirectories for each object type:
    ``envelopes/``, ``anchors/``, ``posture/``, ``revocations/``,
    ``genesis/``, ``delegations/``, ``attestations/``

    Each envelope/anchor is stored as ``<id>.json``. Posture history is
    stored as ``<agent_id>.json`` (a JSON array). Revocations are stored
    as ``<revocation_id>.json``. Genesis, delegation, and attestation
    records are stored as ``<id>.json`` in their respective directories.
    """

    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)
        self._envelopes_dir = self._base / "envelopes"
        self._anchors_dir = self._base / "anchors"
        self._posture_dir = self._base / "posture"
        self._revocations_dir = self._base / "revocations"
        self._genesis_dir = self._base / "genesis"
        self._delegations_dir = self._base / "delegations"
        self._attestations_dir = self._base / "attestations"
        self._org_definitions_dir = self._base / "org_definitions"

        for d in (
            self._envelopes_dir,
            self._anchors_dir,
            self._posture_dir,
            self._revocations_dir,
            self._genesis_dir,
            self._delegations_dir,
            self._attestations_dir,
            self._org_definitions_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    # --- internal helpers ---

    def _safe_path(self, directory: Path, name: str) -> Path:
        """Resolve and validate that the path stays within the target directory.

        Prevents path traversal attacks by ensuring the resolved path is a
        child of the expected directory.

        Args:
            directory: The expected parent directory.
            name: The user-supplied name (e.g., envelope_id, anchor_id).

        Returns:
            The resolved, validated Path.

        Raises:
            ValueError: If the resulting path escapes the target directory.
        """
        target = (directory / name).resolve()
        directory_resolved = directory.resolve()
        if (
            not str(target).startswith(str(directory_resolved) + "/")
            and target != directory_resolved
        ):
            raise ValueError("Path traversal detected")
        return target

    @staticmethod
    def _write_json(path: Path, data: dict | list) -> None:
        path.write_text(json.dumps(data, default=str, indent=2))

    @staticmethod
    def _read_json(path: Path) -> dict | list | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", path, exc)
            return None

    def _all_json_in(self, directory: Path) -> list[dict]:
        """Load all .json files in *directory* as dicts."""
        results: list[dict] = []
        if not directory.exists():
            return results
        for f in sorted(directory.glob("*.json")):
            data = self._read_json(f)
            if isinstance(data, dict):
                results.append(data)
        return results

    # --- Envelopes ---

    def store_envelope(self, envelope_id: str, data: dict) -> None:
        _require_non_empty(envelope_id, "envelope_id")
        path = self._safe_path(self._envelopes_dir, f"{envelope_id}.json")
        self._write_json(path, data)

    def get_envelope(self, envelope_id: str) -> dict | None:
        path = self._safe_path(self._envelopes_dir, f"{envelope_id}.json")
        result = self._read_json(path)
        return result if isinstance(result, dict) else None

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]:
        envelopes = self._all_json_in(self._envelopes_dir)
        if agent_id is not None:
            envelopes = [e for e in envelopes if e.get("agent_id") == agent_id]
        return envelopes

    # --- Audit Anchors ---

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None:
        _require_non_empty(anchor_id, "anchor_id")
        path = self._safe_path(self._anchors_dir, f"{anchor_id}.json")
        self._write_json(path, data)

    def get_audit_anchor(self, anchor_id: str) -> dict | None:
        path = self._safe_path(self._anchors_dir, f"{anchor_id}.json")
        result = self._read_json(path)
        return result if isinstance(result, dict) else None

    def query_anchors(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        verification_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        results: list[dict] = []
        for anchor in self._all_json_in(self._anchors_dir):
            if _matches_filters(
                anchor,
                agent_id=agent_id,
                action=action,
                since=since,
                until=until,
                verification_level=verification_level,
            ):
                results.append(anchor)
                if len(results) >= limit:
                    break
        return results

    # --- Posture Changes ---

    def store_posture_change(self, agent_id: str, data: dict) -> None:
        _require_non_empty(agent_id, "agent_id")
        path = self._safe_path(self._posture_dir, f"{agent_id}.json")
        existing = self._read_json(path)
        if isinstance(existing, list):
            existing.append(data)
        else:
            existing = [data]
        self._write_json(path, existing)

    def get_posture_history(self, agent_id: str) -> list[dict]:
        path = self._safe_path(self._posture_dir, f"{agent_id}.json")
        result = self._read_json(path)
        if isinstance(result, list):
            return result
        return []

    # --- Revocations ---

    def store_revocation(self, revocation_id: str, data: dict) -> None:
        _require_non_empty(revocation_id, "revocation_id")
        path = self._safe_path(self._revocations_dir, f"{revocation_id}.json")
        self._write_json(path, data)

    def get_revocations(self, agent_id: str | None = None) -> list[dict]:
        all_revocations = self._all_json_in(self._revocations_dir)
        if agent_id is not None:
            return [r for r in all_revocations if r.get("agent_id") == agent_id]
        return all_revocations

    # --- Genesis Records ---

    def store_genesis(self, authority_id: str, data: dict) -> None:
        _require_non_empty(authority_id, "authority_id")
        path = self._safe_path(self._genesis_dir, f"{authority_id}.json")
        if path.exists():
            from pact_platform.trust.store.sqlite_store import GenesisAlreadyExistsError

            raise GenesisAlreadyExistsError(authority_id)
        self._write_json(path, data)

    def get_genesis(self, authority_id: str) -> dict | None:
        path = self._safe_path(self._genesis_dir, f"{authority_id}.json")
        result = self._read_json(path)
        return result if isinstance(result, dict) else None

    # --- Delegation Records ---

    def store_delegation(self, delegation_id: str, data: dict) -> None:
        _require_non_empty(delegation_id, "delegation_id")
        path = self._safe_path(self._delegations_dir, f"{delegation_id}.json")
        self._write_json(path, data)

    def get_delegation(self, delegation_id: str) -> dict | None:
        path = self._safe_path(self._delegations_dir, f"{delegation_id}.json")
        result = self._read_json(path)
        return result if isinstance(result, dict) else None

    def get_delegations_for(self, agent_id: str) -> list[dict]:
        all_delegations = self._all_json_in(self._delegations_dir)
        return [
            d
            for d in all_delegations
            if d.get("delegator_id") == agent_id or d.get("delegatee_id") == agent_id
        ]

    # --- Attestations ---

    def store_attestation(self, attestation_id: str, data: dict) -> None:
        _require_non_empty(attestation_id, "attestation_id")
        path = self._safe_path(self._attestations_dir, f"{attestation_id}.json")
        self._write_json(path, data)

    def get_attestation(self, attestation_id: str) -> dict | None:
        path = self._safe_path(self._attestations_dir, f"{attestation_id}.json")
        result = self._read_json(path)
        return result if isinstance(result, dict) else None

    def get_attestations_for(self, agent_id: str) -> list[dict]:
        all_attestations = self._all_json_in(self._attestations_dir)
        return [a for a in all_attestations if a.get("agent_id") == agent_id]

    # --- Org Definitions ---

    def store_org_definition(self, org_id: str, data: dict) -> None:
        _require_non_empty(org_id, "org_id")
        path = self._safe_path(self._org_definitions_dir, f"{org_id}.json")
        self._write_json(path, data)

    def get_org_definition(self, org_id: str) -> dict | None:
        path = self._safe_path(self._org_definitions_dir, f"{org_id}.json")
        result = self._read_json(path)
        return result if isinstance(result, dict) else None

    # --- Health ---

    def health_check(self) -> bool:
        """Check if the filesystem store is accessible.

        Verifies the base directory exists and is accessible.
        """
        try:
            return self._base.exists() and self._base.is_dir()
        except OSError:
            return False
