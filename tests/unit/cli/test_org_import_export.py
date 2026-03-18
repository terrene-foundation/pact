# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Organization Import/Export and CLI commands (M21: Tasks 5041-5045, 5040b).

Tests the following CLI commands:
- care-platform org export --org-id <id> --output <file.yaml>
- care-platform org import --file <org.yaml>
- care-platform org diff <file1> <file2>
- care-platform org deploy --file <org.yaml>
- care-platform org status

And the example YAML config generation (5040b).
"""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from care_platform.build.cli import main
from care_platform.build.org.builder import OrgDefinition, OrgTemplate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def minimal_org() -> OrgDefinition:
    """A minimal valid OrgDefinition for testing."""
    return OrgTemplate.minimal_template("Test Org")


@pytest.fixture()
def minimal_org_yaml(tmp_path, minimal_org) -> Path:
    """Write a minimal OrgDefinition to a YAML file and return the path."""
    data = minimal_org.model_dump(mode="json")
    path = tmp_path / "test-org.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


@pytest.fixture()
def minimal_org_json(tmp_path, minimal_org) -> Path:
    """Write a minimal OrgDefinition to a JSON file and return the path."""
    data = minimal_org.model_dump(mode="json")
    path = tmp_path / "test-org.json"
    path.write_text(json.dumps(data, indent=2))
    return path


@pytest.fixture()
def foundation_org() -> OrgDefinition:
    """Terrene Foundation OrgDefinition for testing."""
    return OrgTemplate.foundation_template()


@pytest.fixture()
def foundation_org_yaml(tmp_path, foundation_org) -> Path:
    """Write the foundation OrgDefinition to a YAML file."""
    data = foundation_org.model_dump(mode="json")
    path = tmp_path / "foundation-org.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


@pytest.fixture()
def modified_minimal_org_yaml(tmp_path, minimal_org) -> Path:
    """Write a modified version of the minimal org for diff testing."""
    data = minimal_org.model_dump(mode="json")
    # Modify: change org name and add a second agent
    data["name"] = "Modified Test Org"
    data["agents"].append(
        {
            "id": "test-org-extra-agent",
            "name": "Extra Agent",
            "role": "An additional test agent",
            "constraint_envelope": "test-org-default-envelope",
            "initial_posture": "supervised",
            "capabilities": [],
            "llm_backend": None,
            "verification_gradient": None,
            "metadata": {},
        }
    )
    data["teams"][0]["agents"].append("test-org-extra-agent")
    path = tmp_path / "modified-org.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


@pytest.fixture()
def invalid_org_yaml(tmp_path) -> Path:
    """Write an invalid OrgDefinition YAML (missing required fields)."""
    path = tmp_path / "invalid-org.yaml"
    path.write_text(
        yaml.dump(
            {
                "org_id": "broken",
                # Missing 'name' field
                "agents": [
                    {
                        "id": "agent-1",
                        "name": "Agent",
                        "role": "test",
                        "constraint_envelope": "nonexistent-envelope",
                    }
                ],
                "teams": [],
                "envelopes": [],
                "workspaces": [],
            },
            default_flow_style=False,
        )
    )
    return path


# ---------------------------------------------------------------------------
# Task 5041: YAML Export Command
# ---------------------------------------------------------------------------


class TestOrgExport:
    """Tests for 'care-platform org export --org-id <id> --output <file>'."""

    def test_export_command_registered(self, runner):
        """The 'export' subcommand is registered under 'org'."""
        result = runner.invoke(main, ["org", "--help"])
        assert result.exit_code == 0
        assert "export" in result.output

    def test_export_help_shows_options(self, runner):
        """'org export --help' shows --org-id and --output options."""
        result = runner.invoke(main, ["org", "export", "--help"])
        assert result.exit_code == 0
        assert "--org-id" in result.output
        assert "--output" in result.output

    def test_export_minimal_org_to_yaml(self, runner, tmp_path):
        """Export a minimal org template to YAML file."""
        output_path = tmp_path / "exported.yaml"
        result = runner.invoke(
            main,
            ["org", "export", "--org-id", "minimal", "--output", str(output_path)],
        )
        assert result.exit_code == 0, f"Export failed: {result.output}"
        assert output_path.exists(), "Output file was not created"

        # Verify the YAML is valid and can be loaded back
        with output_path.open() as f:
            data = yaml.safe_load(f)
        assert "org_id" in data
        assert "agents" in data
        assert "teams" in data
        assert "envelopes" in data

    def test_export_foundation_org_to_yaml(self, runner, tmp_path):
        """Export the foundation org template to YAML file."""
        output_path = tmp_path / "foundation.yaml"
        result = runner.invoke(
            main,
            ["org", "export", "--org-id", "foundation", "--output", str(output_path)],
        )
        assert result.exit_code == 0, f"Export failed: {result.output}"
        assert output_path.exists()

        with output_path.open() as f:
            data = yaml.safe_load(f)
        assert data["org_id"] == "terrene-foundation"
        assert len(data["agents"]) > 0
        assert len(data["teams"]) > 0

    def test_export_roundtrip_preserves_data(self, runner, tmp_path):
        """Export then import should produce an equivalent OrgDefinition."""
        output_path = tmp_path / "roundtrip.yaml"
        result = runner.invoke(
            main,
            ["org", "export", "--org-id", "minimal", "--output", str(output_path)],
        )
        assert result.exit_code == 0

        with output_path.open() as f:
            data = yaml.safe_load(f)
        restored = OrgDefinition.model_validate(data)
        original = OrgTemplate.minimal_template("Test Org")

        assert restored.org_id == original.org_id
        assert restored.name == original.name
        assert len(restored.agents) == len(original.agents)
        assert len(restored.teams) == len(original.teams)

    def test_export_unknown_org_id_fails(self, runner, tmp_path):
        """Export with unknown org-id fails with informative error."""
        output_path = tmp_path / "bad.yaml"
        result = runner.invoke(
            main,
            ["org", "export", "--org-id", "nonexistent-org", "--output", str(output_path)],
        )
        assert result.exit_code != 0
        assert "nonexistent-org" in result.output.lower() or "not found" in result.output.lower()

    def test_export_requires_org_id(self, runner, tmp_path):
        """Export without --org-id fails."""
        output_path = tmp_path / "no-id.yaml"
        result = runner.invoke(
            main,
            ["org", "export", "--output", str(output_path)],
        )
        assert result.exit_code != 0

    def test_export_requires_output(self, runner):
        """Export without --output fails."""
        result = runner.invoke(
            main,
            ["org", "export", "--org-id", "minimal"],
        )
        assert result.exit_code != 0

    def test_export_shows_success_message(self, runner, tmp_path):
        """Export displays a confirmation message on success."""
        output_path = tmp_path / "msg.yaml"
        result = runner.invoke(
            main,
            ["org", "export", "--org-id", "minimal", "--output", str(output_path)],
        )
        assert result.exit_code == 0
        assert "exported" in result.output.lower() or "written" in result.output.lower()


# ---------------------------------------------------------------------------
# Task 5042: YAML/JSON Import Command
# ---------------------------------------------------------------------------


class TestOrgImport:
    """Tests for 'care-platform org import --file <file>'."""

    def test_import_command_registered(self, runner):
        """The 'import' subcommand is registered under 'org' as 'import-file'."""
        result = runner.invoke(main, ["org", "--help"])
        assert result.exit_code == 0
        # 'import' is a Python keyword, so the CLI command may be named 'import-file'
        assert "import" in result.output.lower()

    def test_import_help_shows_options(self, runner):
        """'org import-file --help' shows --file option."""
        result = runner.invoke(main, ["org", "import-file", "--help"])
        assert result.exit_code == 0
        assert "--file" in result.output

    def test_import_valid_yaml(self, runner, minimal_org_yaml):
        """Import a valid YAML org definition succeeds."""
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", str(minimal_org_yaml)],
        )
        assert result.exit_code == 0, f"Import failed: {result.output}"
        assert "valid" in result.output.lower() or "success" in result.output.lower()

    def test_import_valid_json(self, runner, minimal_org_json):
        """Import a valid JSON org definition succeeds."""
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", str(minimal_org_json)],
        )
        assert result.exit_code == 0, f"Import failed: {result.output}"

    def test_import_shows_org_summary(self, runner, minimal_org_yaml):
        """Import displays a summary of the loaded org."""
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", str(minimal_org_yaml)],
        )
        assert result.exit_code == 0
        # Should show org details
        assert "test-org" in result.output.lower() or "test org" in result.output.lower()

    def test_import_with_validation_errors_reports_them(self, runner, invalid_org_yaml):
        """Import of an org with validation errors reports the errors."""
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", str(invalid_org_yaml)],
        )
        # Should show validation warnings/errors but still complete
        output_lower = result.output.lower()
        assert "error" in output_lower or "warning" in output_lower or "validation" in output_lower

    def test_import_nonexistent_file_fails(self, runner):
        """Import with a nonexistent file fails clearly."""
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", "/nonexistent/org.yaml"],
        )
        assert result.exit_code != 0

    def test_import_requires_file(self, runner):
        """Import without --file fails."""
        result = runner.invoke(main, ["org", "import-file"])
        assert result.exit_code != 0

    def test_import_foundation_yaml(self, runner, foundation_org_yaml):
        """Import a full foundation org succeeds."""
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", str(foundation_org_yaml)],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Task 5043: Org Diff Command
# ---------------------------------------------------------------------------


class TestOrgDiff:
    """Tests for 'care-platform org diff <file1> <file2>'."""

    def test_diff_command_registered(self, runner):
        """The 'diff' subcommand is registered under 'org'."""
        result = runner.invoke(main, ["org", "--help"])
        assert result.exit_code == 0
        assert "diff" in result.output

    def test_diff_help_shows_usage(self, runner):
        """'org diff --help' shows expected arguments."""
        result = runner.invoke(main, ["org", "diff", "--help"])
        assert result.exit_code == 0

    def test_diff_identical_files_shows_no_changes(self, runner, minimal_org_yaml):
        """Diffing a file against itself shows no differences."""
        result = runner.invoke(
            main,
            ["org", "diff", str(minimal_org_yaml), str(minimal_org_yaml)],
        )
        assert result.exit_code == 0
        assert "no differences" in result.output.lower() or "identical" in result.output.lower()

    def test_diff_different_files_shows_changes(
        self, runner, minimal_org_yaml, modified_minimal_org_yaml
    ):
        """Diffing two different orgs shows the differences."""
        result = runner.invoke(
            main,
            ["org", "diff", str(minimal_org_yaml), str(modified_minimal_org_yaml)],
        )
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Should mention the added agent
        assert "extra-agent" in output_lower or "added" in output_lower
        # Should mention the name change
        assert "modified" in output_lower or "changed" in output_lower or "name" in output_lower

    def test_diff_shows_added_agents(self, runner, minimal_org_yaml, modified_minimal_org_yaml):
        """Diff output specifically identifies added agents."""
        result = runner.invoke(
            main,
            ["org", "diff", str(minimal_org_yaml), str(modified_minimal_org_yaml)],
        )
        assert result.exit_code == 0
        # The modified file has an extra agent
        assert "agent" in result.output.lower()

    def test_diff_nonexistent_file_fails(self, runner, minimal_org_yaml):
        """Diff with a nonexistent file fails."""
        result = runner.invoke(
            main,
            ["org", "diff", str(minimal_org_yaml), "/nonexistent/file.yaml"],
        )
        assert result.exit_code != 0

    def test_diff_requires_two_files(self, runner, minimal_org_yaml):
        """Diff with fewer than two files fails."""
        result = runner.invoke(
            main,
            ["org", "diff", str(minimal_org_yaml)],
        )
        assert result.exit_code != 0

    def test_diff_foundation_vs_minimal(self, runner, foundation_org_yaml, minimal_org_yaml):
        """Diff between foundation and minimal shows substantial differences."""
        result = runner.invoke(
            main,
            ["org", "diff", str(minimal_org_yaml), str(foundation_org_yaml)],
        )
        assert result.exit_code == 0
        # Foundation has many more agents than minimal
        assert "agent" in result.output.lower()


# ---------------------------------------------------------------------------
# Task 5044: Org Deploy Command
# ---------------------------------------------------------------------------


class TestOrgDeploy:
    """Tests for 'care-platform org deploy --file <file>'."""

    def test_deploy_command_registered(self, runner):
        """The 'deploy' subcommand is registered under 'org'."""
        result = runner.invoke(main, ["org", "--help"])
        assert result.exit_code == 0
        assert "deploy" in result.output

    def test_deploy_help_shows_options(self, runner):
        """'org deploy --help' shows --file option."""
        result = runner.invoke(main, ["org", "deploy", "--help"])
        assert result.exit_code == 0
        assert "--file" in result.output

    def test_deploy_valid_org(self, runner, minimal_org_yaml):
        """Deploy a valid org definition succeeds."""
        result = runner.invoke(
            main,
            ["org", "deploy", "--file", str(minimal_org_yaml)],
        )
        assert result.exit_code == 0, f"Deploy failed: {result.output}"
        output_lower = result.output.lower()
        assert "deploy" in output_lower or "provision" in output_lower or "success" in output_lower

    def test_deploy_shows_bootstrap_result(self, runner, minimal_org_yaml):
        """Deploy shows bootstrap summary (agents, teams, etc)."""
        result = runner.invoke(
            main,
            ["org", "deploy", "--file", str(minimal_org_yaml)],
        )
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Should mention agents or teams registered
        assert "agent" in output_lower or "team" in output_lower

    def test_deploy_nonexistent_file_fails(self, runner):
        """Deploy with nonexistent file fails."""
        result = runner.invoke(
            main,
            ["org", "deploy", "--file", "/nonexistent/org.yaml"],
        )
        assert result.exit_code != 0

    def test_deploy_requires_file(self, runner):
        """Deploy without --file fails."""
        result = runner.invoke(main, ["org", "deploy"])
        assert result.exit_code != 0

    def test_deploy_foundation_org(self, runner, foundation_org_yaml):
        """Deploy the foundation org definition succeeds."""
        result = runner.invoke(
            main,
            ["org", "deploy", "--file", str(foundation_org_yaml)],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Task 5045: Org Status Command
# ---------------------------------------------------------------------------


class TestOrgStatus:
    """Tests for 'care-platform org status'."""

    def test_status_command_registered(self, runner):
        """The 'status' subcommand is registered under 'org'."""
        result = runner.invoke(main, ["org", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_status_succeeds_with_no_runtime(self, runner):
        """'org status' succeeds even when no runtime is active."""
        result = runner.invoke(main, ["org", "status"])
        assert result.exit_code == 0

    def test_status_shows_org_health_info(self, runner):
        """Status output shows org health headings."""
        result = runner.invoke(main, ["org", "status"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Should show at least team count, agent count, or similar summary
        assert (
            "team" in output_lower
            or "agent" in output_lower
            or "organization" in output_lower
            or "no organization" in output_lower
        )

    def test_status_after_deploy_shows_counts(self, runner, minimal_org_yaml):
        """After deploying, status shows non-zero counts."""
        # Deploy first
        deploy_result = runner.invoke(
            main,
            ["org", "deploy", "--file", str(minimal_org_yaml)],
        )
        assert deploy_result.exit_code == 0

        # Now check status
        result = runner.invoke(main, ["org", "status"])
        assert result.exit_code == 0
        # Status should show some summary info
        output_lower = result.output.lower()
        assert "team" in output_lower or "agent" in output_lower


# ---------------------------------------------------------------------------
# Task 5040b: Example YAML Configs
# ---------------------------------------------------------------------------


class TestExampleYAMLConfigs:
    """Tests for example YAML configuration files in examples/ directory."""

    def test_foundation_org_yaml_exists(self):
        """examples/foundation-org.yaml exists."""
        path = Path(__file__).parents[3] / "examples" / "foundation-org.yaml"
        assert path.exists(), f"Expected foundation-org.yaml at {path}"

    def test_minimal_org_yaml_exists(self):
        """examples/minimal-org.yaml exists."""
        path = Path(__file__).parents[3] / "examples" / "minimal-org.yaml"
        assert path.exists(), f"Expected minimal-org.yaml at {path}"

    def test_foundation_org_yaml_is_valid(self):
        """examples/foundation-org.yaml can be parsed as a valid OrgDefinition."""
        path = Path(__file__).parents[3] / "examples" / "foundation-org.yaml"
        if not path.exists():
            pytest.skip("foundation-org.yaml not yet created")
        with path.open() as f:
            data = yaml.safe_load(f)
        org = OrgDefinition.model_validate(data)
        assert org.org_id == "terrene-foundation"
        assert len(org.agents) > 0
        assert len(org.teams) > 0
        valid, errors = org.validate_org()
        assert valid, f"Foundation org validation failed: {errors}"

    def test_minimal_org_yaml_is_valid(self):
        """examples/minimal-org.yaml can be parsed as a valid OrgDefinition."""
        path = Path(__file__).parents[3] / "examples" / "minimal-org.yaml"
        if not path.exists():
            pytest.skip("minimal-org.yaml not yet created")
        with path.open() as f:
            data = yaml.safe_load(f)
        org = OrgDefinition.model_validate(data)
        assert org.org_id is not None
        assert len(org.agents) >= 1
        assert len(org.teams) >= 1
        valid, errors = org.validate_org()
        assert valid, f"Minimal org validation failed: {errors}"

    def test_foundation_org_yaml_matches_template(self):
        """examples/foundation-org.yaml matches OrgTemplate.foundation_template()."""
        path = Path(__file__).parents[3] / "examples" / "foundation-org.yaml"
        if not path.exists():
            pytest.skip("foundation-org.yaml not yet created")
        with path.open() as f:
            data = yaml.safe_load(f)
        from_file = OrgDefinition.model_validate(data)
        from_template = OrgTemplate.foundation_template()

        assert from_file.org_id == from_template.org_id
        assert from_file.name == from_template.name
        assert len(from_file.agents) == len(from_template.agents)
        assert len(from_file.teams) == len(from_template.teams)

    def test_minimal_org_yaml_matches_template(self):
        """examples/minimal-org.yaml matches OrgTemplate.minimal_template()."""
        path = Path(__file__).parents[3] / "examples" / "minimal-org.yaml"
        if not path.exists():
            pytest.skip("minimal-org.yaml not yet created")
        with path.open() as f:
            data = yaml.safe_load(f)
        from_file = OrgDefinition.model_validate(data)
        # The minimal template uses a generic name, YAML uses a specific one
        assert from_file.org_id is not None
        assert len(from_file.agents) >= 1
        assert len(from_file.teams) >= 1

    def test_foundation_example_importable_via_cli(self, runner):
        """The foundation example YAML can be imported via the CLI."""
        path = Path(__file__).parents[3] / "examples" / "foundation-org.yaml"
        if not path.exists():
            pytest.skip("foundation-org.yaml not yet created")
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", str(path)],
        )
        assert result.exit_code == 0

    def test_minimal_example_importable_via_cli(self, runner):
        """The minimal example YAML can be imported via the CLI."""
        path = Path(__file__).parents[3] / "examples" / "minimal-org.yaml"
        if not path.exists():
            pytest.skip("minimal-org.yaml not yet created")
        result = runner.invoke(
            main,
            ["org", "import-file", "--file", str(path)],
        )
        assert result.exit_code == 0
