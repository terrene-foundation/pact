# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Shared utilities for the org build package."""

from __future__ import annotations

import re


def _slugify(name: str) -> str:
    """Convert a human-readable name to a slug for use as an ID.

    Lowercases, replaces spaces and underscores with hyphens, and strips
    any characters outside [a-z0-9-] to prevent path traversal.
    """
    slug = name.lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug
