# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Persistence layer — storage abstraction, versioning, audit queries, and posture history.

This package provides:
- :class:`TrustStore` protocol and implementations (MemoryStore, FilesystemStore,
  SQLiteTrustStore, PostgreSQLTrustStore)
- :class:`VersionTracker` for constraint envelope version history
- :class:`AuditQuery` / :class:`AuditReport` for audit anchor queries
- :class:`PostureHistoryStore` / :class:`PostureEligibilityChecker` for posture lifecycle
- Schema migration framework (``migrate``, ``current_version``)
- Backup and restore (``backup_store``, ``restore_store``)
"""

from care_platform.persistence.audit_query import AuditQuery, AuditReport
from care_platform.persistence.backup import (
    BackupError,
    RestoreError,
    backup_store,
    restore_store,
)
from care_platform.persistence.health import StoreHealthStatus, TrustStoreHealthCheck
from care_platform.persistence.migrations import (
    Migration,
    MigrationError,
    current_version,
    migrate,
)
from care_platform.persistence.posture_history import (
    EligibilityResult,
    PostureChangeRecord,
    PostureChangeTrigger,
    PostureEligibilityChecker,
    PostureHistoryError,
    PostureHistoryStore,
)
from care_platform.persistence.sqlite_store import SQLiteTrustStore
from care_platform.persistence.store import FilesystemStore, MemoryStore, TrustStore
from care_platform.persistence.versioning import (
    EnvelopeDiff,
    EnvelopeVersion,
    VersionTracker,
)

# PostgreSQL store is optional — only available when psycopg2 is installed
try:
    from care_platform.persistence.postgresql_store import PostgreSQLTrustStore
except ImportError:
    pass

__all__ = [
    # Store protocol + implementations
    "TrustStore",
    "MemoryStore",
    "FilesystemStore",
    "SQLiteTrustStore",
    "PostgreSQLTrustStore",
    # Health
    "StoreHealthStatus",
    "TrustStoreHealthCheck",
    # Versioning
    "VersionTracker",
    "EnvelopeVersion",
    "EnvelopeDiff",
    # Audit queries
    "AuditQuery",
    "AuditReport",
    # Posture history
    "PostureHistoryStore",
    "PostureChangeRecord",
    "PostureChangeTrigger",
    "PostureEligibilityChecker",
    "PostureHistoryError",
    "EligibilityResult",
    # Migrations
    "Migration",
    "MigrationError",
    "migrate",
    "current_version",
    # Backup / Restore
    "BackupError",
    "RestoreError",
    "backup_store",
    "restore_store",
]
