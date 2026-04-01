# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Platform-level settings including enforcement mode toggle (TODO-23).

EnforcementMode controls whether governance runs through:
- ``enforce``: HookEnforcer blocks/holds actions (production default)
- ``shadow``: ShadowEnforcer observes but never blocks
- ``disabled``: Governance is completely bypassed (development only)

Usage:
    settings = PlatformSettings()
    assert settings.enforcement_mode == EnforcementMode.ENFORCE

    settings = PlatformSettings(enforcement_mode="shadow")
    assert settings.enforcement_mode == EnforcementMode.SHADOW
"""

from __future__ import annotations

import logging
import os
from enum import Enum

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class EnforcementMode(str, Enum):
    """Governance enforcement mode.

    Controls how governance verdicts are applied at runtime.
    """

    ENFORCE = "enforce"
    SHADOW = "shadow"
    DISABLED = "disabled"


class PlatformSettings(BaseModel):
    """Platform-level configuration settings.

    These settings control runtime behavior of the PACT platform.
    They can be set via environment variables or programmatically.
    """

    enforcement_mode: EnforcementMode = Field(
        default=EnforcementMode.ENFORCE,
        description=(
            "Governance enforcement mode. "
            "'enforce' blocks/holds actions (production). "
            "'shadow' observes without blocking. "
            "'disabled' bypasses governance entirely."
        ),
    )

    @field_validator("enforcement_mode", mode="before")
    @classmethod
    def _coerce_enforcement_mode(cls, v: object) -> object:
        """Accept string values and convert to EnforcementMode.

        The ``disabled`` mode requires ``PACT_ALLOW_DISABLED_MODE=true``
        in the environment to prevent accidental production use.
        """
        mode = v
        if isinstance(v, str):
            try:
                mode = EnforcementMode(v.lower())
            except ValueError:
                valid = ", ".join(m.value for m in EnforcementMode)
                raise ValueError(
                    f"Invalid enforcement_mode '{v}'. Must be one of: {valid}"
                ) from None
        if isinstance(mode, EnforcementMode) and mode == EnforcementMode.DISABLED:
            guard = os.environ.get("PACT_ALLOW_DISABLED_MODE", "").lower()
            if guard != "true":
                raise ValueError(
                    "enforcement_mode='disabled' requires environment variable "
                    "PACT_ALLOW_DISABLED_MODE=true to be set. This prevents "
                    "accidental production deployment with governance disabled."
                )
        return mode

    @classmethod
    def from_env(cls) -> PlatformSettings:
        """Load settings from environment variables.

        Reads:
        - PACT_ENFORCEMENT_MODE: enforce | shadow | disabled (default: enforce)
        """
        mode = os.environ.get("PACT_ENFORCEMENT_MODE", "enforce")
        return cls(enforcement_mode=mode)


# Module-level singleton — populated on first access or by init code.
_settings: PlatformSettings | None = None


def get_platform_settings() -> PlatformSettings:
    """Return the current platform settings singleton.

    If not explicitly set, initializes from environment variables.
    """
    global _settings
    if _settings is None:
        _settings = PlatformSettings.from_env()
    return _settings


def set_platform_settings(settings: PlatformSettings) -> None:
    """Set the platform settings singleton.

    Args:
        settings: The PlatformSettings to use.
    """
    global _settings
    _settings = settings
