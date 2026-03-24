# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Workspace discovery — scan directories and identify workspace boundaries.

Given a root directory (e.g. ~/repos/terrene/terrene/), discovers workspace
structures by looking for:
1. Explicit workspace.yaml manifests
2. COC-pattern directories (briefs/, 01-analysis/, 02-plans/, todos/)
3. General workspace indicators (README.md, docs/, src/)

Returns WorkspaceConfig objects for each discovered workspace, ready to be
registered with a WorkspaceRegistry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from pact_platform.build.config.schema import WorkspaceConfig

logger = logging.getLogger(__name__)


# COC workspace indicators — if a directory contains these, it's likely a workspace
_COC_INDICATORS = {"briefs", "todos", "01-analysis", "02-plans"}
# Minimum COC indicators to auto-detect as a workspace
_COC_MIN_INDICATORS = 2

# Directories to always skip during discovery
_SKIP_DIRS = {
    ".git",
    ".claude",
    ".obsidian",
    ".idea",
    ".jbeval",
    "__pycache__",
    "node_modules",
    ".venv",
}


class DiscoveredWorkspace(BaseModel):
    """A workspace discovered from disk scan."""

    config: WorkspaceConfig
    discovery_method: str = ""  # "manifest", "coc_pattern", "explicit"
    indicators_found: list[str] = Field(default_factory=list)


class WorkspaceManifest(BaseModel):
    """Schema for workspace.yaml manifest files."""

    id: str
    description: str = ""
    knowledge_base_paths: list[str] = Field(
        default_factory=lambda: ["briefs/", "01-analysis/", "02-plans/"],
    )
    team_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceDiscovery:
    """Discovers workspace structures from a directory tree.

    Scans a root directory and identifies workspace boundaries using
    explicit manifests (workspace.yaml) or pattern detection (COC structure).

    Usage:
        discovery = WorkspaceDiscovery()
        workspaces = discovery.discover("/path/to/foundation")
    """

    def __init__(
        self,
        *,
        scan_depth: int = 2,
        require_manifest: bool = False,
    ) -> None:
        """Initialize workspace discovery.

        Args:
            scan_depth: Maximum directory depth to scan for workspaces.
            require_manifest: If True, only discover workspaces with explicit
                workspace.yaml manifests (skip auto-detection).
        """
        self._scan_depth = scan_depth
        self._require_manifest = require_manifest

    def discover(self, root_path: str | Path) -> list[DiscoveredWorkspace]:
        """Discover all workspaces under a root directory.

        Scans subdirectories for workspace indicators. Each discovered
        workspace gets a WorkspaceConfig suitable for registration.

        Args:
            root_path: Root directory to scan.

        Returns:
            List of discovered workspaces, sorted by path.
        """
        root = Path(root_path).resolve()
        if not root.is_dir():
            raise ValueError(f"Root path is not a directory: {root}")

        discovered: list[DiscoveredWorkspace] = []
        self._scan_directory(root, discovered, depth=0)

        # Sort by path for deterministic output
        discovered.sort(key=lambda w: w.config.path)
        logger.info(
            "Discovered %d workspace(s) under %s",
            len(discovered),
            root,
        )
        return discovered

    def discover_single(self, workspace_path: str | Path) -> DiscoveredWorkspace | None:
        """Attempt to discover a single workspace at the given path.

        Args:
            workspace_path: Directory to check for workspace indicators.

        Returns:
            DiscoveredWorkspace if the directory is a workspace, None otherwise.
        """
        path = Path(workspace_path).resolve()
        if not path.is_dir():
            return None

        return self._check_directory(path)

    def _scan_directory(
        self,
        directory: Path,
        results: list[DiscoveredWorkspace],
        depth: int,
    ) -> None:
        """Recursively scan a directory for workspaces."""
        if depth > self._scan_depth:
            return

        # Check this directory first
        workspace = self._check_directory(directory)
        if workspace is not None:
            results.append(workspace)
            # Don't recurse into discovered workspaces (they're atomic units)
            return

        # Recurse into subdirectories
        try:
            for child in sorted(directory.iterdir()):
                if child.is_dir() and child.name not in _SKIP_DIRS:
                    self._scan_directory(child, results, depth + 1)
        except PermissionError:
            logger.warning("Permission denied scanning: %s", directory)

    def _check_directory(self, directory: Path) -> DiscoveredWorkspace | None:
        """Check if a directory is a workspace."""
        # Method 1: Explicit manifest
        manifest_path = directory / "workspace.yaml"
        if manifest_path.is_file():
            return self._from_manifest(directory, manifest_path)

        # Method 1b: Also check .yml extension
        manifest_path_yml = directory / "workspace.yml"
        if manifest_path_yml.is_file():
            return self._from_manifest(directory, manifest_path_yml)

        # Method 2: COC pattern detection (skip if require_manifest is True)
        if not self._require_manifest:
            return self._from_coc_pattern(directory)

        return None

    def _from_manifest(
        self,
        directory: Path,
        manifest_path: Path,
    ) -> DiscoveredWorkspace | None:
        """Create workspace from explicit manifest file."""
        try:
            with manifest_path.open() as f:
                raw = yaml.safe_load(f)

            if not isinstance(raw, dict):
                logger.warning("Invalid workspace manifest (not a dict): %s", manifest_path)
                return None

            manifest = WorkspaceManifest(**raw)
            config = WorkspaceConfig(
                id=manifest.id,
                path=str(directory),
                description=manifest.description,
                knowledge_base_paths=manifest.knowledge_base_paths,
            )
            return DiscoveredWorkspace(
                config=config,
                discovery_method="manifest",
                indicators_found=[str(manifest_path.name)],
            )
        except Exception as exc:
            logger.warning(
                "Failed to parse workspace manifest %s: %s",
                manifest_path,
                exc,
            )
            return None

    def _from_coc_pattern(self, directory: Path) -> DiscoveredWorkspace | None:
        """Detect workspace from COC directory pattern."""
        indicators_found: list[str] = []

        try:
            children = {child.name for child in directory.iterdir() if child.is_dir()}
        except PermissionError:
            return None

        for indicator in _COC_INDICATORS:
            if indicator in children:
                indicators_found.append(indicator)

        if len(indicators_found) < _COC_MIN_INDICATORS:
            return None

        # Auto-generate workspace ID from directory name
        workspace_id = directory.name

        # Build knowledge_base_paths from what actually exists
        knowledge_base_paths: list[str] = []
        for default_path in ["briefs/", "01-analysis/", "02-plans/"]:
            dir_name = default_path.rstrip("/")
            if dir_name in children:
                knowledge_base_paths.append(default_path)

        config = WorkspaceConfig(
            id=workspace_id,
            path=str(directory),
            description=f"Auto-discovered workspace: {directory.name}",
            knowledge_base_paths=knowledge_base_paths or ["briefs/", "01-analysis/", "02-plans/"],
        )
        return DiscoveredWorkspace(
            config=config,
            discovery_method="coc_pattern",
            indicators_found=indicators_found,
        )
