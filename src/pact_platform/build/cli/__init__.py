# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""PACT CLI — command-line interface for platform operations.

Commands:
    pact --version                              Show version
    pact validate <file>                        Validate a YAML configuration file
    pact status                                 Show platform status
    pact org create --template <t> --name <n>   Create an org from a template
    pact org validate --config <file>           Validate an org config file
    pact org list-templates                     List available templates
    pact org export --org-id <id> --output <f>  Export org to YAML
    pact org import-file --file <f>             Import org from YAML/JSON
    pact org diff <file1> <file2>               Compare two org definitions
    pact org deploy --file <f>                  Deploy org to trust store
    pact org status                             Show runtime org health
"""

import json
import logging
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pact_platform import __version__
from pact_platform.build.config.env import _load_dotenv
from pact_platform.build.config.loader import ConfigError, load_config

logger = logging.getLogger(__name__)

console = Console()
error_console = Console(stderr=True)


@click.group()
@click.version_option(version=__version__, prog_name="pact")
def main() -> None:
    """PACT — Governed operational model for AI agent organizations."""
    _load_dotenv()


@main.command()
@click.argument("config_file", type=click.Path(exists=False))
def validate(config_file: str) -> None:
    """Validate a YAML configuration file against the PACT schema."""
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
            title="PACT",
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
            "  [cyan]pact validate config.yaml[/cyan]",
            title="PACT Status",
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
    from pact_platform.build.templates.registry import TemplateRegistry

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
    from pact_platform.build.org.builder import OrgTemplate
    from pact_platform.build.templates.registry import TemplateRegistry

    # Handle 'minimal' template specially (from OrgTemplate)
    if template == "minimal":
        org_def = OrgTemplate.minimal_template(name)
        valid, errors = org_def.validate_org()
        if not valid:
            error_console.print(
                "[bold red]Validation failed for generated org:[/bold red]\n"
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
                title="PACT - Organization Created",
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
            title="PACT - Organization Created",
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
            title="PACT - Org Validation",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# Task 5041: org export — export an OrgDefinition to YAML
# ---------------------------------------------------------------------------


@org.command("export")
@click.option(
    "--org-id",
    required=True,
    help="Organization template ID to export ('minimal' or 'foundation')",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output file path (YAML format)",
)
def org_export(org_id: str, output: str) -> None:
    """Export an organization definition to a YAML file."""
    from pact_platform.build.org.builder import OrgDefinition, OrgTemplate

    # Resolve the org definition from known templates
    org_def: OrgDefinition | None = None
    if org_id == "minimal":
        org_def = OrgTemplate.minimal_template("Test Org")
    elif org_id == "foundation":
        org_def = OrgTemplate.foundation_template()
    else:
        error_console.print(
            f"[bold red]Organization not found:[/bold red] '{org_id}'\n"
            "  Available org IDs: 'minimal', 'foundation'"
        )
        sys.exit(1)

    # Serialize with Pydantic model_dump and write as YAML
    data = org_def.model_dump(mode="json")
    output_path = Path(output)
    with output_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    console.print()
    console.print(
        Panel(
            f"[bold green]Exported[/bold green] organization '{org_def.name}' to {output}\n\n"
            f"  Organization ID: {org_def.org_id}\n"
            f"  Agents: {len(org_def.agents)}\n"
            f"  Teams: {len(org_def.teams)}\n"
            f"  Envelopes: {len(org_def.envelopes)}\n"
            f"  Workspaces: {len(org_def.workspaces)}",
            title="PACT - Org Exported",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# Task 5042: org import-file — import an OrgDefinition from YAML/JSON
# ---------------------------------------------------------------------------


@org.command("import-file")
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to YAML or JSON org definition file",
)
def org_import_file(file_path: str) -> None:
    """Import and validate an organization definition from a YAML or JSON file."""
    from pact_platform.build.org.builder import OrgDefinition

    path = Path(file_path)

    # Load from YAML or JSON based on extension
    try:
        raw_text = path.read_text()
        if path.suffix.lower() == ".json":
            data = json.loads(raw_text)
        else:
            data = yaml.safe_load(raw_text)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        error_console.print(f"[bold red]Parse error:[/bold red] {e}")
        sys.exit(1)
    except OSError as e:
        error_console.print(f"[bold red]File read error:[/bold red] {e}")
        sys.exit(1)

    if not isinstance(data, dict):
        error_console.print(
            f"[bold red]Invalid format:[/bold red] Expected a mapping, got {type(data).__name__}"
        )
        sys.exit(1)

    # Parse into OrgDefinition
    try:
        org_def = OrgDefinition.model_validate(data)
    except Exception as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {e}")
        sys.exit(1)

    # Run org validation
    valid, errors = org_def.validate_org()

    # Build summary table
    table = Table(title="Organization Summary", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    table.add_row("Organization ID", org_def.org_id)
    table.add_row("Name", org_def.name)
    table.add_row("Agents", str(len(org_def.agents)))
    table.add_row("Teams", str(len(org_def.teams)))
    table.add_row("Envelopes", str(len(org_def.envelopes)))
    table.add_row("Workspaces", str(len(org_def.workspaces)))
    table.add_row("Valid", "[green]Yes[/green]" if valid else "[red]No[/red]")

    console.print()
    if valid:
        console.print(
            Panel(
                f"[bold green]Successfully[/bold green] imported organization from {file_path}",
                title="PACT - Org Import",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold yellow]Imported[/bold yellow] organization from {file_path} "
                f"with {len(errors)} validation error(s):\n"
                + "\n".join(f"  - {e}" for e in errors),
                title="PACT - Org Import (Validation Errors)",
                border_style="yellow",
            )
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Task 5043: org diff — compare two OrgDefinition files
# ---------------------------------------------------------------------------


def _diff_org_defs(
    org1_data: dict,
    org2_data: dict,
) -> dict:
    """Compare two OrgDefinition dicts and return structured differences.

    Returns a dict with keys:
        - 'name_changed': tuple (old, new) or None
        - 'agents_added': list of agent IDs
        - 'agents_removed': list of agent IDs
        - 'agents_changed': list of (agent_id, changes_description)
        - 'teams_added': list of team IDs
        - 'teams_removed': list of team IDs
        - 'teams_changed': list of (team_id, changes_description)
        - 'envelopes_added': list of envelope IDs
        - 'envelopes_removed': list of envelope IDs
        - 'envelopes_changed': list of (envelope_id, changes_description)
    """
    result: dict = {
        "name_changed": None,
        "agents_added": [],
        "agents_removed": [],
        "agents_changed": [],
        "teams_added": [],
        "teams_removed": [],
        "teams_changed": [],
        "envelopes_added": [],
        "envelopes_removed": [],
        "envelopes_changed": [],
    }

    # Name change
    if org1_data.get("name") != org2_data.get("name"):
        result["name_changed"] = (org1_data.get("name"), org2_data.get("name"))

    # Agents diff
    agents1 = {a["id"]: a for a in org1_data.get("agents", [])}
    agents2 = {a["id"]: a for a in org2_data.get("agents", [])}
    result["agents_added"] = sorted(set(agents2.keys()) - set(agents1.keys()))
    result["agents_removed"] = sorted(set(agents1.keys()) - set(agents2.keys()))
    for aid in sorted(set(agents1.keys()) & set(agents2.keys())):
        if agents1[aid] != agents2[aid]:
            # Find which fields changed
            changed_fields = [k for k in agents1[aid] if agents1[aid].get(k) != agents2[aid].get(k)]
            result["agents_changed"].append((aid, changed_fields))

    # Teams diff
    teams1 = {t["id"]: t for t in org1_data.get("teams", [])}
    teams2 = {t["id"]: t for t in org2_data.get("teams", [])}
    result["teams_added"] = sorted(set(teams2.keys()) - set(teams1.keys()))
    result["teams_removed"] = sorted(set(teams1.keys()) - set(teams2.keys()))
    for tid in sorted(set(teams1.keys()) & set(teams2.keys())):
        if teams1[tid] != teams2[tid]:
            changed_fields = [k for k in teams1[tid] if teams1[tid].get(k) != teams2[tid].get(k)]
            result["teams_changed"].append((tid, changed_fields))

    # Envelopes diff
    envs1 = {e["id"]: e for e in org1_data.get("envelopes", [])}
    envs2 = {e["id"]: e for e in org2_data.get("envelopes", [])}
    result["envelopes_added"] = sorted(set(envs2.keys()) - set(envs1.keys()))
    result["envelopes_removed"] = sorted(set(envs1.keys()) - set(envs2.keys()))
    for eid in sorted(set(envs1.keys()) & set(envs2.keys())):
        if envs1[eid] != envs2[eid]:
            changed_fields = [k for k in envs1[eid] if envs1[eid].get(k) != envs2[eid].get(k)]
            result["envelopes_changed"].append((eid, changed_fields))

    return result


def _has_differences(diff: dict) -> bool:
    """Check if a diff result contains any differences."""
    if diff["name_changed"]:
        return True
    for key in [
        "agents_added",
        "agents_removed",
        "agents_changed",
        "teams_added",
        "teams_removed",
        "teams_changed",
        "envelopes_added",
        "envelopes_removed",
        "envelopes_changed",
    ]:
        if diff[key]:
            return True
    return False


@org.command("diff")
@click.argument("file1", type=click.Path(exists=True))
@click.argument("file2", type=click.Path(exists=True))
def org_diff(file1: str, file2: str) -> None:
    """Compare two organization definition files and show differences."""
    # Load both files
    try:
        with open(file1) as f:
            data1 = yaml.safe_load(f) if not file1.endswith(".json") else json.load(f)
        with open(file2) as f:
            data2 = yaml.safe_load(f) if not file2.endswith(".json") else json.load(f)
    except (yaml.YAMLError, json.JSONDecodeError, OSError) as e:
        error_console.print(f"[bold red]Failed to load files:[/bold red] {e}")
        sys.exit(1)

    if not isinstance(data1, dict) or not isinstance(data2, dict):
        error_console.print("[bold red]Both files must contain YAML/JSON mappings[/bold red]")
        sys.exit(1)

    diff = _diff_org_defs(data1, data2)

    if not _has_differences(diff):
        console.print()
        console.print(
            Panel(
                "[bold green]No differences[/bold green] found between the two organization files.",
                title="PACT - Org Diff",
                border_style="green",
            )
        )
        return

    # Build diff output using Rich tables
    console.print()
    console.print(
        Panel(
            f"Comparing [cyan]{file1}[/cyan] vs [cyan]{file2}[/cyan]",
            title="PACT - Org Diff",
            border_style="blue",
        )
    )

    # Name change
    if diff["name_changed"]:
        old_name, new_name = diff["name_changed"]
        console.print(f"\n  [yellow]Name changed:[/yellow] '{old_name}' -> '{new_name}'")

    # Agents
    if diff["agents_added"] or diff["agents_removed"] or diff["agents_changed"]:
        table = Table(title="Agent Changes", show_header=True, header_style="bold cyan")
        table.add_column("Change", style="bold")
        table.add_column("Agent ID")
        table.add_column("Details")

        for aid in diff["agents_added"]:
            table.add_row("[green]Added[/green]", aid, "New agent in second file")
        for aid in diff["agents_removed"]:
            table.add_row("[red]Removed[/red]", aid, "Present only in first file")
        for aid, fields in diff["agents_changed"]:
            table.add_row("[yellow]Changed[/yellow]", aid, ", ".join(fields))

        console.print()
        console.print(table)

    # Teams
    if diff["teams_added"] or diff["teams_removed"] or diff["teams_changed"]:
        table = Table(title="Team Changes", show_header=True, header_style="bold cyan")
        table.add_column("Change", style="bold")
        table.add_column("Team ID")
        table.add_column("Details")

        for tid in diff["teams_added"]:
            table.add_row("[green]Added[/green]", tid, "New team in second file")
        for tid in diff["teams_removed"]:
            table.add_row("[red]Removed[/red]", tid, "Present only in first file")
        for tid, fields in diff["teams_changed"]:
            table.add_row("[yellow]Changed[/yellow]", tid, ", ".join(fields))

        console.print()
        console.print(table)

    # Envelopes
    if diff["envelopes_added"] or diff["envelopes_removed"] or diff["envelopes_changed"]:
        table = Table(title="Envelope Changes", show_header=True, header_style="bold cyan")
        table.add_column("Change", style="bold")
        table.add_column("Envelope ID")
        table.add_column("Details")

        for eid in diff["envelopes_added"]:
            table.add_row("[green]Added[/green]", eid, "New envelope in second file")
        for eid in diff["envelopes_removed"]:
            table.add_row("[red]Removed[/red]", eid, "Present only in first file")
        for eid, fields in diff["envelopes_changed"]:
            table.add_row("[yellow]Changed[/yellow]", eid, ", ".join(fields))

        console.print()
        console.print(table)


# ---------------------------------------------------------------------------
# Task 5044: org deploy — deploy an OrgDefinition to the trust store
# ---------------------------------------------------------------------------


@org.command("deploy")
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to YAML or JSON org definition file",
)
def org_deploy(file_path: str) -> None:
    """Deploy an organization definition to the trust store via PlatformBootstrap."""
    from pact_platform.build.bootstrap import PlatformBootstrap
    from pact_platform.build.config.schema import (
        GenesisConfig,
        PactConfig,
    )
    from pact_platform.build.org.builder import OrgDefinition
    from pact_platform.trust.store.store import MemoryStore

    path = Path(file_path)

    # Load the org definition
    try:
        raw_text = path.read_text()
        if path.suffix.lower() == ".json":
            data = json.loads(raw_text)
        else:
            data = yaml.safe_load(raw_text)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        error_console.print(f"[bold red]Parse error:[/bold red] {e}")
        sys.exit(1)
    except OSError as e:
        error_console.print(f"[bold red]File read error:[/bold red] {e}")
        sys.exit(1)

    if not isinstance(data, dict):
        error_console.print(
            f"[bold red]Invalid format:[/bold red] Expected a mapping, got {type(data).__name__}"
        )
        sys.exit(1)

    # Parse and validate the OrgDefinition
    try:
        org_def = OrgDefinition.model_validate(data)
    except Exception as e:
        error_console.print(f"[bold red]Org definition error:[/bold red] {e}")
        sys.exit(1)

    valid, errors = org_def.validate_org()
    if not valid:
        error_console.print(
            "[bold red]Org validation failed:[/bold red]\n" + "\n".join(f"  - {e}" for e in errors)
        )
        sys.exit(1)

    # Convert OrgDefinition to PactConfig for bootstrapping
    authority_id = org_def.authority_id or f"{org_def.org_id}.authority"
    platform_config = PactConfig(
        name=org_def.name,
        genesis=GenesisConfig(
            authority=authority_id,
            authority_name=org_def.name,
        ),
        constraint_envelopes=list(org_def.envelopes),
        agents=list(org_def.agents),
        teams=list(org_def.teams),
        workspaces=list(org_def.workspaces),
    )

    # Bootstrap into a MemoryStore (for CLI deployment demonstration)
    store = MemoryStore()
    bootstrap = PlatformBootstrap(store=store)

    try:
        result = bootstrap.initialize(platform_config, discover_workspaces=False)
    except Exception as e:
        error_console.print(f"[bold red]Deploy failed:[/bold red] {e}")
        sys.exit(1)

    if result.is_successful:
        console.print()
        console.print(
            Panel(
                f"[bold green]Deployed[/bold green] organization '{org_def.name}' successfully\n\n"
                f"  Genesis Authority: {result.genesis_authority}\n"
                f"  Agents Registered: {result.agents_registered}\n"
                f"  Teams Registered: {result.teams_registered}\n"
                f"  Envelopes Created: {result.envelopes_created}\n"
                f"  Delegations Created: {result.delegations_created}\n"
                f"  Workspaces: {result.workspaces_registered}",
                title="PACT - Org Deployed",
                border_style="green",
            )
        )
    else:
        error_console.print(
            Panel(
                "[bold red]Deploy completed with errors:[/bold red]\n"
                + "\n".join(f"  - {e}" for e in result.errors),
                title="PACT - Deploy Errors",
                border_style="red",
            )
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Task 5045: org status — show runtime org health
# ---------------------------------------------------------------------------


@org.command("status")
def org_status() -> None:
    """Show runtime organization health: teams, agents, and status breakdown."""
    # In the CLI context without a persistent runtime, show a summary panel.
    # When a store is available, this would query the actual trust store.
    console.print()
    console.print(
        Panel(
            "[dim]No organization deployed in current session.[/dim]\n\n"
            "Deploy an organization to see runtime health:\n"
            "  [cyan]pact org deploy --file org.yaml[/cyan]\n\n"
            "Or create one from a template:\n"
            "  [cyan]pact org create --template minimal --name 'My Org'[/cyan]",
            title="PACT - Organization Status",
            border_style="blue",
        )
    )

    # Show a summary table even when empty
    table = Table(title="Organization Health", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value")

    table.add_row("Teams", "0")
    table.add_row("Agents (Total)", "0")
    table.add_row("Agents (Active)", "0")
    table.add_row("Agents (Suspended)", "0")
    table.add_row("Pending Approvals", "0")

    console.print(table)


# ---------------------------------------------------------------------------
# Task 6034: org generate — auto-generate an organization from a config
# ---------------------------------------------------------------------------


@org.command("generate")
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=False),
    help="Path to YAML OrgGeneratorConfig file",
)
@click.option(
    "--output",
    "output_file",
    required=False,
    type=click.Path(),
    default=None,
    help="Output file path for the generated OrgDefinition (YAML format)",
)
@click.option(
    "--validate-only",
    is_flag=True,
    default=False,
    help="Generate and validate, but do not produce output",
)
def org_generate(input_file: str, output_file: str | None, validate_only: bool) -> None:
    """Auto-generate a CARE-governed organization from a high-level config.

    Reads an OrgGeneratorConfig from a YAML file, runs the auto-generation
    engine, and outputs the resulting OrgDefinition as YAML.

    The generated organization is guaranteed to pass validate_org_detailed()
    with zero ERRORs.
    """
    from pact_platform.build.org.generator import OrgGenerator, OrgGeneratorConfig

    # Load the input file
    input_path = Path(input_file)
    if not input_path.exists():
        error_console.print(f"[bold red]File not found:[/bold red] {input_file}")
        sys.exit(1)

    try:
        raw_text = input_path.read_text()
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        error_console.print(f"[bold red]YAML parse error:[/bold red] {e}")
        sys.exit(1)
    except OSError as e:
        error_console.print(f"[bold red]File read error:[/bold red] {e}")
        sys.exit(1)

    if not isinstance(data, dict):
        error_console.print(
            f"[bold red]Invalid format:[/bold red] Expected a YAML mapping, "
            f"got {type(data).__name__}"
        )
        sys.exit(1)

    # Parse into OrgGeneratorConfig
    try:
        config = OrgGeneratorConfig.model_validate(data)
    except Exception as e:
        error_console.print(f"[bold red]Config validation error:[/bold red] {e}")
        sys.exit(1)

    # Generate the organization
    try:
        generator = OrgGenerator()
        org_def = generator.generate(config)
    except ValueError as e:
        error_console.print(f"[bold red]Generation failed:[/bold red] {e}")
        sys.exit(1)

    if validate_only:
        console.print()
        console.print(
            Panel(
                f"[bold green]Valid[/bold green] organization generated from {input_file}\n\n"
                f"  Organization ID: {org_def.org_id}\n"
                f"  Name: {org_def.name}\n"
                f"  Departments: {len(org_def.departments)}\n"
                f"  Teams: {len(org_def.teams)}\n"
                f"  Agents: {len(org_def.agents)}\n"
                f"  Envelopes: {len(org_def.envelopes)}",
                title="PACT - Org Generate (Validate Only)",
                border_style="green",
            )
        )
        return

    # Output the generated OrgDefinition
    org_data = org_def.model_dump(mode="json")

    if output_file:
        output_path = Path(output_file)
        with output_path.open("w") as f:
            yaml.dump(org_data, f, default_flow_style=False, sort_keys=False)

        console.print()
        console.print(
            Panel(
                f"[bold green]Generated[/bold green] organization '{org_def.name}' "
                f"to {output_file}\n\n"
                f"  Organization ID: {org_def.org_id}\n"
                f"  Departments: {len(org_def.departments)}\n"
                f"  Teams: {len(org_def.teams)}\n"
                f"  Agents: {len(org_def.agents)}\n"
                f"  Envelopes: {len(org_def.envelopes)}\n"
                f"  Workspaces: {len(org_def.workspaces)}",
                title="PACT - Org Generated",
                border_style="green",
            )
        )
    else:
        # Print to stdout
        yaml.dump(org_data, sys.stdout, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    main()
