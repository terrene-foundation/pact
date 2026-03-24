# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Smoke tests for pact and pact_platform packages."""


def test_pact_package_importable():
    """Verify the pact package (kailash-pact) is importable."""
    import pact

    assert pact.__version__


def test_pact_platform_importable():
    """Verify the pact_platform package is importable."""
    import pact_platform

    assert pact_platform.__version__ == "0.3.0"


def test_submodules_importable():
    """Verify all pact_platform submodules are importable."""
    import pact_platform.build.config
    import pact_platform.build.workspace
    import pact_platform.trust
    import pact_platform.trust.audit
    import pact_platform.trust.constraint
    import pact_platform.use.execution

    assert pact_platform.trust is not None
    assert pact_platform.trust.constraint is not None
    assert pact_platform.use.execution is not None
    assert pact_platform.trust.audit is not None
    assert pact_platform.build.workspace is not None
    assert pact_platform.build.config is not None


def test_governance_from_kailash_pact():
    """Verify governance imports come from kailash-pact."""
    from pact.governance import GovernanceEngine

    assert GovernanceEngine is not None
