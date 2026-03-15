# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Smoke tests for care_platform package."""


def test_package_imports():
    """Verify the care_platform package is importable."""
    import care_platform

    assert care_platform.__version__ == "0.1.0"


def test_submodules_importable():
    """Verify all submodules are importable."""
    import care_platform.audit
    import care_platform.config
    import care_platform.constraint
    import care_platform.execution
    import care_platform.trust
    import care_platform.workspace

    assert care_platform.trust is not None
    assert care_platform.constraint is not None
    assert care_platform.execution is not None
    assert care_platform.audit is not None
    assert care_platform.workspace is not None
    assert care_platform.config is not None
