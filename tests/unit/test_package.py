# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Smoke tests for care_platform package."""


def test_package_imports():
    """Verify the care_platform package is importable."""
    import care_platform

    assert care_platform.__version__ == "0.1.0"


def test_submodules_importable():
    """Verify all submodules are importable."""
    import care_platform.trust.audit
    import care_platform.build.config
    import care_platform.trust.constraint
    import care_platform.use.execution
    import care_platform.trust
    import care_platform.build.workspace

    assert care_platform.trust is not None
    assert care_platform.trust.constraint is not None
    assert care_platform.use.execution is not None
    assert care_platform.trust.audit is not None
    assert care_platform.build.workspace is not None
    assert care_platform.build.config is not None
