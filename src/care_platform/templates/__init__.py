# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Template library — predefined constraint envelope and team templates.

Provides TemplateRegistry with built-in templates for the four Foundation
team types: media, governance, standards, and partnerships.
"""

from care_platform.templates.registry import TeamTemplate, TemplateRegistry

__all__ = [
    "TeamTemplate",
    "TemplateRegistry",
]
