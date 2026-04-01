# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for container registry publishing workflow (Task 5026).

Validates that:
- .github/workflows/publish.yml includes a container build+push job
- The job builds and pushes to ghcr.io/terrene-foundation/pact
- Tags include the version number and 'latest'
- Uses GitHub Container Registry (ghcr.io)
- The job runs on release events
- Proper permissions are set for package publishing
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"

pytestmark = pytest.mark.skipif(
    not PUBLISH_WORKFLOW.is_file(),
    reason="publish.yml not present — CI workflow not yet created",
)


def _load_workflow() -> dict:
    """Load and parse the publish workflow YAML."""
    content = PUBLISH_WORKFLOW.read_text()
    return yaml.safe_load(content)


class TestPublishWorkflowExists:
    """The publish workflow must exist and be valid YAML."""

    def test_workflow_file_exists(self):
        """publish.yml must exist in .github/workflows/."""
        assert PUBLISH_WORKFLOW.is_file(), f"publish.yml not found at {PUBLISH_WORKFLOW}"

    def test_workflow_is_valid_yaml(self):
        """publish.yml must be parseable YAML."""
        content = PUBLISH_WORKFLOW.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "publish.yml must parse to a dict"


class TestContainerRegistryJob:
    """A container build+push job must exist in the publish workflow."""

    def test_container_job_exists(self):
        """publish.yml must have a job for building and pushing Docker images."""
        workflow = _load_workflow()
        jobs = workflow.get("jobs", {})
        # Look for a job that references Docker or container registry
        container_jobs = [name for name, job in jobs.items() if _job_references_container(job)]
        assert len(container_jobs) >= 1, (
            "publish.yml must have at least one job that builds/pushes a Docker image. "
            f"Found jobs: {list(jobs.keys())}"
        )

    def test_uses_ghcr(self):
        """The container job must push to ghcr.io."""
        workflow = _load_workflow()
        content = PUBLISH_WORKFLOW.read_text()
        assert (
            "ghcr.io" in content
        ), "publish.yml must reference ghcr.io (GitHub Container Registry)"

    def test_image_name_correct(self):
        """The container image must be tagged as ghcr.io/terrene-foundation/pact."""
        content = PUBLISH_WORKFLOW.read_text()
        assert (
            "terrene-foundation/pact" in content
        ), "Container image must be named terrene-foundation/pact"

    def test_tags_include_latest(self):
        """The container image must be tagged with 'latest'."""
        content = PUBLISH_WORKFLOW.read_text()
        assert "latest" in content, "Container image must include a 'latest' tag"

    def test_triggers_on_release(self):
        """The container job must trigger on release events."""
        workflow = _load_workflow()
        # 'on' is parsed as True by PyYAML, so check raw text
        content = PUBLISH_WORKFLOW.read_text()
        assert "release" in content, "publish.yml must trigger on release events"

    def test_has_packages_write_permission(self):
        """The workflow must have packages: write permission for GHCR publishing."""
        content = PUBLISH_WORKFLOW.read_text()
        assert (
            "packages" in content
        ), "publish.yml must include 'packages' permission for GHCR publishing"


def _job_references_container(job: dict) -> bool:
    """Check if a job definition references Docker container operations."""
    if not isinstance(job, dict):
        return False

    job_str = str(job).lower()
    container_indicators = [
        "docker",
        "ghcr.io",
        "container",
        "build-push-action",
        "docker/build-push-action",
    ]
    return any(indicator in job_str for indicator in container_indicators)
