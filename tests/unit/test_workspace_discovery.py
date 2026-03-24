# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for workspace discovery — scan directories and identify workspace boundaries.

Tests verify that WorkspaceDiscovery correctly discovers workspaces via:
1. Explicit workspace.yaml manifests
2. COC-pattern directory detection (briefs/, todos/, 01-analysis/, 02-plans/)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pact_platform.build.workspace.discovery import (
    WorkspaceDiscovery,
    WorkspaceManifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_coc_workspace(base: Path, name: str, indicators: list[str]) -> Path:
    """Create a directory with COC indicator subdirectories."""
    ws = base / name
    ws.mkdir(parents=True, exist_ok=True)
    for ind in indicators:
        (ws / ind).mkdir(exist_ok=True)
    return ws


def _create_manifest_workspace(base: Path, name: str, manifest_content: str) -> Path:
    """Create a directory with a workspace.yaml manifest."""
    ws = base / name
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "workspace.yaml").write_text(manifest_content)
    return ws


# ---------------------------------------------------------------------------
# WorkspaceManifest model
# ---------------------------------------------------------------------------


class TestWorkspaceManifest:
    """Tests for the WorkspaceManifest Pydantic model."""

    def test_minimal_manifest(self):
        m = WorkspaceManifest(id="test-ws")
        assert m.id == "test-ws"
        assert m.description == ""
        assert m.knowledge_base_paths == ["briefs/", "01-analysis/", "02-plans/"]

    def test_full_manifest(self):
        m = WorkspaceManifest(
            id="pact",
            description="The PACT workspace",
            knowledge_base_paths=["briefs/", "docs/"],
            team_id="platform-team",
            metadata={"priority": "high"},
        )
        assert m.team_id == "platform-team"
        assert m.metadata["priority"] == "high"


# ---------------------------------------------------------------------------
# COC pattern discovery
# ---------------------------------------------------------------------------


class TestCOCPatternDiscovery:
    """Tests for auto-detecting workspaces via COC directory patterns."""

    def test_discovers_with_two_indicators(self, tmp_path: Path):
        _create_coc_workspace(tmp_path, "my-project", ["briefs", "todos"])
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 1
        assert results[0].discovery_method == "coc_pattern"
        assert results[0].config.id == "my-project"

    def test_discovers_with_all_four_indicators(self, tmp_path: Path):
        _create_coc_workspace(tmp_path, "full-coc", ["briefs", "todos", "01-analysis", "02-plans"])
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 1
        assert set(results[0].indicators_found) == {"briefs", "todos", "01-analysis", "02-plans"}

    def test_ignores_single_indicator(self, tmp_path: Path):
        """One indicator is not enough to detect a workspace."""
        _create_coc_workspace(tmp_path, "not-a-workspace", ["briefs"])
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 0

    def test_knowledge_base_paths_from_existing_dirs(self, tmp_path: Path):
        _create_coc_workspace(tmp_path, "ws", ["briefs", "01-analysis", "todos"])
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 1
        # "briefs/" and "01-analysis/" exist, "02-plans/" does not
        assert "briefs/" in results[0].config.knowledge_base_paths
        assert "01-analysis/" in results[0].config.knowledge_base_paths


# ---------------------------------------------------------------------------
# Manifest-based discovery
# ---------------------------------------------------------------------------


class TestManifestDiscovery:
    """Tests for discovering workspaces via workspace.yaml manifests."""

    def test_discovers_yaml_manifest(self, tmp_path: Path):
        _create_manifest_workspace(
            tmp_path,
            "my-project",
            "id: my-project\ndescription: Test workspace\n",
        )
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 1
        assert results[0].discovery_method == "manifest"
        assert results[0].config.id == "my-project"
        assert results[0].config.description == "Test workspace"

    def test_discovers_yml_extension(self, tmp_path: Path):
        ws = tmp_path / "proj"
        ws.mkdir()
        (ws / "workspace.yml").write_text("id: proj\n")
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 1
        assert results[0].config.id == "proj"

    def test_manifest_takes_precedence_over_coc(self, tmp_path: Path):
        """If a directory has both a manifest and COC indicators, manifest wins."""
        ws = tmp_path / "both"
        ws.mkdir()
        (ws / "workspace.yaml").write_text("id: manifest-ws\ndescription: From manifest\n")
        (ws / "briefs").mkdir()
        (ws / "todos").mkdir()
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 1
        assert results[0].discovery_method == "manifest"
        assert results[0].config.id == "manifest-ws"

    def test_invalid_manifest_skipped(self, tmp_path: Path):
        ws = tmp_path / "bad"
        ws.mkdir()
        (ws / "workspace.yaml").write_text("not: valid: yaml: [[[")
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        # Invalid manifest is skipped (no coc indicators either)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Scan depth and recursion
# ---------------------------------------------------------------------------


