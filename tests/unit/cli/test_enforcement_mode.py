# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for platform-level enforcement mode toggle (TODO-23).

Validates:
1. EnforcementMode enum has three values: enforce, shadow, disabled
2. PlatformSettings stores and retrieves enforcement_mode
3. CLI `pact config show` displays current mode
"""

import pytest
from click.testing import CliRunner

from pact_platform.engine.settings import EnforcementMode, PlatformSettings


class TestEnforcementMode:
    """Unit tests for the EnforcementMode enum and PlatformSettings."""

    def test_enforcement_mode_values(self):
        """EnforcementMode must have exactly three values."""
        assert EnforcementMode.ENFORCE == "enforce"
        assert EnforcementMode.SHADOW == "shadow"
        assert EnforcementMode.DISABLED == "disabled"
        assert len(EnforcementMode) == 3

    def test_platform_settings_default_is_enforce(self):
        """Default enforcement mode must be 'enforce'."""
        settings = PlatformSettings()
        assert settings.enforcement_mode == EnforcementMode.ENFORCE

    def test_platform_settings_set_shadow(self):
        """Can set enforcement_mode to shadow."""
        settings = PlatformSettings(enforcement_mode=EnforcementMode.SHADOW)
        assert settings.enforcement_mode == EnforcementMode.SHADOW

    def test_platform_settings_set_disabled(self):
        """Can set enforcement_mode to disabled."""
        settings = PlatformSettings(enforcement_mode=EnforcementMode.DISABLED)
        assert settings.enforcement_mode == EnforcementMode.DISABLED

    def test_platform_settings_from_string(self):
        """Enforcement mode should be constructible from string."""
        settings = PlatformSettings(enforcement_mode="shadow")
        assert settings.enforcement_mode == EnforcementMode.SHADOW

    def test_platform_settings_invalid_mode_raises(self):
        """Invalid enforcement mode must raise a validation error."""
        with pytest.raises(ValueError):
            PlatformSettings(enforcement_mode="invalid_mode")


class TestConfigShowCommand:
    """Tests for `pact config show` CLI command."""

    @pytest.fixture()
    def runner(self) -> CliRunner:
        return CliRunner()

    @pytest.fixture()
    def cli_mod(self):
        import pact_platform.cli as mod

        return mod

    def test_config_show_displays_enforcement_mode(self, runner, cli_mod):
        """pact config show should display enforcement mode."""
        result = runner.invoke(cli_mod.main, ["config", "show"])
        assert result.exit_code == 0
        assert "enforcement_mode" in result.output.lower() or "Enforcement Mode" in result.output

    def test_config_show_displays_enforce_as_default(self, runner, cli_mod):
        """Default enforcement mode displayed should be 'enforce'."""
        result = runner.invoke(cli_mod.main, ["config", "show"])
        assert result.exit_code == 0
        assert "enforce" in result.output.lower()
