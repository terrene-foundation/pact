# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for PACT configuration loader."""

import pytest

from pact_platform.build.config.loader import ConfigError, load_config, load_config_from_dict


class TestLoadConfigFromDict:
    def test_valid_minimal_config(self):
        data = {
            "name": "Test Org",
            "genesis": {
                "authority": "test.org",
                "authority_name": "Test Organization",
            },
        }
        config = load_config_from_dict(data)
        assert config.name == "Test Org"
        assert config.genesis.authority == "test.org"

    def test_missing_required_field(self):
        with pytest.raises(ConfigError, match="Configuration validation failed"):
            load_config_from_dict({"name": "Test"})

    def test_invalid_posture_value(self):
        with pytest.raises(ConfigError, match="Configuration validation failed"):
            load_config_from_dict(
                {
                    "name": "Test",
                    "genesis": {"authority": "x", "authority_name": "X"},
                    "default_posture": "invalid_posture",
                }
            )

    def test_full_config_with_envelopes(self):
        data = {
            "name": "Full Test",
            "genesis": {"authority": "test.org", "authority_name": "Test"},
            "constraint_envelopes": [
                {
                    "id": "env-1",
                    "financial": {"max_spend_usd": 0.0},
                    "operational": {
                        "allowed_actions": ["read"],
                        "blocked_actions": ["delete"],
                    },
                }
            ],
            "agents": [
                {
                    "id": "agent-1",
                    "name": "Agent",
                    "role": "Testing",
                    "constraint_envelope": "env-1",
                }
            ],
        }
        config = load_config_from_dict(data)
        assert len(config.constraint_envelopes) == 1
        assert len(config.agents) == 1
        assert config.agents[0].constraint_envelope == "env-1"


class TestLoadConfigFromFile:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_wrong_extension(self, tmp_path):
        bad_file = tmp_path / "config.json"
        bad_file.write_text("{}")
        with pytest.raises(ConfigError, match="must be .yml or .yaml"):
            load_config(bad_file)

    def test_invalid_yaml(self, tmp_path):
        bad_yaml = tmp_path / "config.yaml"
        bad_yaml.write_text(":\n  invalid: [yaml\n  broken")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(bad_yaml)

    def test_yaml_not_mapping(self, tmp_path):
        list_yaml = tmp_path / "config.yaml"
        list_yaml.write_text("- item1\n- item2\n")
        with pytest.raises(ConfigError, match="must be a YAML mapping"):
            load_config(list_yaml)

    def test_valid_yaml_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
name: "Test Org"
genesis:
  authority: "test.org"
  authority_name: "Test Organization"
agents:
  - id: agent-1
    name: Agent One
    role: Testing
    constraint_envelope: env-1
"""
        )
        config = load_config(config_file)
        assert config.name == "Test Org"
        assert len(config.agents) == 1

    def test_example_config_loads(self):
        """Verify the example config file is valid."""
        from pathlib import Path

        example_path = Path(__file__).parents[3] / "examples" / "care-config.yaml"
        if example_path.exists():
            config = load_config(example_path)
            assert config.name == "Terrene Foundation"
            assert config.genesis.authority == "terrene.foundation"
            assert len(config.constraint_envelopes) >= 1
            assert len(config.agents) >= 1
            assert len(config.teams) >= 1


class TestLoadConfigDefaults:
    def test_default_envelope(self):
        from pact_platform.build.config.defaults import default_constraint_envelope

        env = default_constraint_envelope("test-agent")
        assert env.id == "test-agent-envelope"
        assert env.financial.max_spend_usd == 0.0
        assert env.communication.internal_only is True
        assert env.communication.external_requires_approval is True
        assert "pii" in env.data_access.blocked_data_types

    def test_default_gradient(self):
        from pact_platform.build.config.defaults import default_verification_gradient

        grad = default_verification_gradient()
        from pact_platform.build.config.schema import VerificationLevel

        assert grad.default_level == VerificationLevel.HELD