class TestScanDepth:
    """Tests for scan depth and recursive discovery."""

    def test_depth_zero_only_checks_root(self, tmp_path: Path):
        _create_coc_workspace(tmp_path / "nested", "project", ["briefs", "todos"])
        discovery = WorkspaceDiscovery(scan_depth=0)
        results = discovery.discover(tmp_path)
        # Root has no indicators, and scan_depth=0 doesn't recurse beyond immediate children
        # Nested is at depth 1 (tmp_path/nested), project at depth 2 — beyond scan_depth=0
        assert len(results) == 0

    def test_does_not_recurse_into_discovered_workspace(self, tmp_path: Path):
        """If a directory is a workspace, its children are not scanned."""
        ws = tmp_path / "parent-ws"
        ws.mkdir()
        (ws / "briefs").mkdir()
        (ws / "todos").mkdir()
        # Add a nested workspace inside
        nested = ws / "child"
        nested.mkdir()
        (nested / "briefs").mkdir()
        (nested / "todos").mkdir()
        discovery = WorkspaceDiscovery(scan_depth=3)
        results = discovery.discover(tmp_path)
        # Only the parent workspace should be discovered
        assert len(results) == 1
        assert results[0].config.id == "parent-ws"

    def test_skips_dotdirs(self, tmp_path: Path):
        """Directories like .git, .claude are skipped."""
        _create_coc_workspace(tmp_path, ".git", ["briefs", "todos"])
        _create_coc_workspace(tmp_path, "real-project", ["briefs", "todos"])
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 1
        assert results[0].config.id == "real-project"

    def test_multiple_workspaces(self, tmp_path: Path):
        _create_coc_workspace(tmp_path, "alpha", ["briefs", "todos"])
        _create_coc_workspace(tmp_path, "beta", ["briefs", "01-analysis"])
        _create_manifest_workspace(tmp_path, "gamma", "id: gamma\n")
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        assert len(results) == 3
        ids = {r.config.id for r in results}
        assert ids == {"alpha", "beta", "gamma"}


# ---------------------------------------------------------------------------
# require_manifest mode
# ---------------------------------------------------------------------------


class TestRequireManifest:
    """When require_manifest=True, only manifest-based workspaces are found."""

    def test_coc_pattern_ignored(self, tmp_path: Path):
        _create_coc_workspace(tmp_path, "coc-only", ["briefs", "todos"])
        discovery = WorkspaceDiscovery(scan_depth=1, require_manifest=True)
        results = discovery.discover(tmp_path)
        assert len(results) == 0

    def test_manifest_still_found(self, tmp_path: Path):
        _create_manifest_workspace(tmp_path, "manifest-proj", "id: manifest-proj\n")
        discovery = WorkspaceDiscovery(scan_depth=1, require_manifest=True)
        results = discovery.discover(tmp_path)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# discover_single
# ---------------------------------------------------------------------------


class TestDiscoverSingle:
    """Tests for discover_single (check one directory)."""

    def test_single_coc(self, tmp_path: Path):
        ws = _create_coc_workspace(tmp_path, "single", ["briefs", "todos"])
        discovery = WorkspaceDiscovery()
        result = discovery.discover_single(ws)
        assert result is not None
        assert result.config.id == "single"

    def test_single_not_workspace(self, tmp_path: Path):
        ws = tmp_path / "empty"
        ws.mkdir()
        discovery = WorkspaceDiscovery()
        result = discovery.discover_single(ws)
        assert result is None

    def test_single_nonexistent_directory(self, tmp_path: Path):
        discovery = WorkspaceDiscovery()
        result = discovery.discover_single(tmp_path / "does-not-exist")
        assert result is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Edge cases and error handling."""

    def test_invalid_root_raises(self, tmp_path: Path):
        discovery = WorkspaceDiscovery()
        with pytest.raises(ValueError, match="not a directory"):
            discovery.discover(tmp_path / "nonexistent")

    def test_sorted_output(self, tmp_path: Path):
        """Results are sorted by path for deterministic output."""
        _create_coc_workspace(tmp_path, "zzz", ["briefs", "todos"])
        _create_coc_workspace(tmp_path, "aaa", ["briefs", "todos"])
        discovery = WorkspaceDiscovery(scan_depth=1)
        results = discovery.discover(tmp_path)
        paths = [r.config.path for r in results]
        assert paths == sorted(paths)
