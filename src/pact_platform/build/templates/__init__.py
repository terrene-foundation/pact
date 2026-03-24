# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Template library — predefined constraint envelope and team templates.

Provides TemplateRegistry with built-in templates for the six Foundation
team types: media, governance, standards, partnerships, engineering, and executive.

Includes YAML loading (load_from_yaml), custom registration with validation
(register), and multi-team composition (via OrgBuilder.compose_from_templates).
"""

from pact_platform.build.templates.registry import TeamTemplate, TemplateRegistry

__all__ = [
    "TeamTemplate",
    "TemplateRegistry",
]
