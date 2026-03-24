# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""RT-19: FilesystemStore path traversal protection tests.

Tests that:
1. Normal IDs work correctly (no false positives)
2. Relative path traversal (../) in IDs raises ValueError
3. Absolute paths in IDs raise ValueError
4. Protection applies to all store/get methods
"""

import pytest

from pact_platform.trust.store.store import FilesystemStore


class TestPathTraversalProtection:
    """Verify that FilesystemStore prevents path traversal attacks."""

    def test_normal_id_works(self, tmp_path):
        """A normal alphanumeric ID should work without error."""
        store = FilesystemStore(base_path=tmp_path)
        store.store_envelope("env-123", {"envelope_id": "env-123"})
        result = store.get_envelope("env-123")
        assert result is not None
        assert result["envelope_id"] == "env-123"

    def test_relative_traversal_in_envelope_store_raises(self, tmp_path):
        """Using ../ in envelope_id should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.store_envelope("../../etc/passwd", {"data": "evil"})

    def test_relative_traversal_in_envelope_get_raises(self, tmp_path):
        """Using ../ in envelope_id for get should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.get_envelope("../../../etc/shadow")

    def test_absolute_path_in_envelope_store_raises(self, tmp_path):
        """Using an absolute path as envelope_id should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.store_envelope("/etc/passwd", {"data": "evil"})

    def test_relative_traversal_in_anchor_store_raises(self, tmp_path):
        """Using ../ in anchor_id should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.store_audit_anchor("../../etc/passwd", {"data": "evil"})

    def test_relative_traversal_in_anchor_get_raises(self, tmp_path):
        """Using ../ in anchor_id for get should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.get_audit_anchor("../../../etc/shadow")

    def test_relative_traversal_in_posture_store_raises(self, tmp_path):
        """Using ../ in agent_id for posture store should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.store_posture_change("../../etc/passwd", {"data": "evil"})

    def test_relative_traversal_in_posture_get_raises(self, tmp_path):
        """Using ../ in agent_id for posture get should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.get_posture_history("../../../etc/shadow")

    def test_relative_traversal_in_revocation_store_raises(self, tmp_path):
        """Using ../ in revocation_id should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.store_revocation("../../etc/passwd", {"data": "evil"})

    def test_absolute_path_in_anchor_store_raises(self, tmp_path):
        """Using an absolute path as anchor_id should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.store_audit_anchor("/tmp/evil", {"data": "evil"})

    def test_absolute_path_in_revocation_store_raises(self, tmp_path):
        """Using an absolute path as revocation_id should raise ValueError."""
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            store.store_revocation("/tmp/evil", {"data": "evil"})

    def test_normal_anchor_id_works(self, tmp_path):
        """A normal anchor ID should work correctly."""
        store = FilesystemStore(base_path=tmp_path)
        store.store_audit_anchor("anc-456", {"anchor_id": "anc-456"})
        result = store.get_audit_anchor("anc-456")
        assert result is not None
        assert result["anchor_id"] == "anc-456"

    def test_normal_posture_agent_id_works(self, tmp_path):
        """A normal agent_id for posture should work correctly."""
        store = FilesystemStore(base_path=tmp_path)
        store.store_posture_change("agent-1", {"direction": "upgrade"})
        result = store.get_posture_history("agent-1")
        assert len(result) == 1

    def test_normal_revocation_id_works(self, tmp_path):
        """A normal revocation_id should work correctly."""
        store = FilesystemStore(base_path=tmp_path)
        store.store_revocation("rev-789", {"agent_id": "agent-1"})
        results = store.get_revocations()
        assert len(results) == 1
