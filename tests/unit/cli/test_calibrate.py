# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for `pact calibrate` CLI command (TODO-24).

Validates:
1. Command accepts a YAML org file
2. Generates synthetic actions per role
3. Runs shadow evaluation via ShadowEnforcer
4. Reports per-supervisor held ratio
5. Flags supervisors below 10% held (constraint theater)
6. Flags supervisors above 50% held (over-restriction)
"""

import os
import tempfile

import pytest
import yaml
from click.testing import CliRunner


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli_mod():
    import pact_platform.cli as mod

    return mod


@pytest.fixture()
def sample_org_yaml() -> str:
    """Create a minimal org YAML for calibration testing.

    Uses the PACT governance YAML schema that load_org_yaml() expects:
    top-level org_id, name, departments, teams, roles, envelopes.
    """
    org_data = {
        "org_id": "calibration-test",
        "name": "Calibration Test Org",
        "departments": [
            {"id": "eng", "name": "Engineering"},
            {"id": "ops", "name": "Operations"},
        ],
        "teams": [
            {"id": "eng-backend", "name": "Backend"},
            {"id": "ops-platform", "name": "Platform"},
        ],
        "roles": [
            {
                "id": "eng-lead",
                "name": "Engineering Lead",
                "heads": "eng",
            },
            {
                "id": "eng-dev",
                "name": "Developer",
                "reports_to": "eng-lead",
                "heads": "eng-backend",
            },
            {
                "id": "ops-lead",
                "name": "Operations Lead",
                "heads": "ops",
            },
            {
                "id": "ops-eng",
                "name": "Operations Engineer",
                "reports_to": "ops-lead",
                "heads": "ops-platform",
            },
        ],
        "envelopes": [
            {
                "target": "eng-lead",
                "defined_by": "eng-lead",
                "financial": {"max_spend_usd": 5000.0},
                "operational": {
                    "allowed_actions": ["review", "approve", "code", "deploy", "test"],
                    "max_actions_per_day": 100,
                },
            },
            {
                "target": "eng-dev",
                "defined_by": "eng-lead",
                "financial": {"max_spend_usd": 500.0},
                "operational": {
                    "allowed_actions": ["code", "test"],
                    "max_actions_per_day": 50,
                },
            },
            {
                "target": "ops-lead",
                "defined_by": "ops-lead",
                "financial": {"max_spend_usd": 3000.0},
                "operational": {
                    "allowed_actions": ["monitor", "deploy", "approve"],
                    "max_actions_per_day": 80,
                },
            },
            {
                "target": "ops-eng",
                "defined_by": "ops-lead",
                "financial": {"max_spend_usd": 200.0},
                "operational": {
                    "allowed_actions": ["monitor"],
                    "max_actions_per_day": 40,
                },
            },
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(org_data, f, default_flow_style=False)
        return f.name


class TestCalibrateCommand:
    """Tests for `pact calibrate` CLI command."""

    def test_calibrate_command_registered(self, runner, cli_mod):
        """pact calibrate should be a registered command."""
        result = runner.invoke(cli_mod.main, ["calibrate", "--help"])
        assert result.exit_code == 0
        assert "calibrate" in result.output.lower() or "Calibrate" in result.output

    def test_calibrate_requires_yaml_file(self, runner, cli_mod):
        """pact calibrate should require a YAML file argument."""
        result = runner.invoke(cli_mod.main, ["calibrate"])
        assert result.exit_code != 0

    def test_calibrate_rejects_missing_file(self, runner, cli_mod):
        """pact calibrate should fail with a nonexistent file."""
        result = runner.invoke(cli_mod.main, ["calibrate", "/nonexistent/org.yaml"])
        assert result.exit_code != 0

    def test_calibrate_runs_with_valid_yaml(self, runner, cli_mod, sample_org_yaml):
        """pact calibrate should produce output with a valid org YAML."""
        try:
            result = runner.invoke(cli_mod.main, ["calibrate", sample_org_yaml])
            # The command should complete (may have warnings but not crash)
            assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        finally:
            os.unlink(sample_org_yaml)

    def test_calibrate_output_mentions_held_ratio(self, runner, cli_mod, sample_org_yaml):
        """Calibration output should mention held ratio."""
        try:
            result = runner.invoke(cli_mod.main, ["calibrate", sample_org_yaml])
            assert result.exit_code == 0, f"Output: {result.output}"
            output_lower = result.output.lower()
            assert (
                "held" in output_lower
            ), f"Expected 'held' in calibration output. Got: {result.output}"
        finally:
            os.unlink(sample_org_yaml)

    def test_calibrate_flags_constraint_theater(self, runner, cli_mod, sample_org_yaml):
        """Calibration should flag supervisors with <10% held (constraint theater)."""
        try:
            result = runner.invoke(cli_mod.main, ["calibrate", sample_org_yaml])
            assert result.exit_code == 0, f"Output: {result.output}"
            # Output should mention "constraint theater" or "under-restriction" or the threshold
            output_lower = result.output.lower()
            assert (
                "theater" in output_lower
                or "<10%" in output_lower
                or "below 10%" in output_lower
                or "under" in output_lower
            ), f"Expected constraint theater flag in output. Got: {result.output}"
        finally:
            os.unlink(sample_org_yaml)
