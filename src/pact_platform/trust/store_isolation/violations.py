# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Plane violation error — raised when a store operation violates plane isolation."""

from __future__ import annotations


class PlaneViolationError(Exception):
    """Raised when a store operation is attempted on the wrong plane.

    For example, a data plane store attempting to write genesis records
    (a management-only operation) will raise this error.

    Args:
        plane_name: The plane that was violated (e.g., 'data plane', 'management plane').
        operation: The operation that was attempted (e.g., 'store_genesis').
    """

    def __init__(self, plane_name: str, operation: str) -> None:
        self.plane_name = plane_name
        self.operation = operation
        super().__init__(
            f"Operation '{operation}' is not permitted on the {plane_name}. "
            f"This operation belongs to the other plane."
        )
