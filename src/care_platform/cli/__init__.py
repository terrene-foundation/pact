# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""CARE Platform CLI — command-line interface for platform operations.

Commands:
    care-platform --version                              Show version
    care-platform validate <file>                        Validate a YAML configuration file
    care-platform status                                 Show platform status
    care-platform org create --template <t> --name <n>   Create an org from a template
    care-platform org validate --config <file>           Validate an org config file
    care-platform org list-templates                     List available templates
"""

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from care_platform import __version__
from care_platform.config.env import _load_dotenv
from care_platform.config.loader import ConfigError, load_config

console = Console()
error_console = Console(stderr=True)


@click.group()
@click.version_option(version=__version__, prog_name="care-platform")
def main() -> None:
    """CARE Platform — Governed operational model for AI agent organizations."""
    _load_dotenv()


@main.command()
@click.argument("config_file", type=click.Path(exists=False))
def validate(config_file: str) -> None:
    """Validate a YAML configuration file against the CARE Platform schema."""
    try:
        config = load_config(config_file)
    except ConfigError as e:
        error_console.print(f"[bold red]Validation failed:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        sys.exit(1)

    # Build summary table
    table = Table(title="Configuration Summary", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    table.add_row("Organization", config.name)
    table.add_row("Genesis Authority", config.genesis.authority)
    table.add_row("Default Posture", config.default_posture.value)
    table.add_row("Constraint Envelopes", str(len(config.constraint_envelopes)))
    table.add_row("Agents", str(len(config.agents)))
    table.add_row("Teams", str(len(config.teams)))
    table.add_row("Workspaces", str(len(config.workspaces)))

    console.print()
    console.print(
        Panel(
            f"[bold green]Valid[/bold green] configuration: {config_file}",
            title="CARE Platform",
            border_style="green",
        )
    )
    console.print(table)


@main.command()
def status() -> None:
    """Show current platform status."""
    console.print()
    console.print(
        Panel(
            "[dim]No active workspaces[/dim]\n\n"
            "Load a configuration to get started:\n"
            "  [cyan]care-platform validate config.yaml[/cyan]",
            title="CARE Platform Status",
            border_style="blue",
        )
    )


# ---------------------------------------------------------------------------
# org subcommand group
# ---------------------------------------------------------------------------


@main.group()
def org() -> None:
    """Organization Builder — create and manage CARE-governed organizations."""


@org.command("list-templates")
def org_list_templates() -> None:
    """List all available organization templates."""
    from care_platform.templates.registry import TemplateRegistry

    registry = TemplateRegistry()
    templates = registry.list()

    table = Table(title="Available Templates", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Agents")

    for name in templates:
        tpl = registry.get(name)
        table.add_row(name, tpl.description, str(len(tpl.agents)))

    console.print()
    console.print(table)


@org.command("create")
@click.option(
    "--template",
    required=True,
    help="Template name (use 'org list-templates' to see options, or 'minimal')",
)
@click.option("--name", required=True, help="Organization name")
def org_create(template: str, name: str) -> None:
    """Create an organization from a template."""
    from care_platform.org.builder import OrgTemplate
    from care_platform.templates.registry import TemplateRegistry

    # Handle 'minimal' template specially (from OrgTemplate)
    if template == "minimal":
        org_def = OrgTemplate.minimal_template(name)
        valid, errors = org_def.validate_org()
        if not valid:
            error_console.print(
                f"[bold red]Validation failed for generated org:[/bold red]\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
            sys.exit(1)
        console.print()
        console.print(
            Panel(
                f"[bold green]Created[/bold green] organization '{name}' from template 'minimal'\n\n"
                f"  Organization ID: {org_def.org_id}\n"
                f"  Teams: {len(org_def.teams)}\n"
                f"  Agents: {len(org_def.agents)}\n"
                f"  Envelopes: {len(org_def.envelopes)}\n"
                f"  Workspaces: {len(org_def.workspaces)}",
                title="CARE Platform - Organization Created",
                border_style="green",
            )
        )
        return

    # Use TemplateRegistry for named templates
    try:
        registry = TemplateRegistry()
        tpl = registry.get(template)
    except ValueError as e:
        error_console.print(f"[bold red]Template error:[/bold red] {e}")
        sys.exit(1)

    console.print()
    console.print(
        Panel(
            f"[bold green]Created[/bold green] organization '{name}' from template '{template}'\n\n"
            f"  Team: {tpl.team.name}\n"
            f"  Agents: {len(tpl.agents)}\n"
            f"  Envelopes: {len(tpl.envelopes)}",
            title="CARE Platform - Organization Created",
            border_style="green",
        )
    )


@org.command("validate")
@click.option(
    "--config",
    "config_file",
    required=True,
    type=click.Path(exists=False),
    help="Path to YAML org configuration file",
)
def org_validate(config_file: str) -> None:
    """Validate an organization configuration file."""
    try:
        config = load_config(config_file)
    except ConfigError as e:
        error_console.print(f"[bold red]Org validation failed:[/bold red] {e}")
        sys.exit(1)
    except FileNotFoundError:
        error_console.print(f"[bold red]File not found:[/bold red] {config_file}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        sys.exit(1)

    console.print()
    console.print(
        Panel(
            f"[bold green]Valid[/bold green] organization configuration: {config_file}\n\n"
            f"  Organization: {config.name}\n"
            f"  Teams: {len(config.teams)}\n"
            f"  Agents: {len(config.agents)}\n"
            f"  Envelopes: {len(config.constraint_envelopes)}",
            title="CARE Platform - Org Validation",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
