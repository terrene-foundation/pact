# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""PACT admin CLI — unified command-line interface for governed AI operations.

Wraps the existing build CLI (validate, status, org sub-commands) and adds
governance operations (quickstart, role, clearance, bridge, envelope, agent,
audit) powered by the ``pact.governance`` engine.

Usage:
    pact --help
    pact quickstart --example university
    pact org create <yaml-file>
    pact org list
    pact role assign <address> <user>
    pact clearance grant <address> <level>
    pact bridge create <role_a> <role_b>
    pact envelope show <address>
    pact agent register <id> <role>
    pact audit export [--format json|csv]
    pact validate <config-file>
    pact status
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from pact import __version__

logger = logging.getLogger(__name__)

console = Console()
error_console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Module-level governance engine singleton — populated by commands that need it
# ---------------------------------------------------------------------------

_engine: Any = None
_agent_mapping: Any = None


def _get_engine() -> Any:
    """Return the module-level GovernanceEngine, or None if not initialized."""
    return _engine


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=__version__, prog_name="pact")
def main() -> None:
    """PACT — Governed operational model for AI agent organizations."""
    from pact_platform.build.config.env import _load_dotenv

    _load_dotenv()


# ---------------------------------------------------------------------------
# quickstart
# ---------------------------------------------------------------------------

_EXAMPLE_CHOICES = ["university"]


@main.command()
@click.option(
    "--example",
    type=click.Choice(_EXAMPLE_CHOICES, case_sensitive=False),
    required=True,
    help="Example org to load (e.g. 'university').",
)
@click.option(
    "--serve/--no-serve",
    default=True,
    help="Start the FastAPI server after loading the example org.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to bind the API server.",
)
@click.option(
    "--port",
    default=8000,
    show_default=True,
    type=int,
    help="Port to bind the API server.",
)
def quickstart(example: str, serve: bool, host: str, port: int) -> None:
    """Load an example org, compile it, and optionally start the API server.

    Example:
        pact quickstart --example university
    """
    global _engine, _agent_mapping

    from pact.governance import (
        AgentRoleMapping,
        GovernanceEngine,
    )

    if example == "university":
        from pact_platform.examples.university.org import create_university_org
        from pact_platform.examples.university.clearance import create_university_clearances
        from pact_platform.examples.university.envelopes import create_university_envelopes

        console.print()
        console.print(
            Panel(
                "[bold cyan]PACT Quickstart[/bold cyan] — University Example",
                border_style="cyan",
            )
        )

        # --- Compile the org ---
        with console.status("[bold green]Compiling university org..."):
            compiled, org_def = create_university_org()
            engine = GovernanceEngine(org_def)
            org = engine.get_org()

        console.print(f"  [green]Compiled[/green] {len(org.nodes)} nodes")

        # --- Apply clearances ---
        with console.status("[bold green]Applying clearances..."):
            clearances = create_university_clearances(compiled)
            for addr, clr in clearances.items():
                engine.grant_clearance(addr, clr)

        console.print(f"  [green]Granted[/green] {len(clearances)} clearances")

        # --- Apply envelopes ---
        with console.status("[bold green]Applying envelopes..."):
            envelopes = create_university_envelopes(compiled)
            for env in envelopes:
                engine.set_role_envelope(env)

        console.print(f"  [green]Set[/green] {len(envelopes)} role envelopes")

        # Store engine globally
        _engine = engine
        _agent_mapping = AgentRoleMapping()
        _agent_mapping.from_org(compiled)

        # --- Org tree ---
        _print_org_tree(org)

        console.print()
        console.print(
            Panel(
                f"[bold green]Ready[/bold green] — University org loaded with "
                f"{len(org.nodes)} nodes, {len(clearances)} clearances, "
                f"{len(envelopes)} envelopes.\n\n"
                f"Try governance commands:\n"
                f"  [cyan]pact envelope show D1-R1-D1-R1-D1-R1-T1-R1[/cyan]\n"
                f"  [cyan]pact clearance grant D1-R1-D1-R1-D1-R1-T1-R1 confidential[/cyan]\n"
                f"  [cyan]pact agent register agent-cs-001 D1-R1-D1-R1-D1-R1-T1-R1[/cyan]",
                title="PACT Quickstart",
                border_style="green",
            )
        )

        if serve:
            _start_server(host, port)
    else:
        error_console.print(
            f"[bold red]Unknown example:[/bold red] '{example}'. "
            f"Available: {', '.join(_EXAMPLE_CHOICES)}"
        )
        sys.exit(1)


def _print_org_tree(org: Any) -> None:
    """Print a Rich tree of the compiled org structure."""
    tree = Tree("[bold]Organization[/bold]")
    # Find root nodes (addresses with a single segment pair like D1-R1)
    root_addresses = sorted(addr for addr in org.nodes if addr.count("-") == 1)
    if not root_addresses:
        # Fallback: show all nodes sorted
        root_addresses = sorted(org.nodes.keys())

    # Build child map: parent_addr -> [child_addr]
    all_addrs = sorted(org.nodes.keys(), key=lambda a: (len(a), a))
    children_of: dict[str, list[str]] = {}
    for addr in all_addrs:
        # Find the longest prefix that is also a valid address
        parts = addr.rsplit("-", 2)
        if len(parts) >= 3:
            parent_candidate = addr[: addr.rfind("-", 0, addr.rfind("-"))]
            # Walk back to find the actual parent
            while parent_candidate and parent_candidate not in org.nodes:
                idx = parent_candidate.rfind("-")
                if idx == -1:
                    parent_candidate = ""
                    break
                parent_candidate = parent_candidate[:idx]
            if parent_candidate and parent_candidate != addr:
                children_of.setdefault(parent_candidate, []).append(addr)
                continue
        # It's a root
        if addr not in root_addresses:
            root_addresses.append(addr)

    def _add_subtree(parent_tree: Tree, address: str) -> None:
        node = org.nodes[address]
        node_type = getattr(node, "node_type", None)
        role_name = getattr(node, "name", address)
        label = f"[dim]{address}[/dim] — {role_name}"
        if node_type:
            label += (
                f" [dim]({node_type.value if hasattr(node_type, 'value') else node_type})[/dim]"
            )
        branch = parent_tree.add(label)
        for child in sorted(children_of.get(address, [])):
            _add_subtree(branch, child)

    # Deduplicate
    seen: set[str] = set()
    for root in root_addresses:
        if root not in seen:
            seen.add(root)
            _add_subtree(tree, root)

    console.print()
    console.print(tree)


def _start_server(host: str, port: int) -> None:
    """Start the FastAPI server via uvicorn."""
    console.print()
    console.print(
        f"[bold cyan]Starting API server[/bold cyan] on "
        f"[link=http://{host}:{port}]http://{host}:{port}[/link] ..."
    )
    console.print("  Press Ctrl+C to stop.\n")
    try:
        import uvicorn

        uvicorn.run(
            "pact_platform.use.api.server:create_app",
            host=host,
            port=port,
            factory=True,
            log_level="info",
        )
    except ImportError:
        error_console.print(
            "[bold red]uvicorn not installed.[/bold red] "
            "Install with: pip install uvicorn\n"
            "Skipping server start. The org is loaded and governance commands "
            "are available."
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped.[/dim]")


# ---------------------------------------------------------------------------
# org group — wraps existing build CLI commands + new governance commands
# ---------------------------------------------------------------------------


@main.group()
def org() -> None:
    """Organization management — create, list, validate, and deploy orgs."""


@org.command("create")
@click.argument("yaml_file", type=click.Path(exists=True))
def org_create(yaml_file: str) -> None:
    """Load and compile an organization from a YAML file.

    The YAML file should follow the PACT org schema (org_id, name,
    departments, teams, roles, clearances, envelopes, bridges, ksps).
    """
    global _engine, _agent_mapping

    from pact.governance import (
        AgentRoleMapping,
        GovernanceEngine,
        load_org_yaml,
    )

    console.print()
    with console.status(f"[bold green]Loading org from {yaml_file}..."):
        loaded = load_org_yaml(yaml_file)
        engine = GovernanceEngine(loaded.org_definition)
        org = engine.get_org()

    console.print(f"  [green]Compiled[/green] {len(org.nodes)} nodes")

    # Apply governance specs from the YAML
    applied_clearances = 0
    applied_envelopes = 0
    applied_bridges = 0
    applied_ksps = 0

    # Clearances
    for spec in loaded.clearances:
        from pact.governance import RoleClearance
        from pact_platform.build.config.schema import ConfidentialityLevel

        compiled = engine.get_org()
        # Resolve role_id to address
        node = compiled.get_node_by_role_id(spec.role_id)
        if node is None:
            error_console.print(
                f"  [yellow]Warning:[/yellow] Role '{spec.role_id}' "
                f"not found in compiled org, skipping clearance."
            )
            continue
        address = node.address
        clr = RoleClearance(
            role_address=address,
            max_clearance=ConfidentialityLevel(spec.level),
            compartments=frozenset(spec.compartments),
            nda_signed=spec.nda_signed,
        )
        engine.grant_clearance(address, clr)
        applied_clearances += 1

    # Envelopes
    for spec in loaded.envelopes:
        from pact.governance import RoleEnvelope
        from pact_platform.build.config.schema import (
            ConstraintEnvelopeConfig,
            FinancialConstraintConfig,
            OperationalConstraintConfig,
            TemporalConstraintConfig,
            DataAccessConstraintConfig,
            CommunicationConstraintConfig,
        )

        compiled = engine.get_org()
        # Resolve target and defined_by to addresses
        target_node = compiled.get_node_by_role_id(spec.target)
        definer_node = compiled.get_node_by_role_id(spec.defined_by)
        if target_node is None or definer_node is None:
            error_console.print(
                f"  [yellow]Warning:[/yellow] Could not resolve envelope "
                f"target='{spec.target}' or defined_by='{spec.defined_by}', skipping."
            )
            continue

        env_config = ConstraintEnvelopeConfig(
            id=f"env-{spec.target}",
            financial=FinancialConstraintConfig(**(spec.financial or {})),
            operational=OperationalConstraintConfig(**(spec.operational or {})),
            temporal=TemporalConstraintConfig(**(spec.temporal or {})),
            data_access=DataAccessConstraintConfig(**(spec.data_access or {})),
            communication=CommunicationConstraintConfig(**(spec.communication or {})),
        )
        role_env = RoleEnvelope(
            id=f"env-{spec.target}",
            defining_role_address=definer_node.address,
            target_role_address=target_node.address,
            envelope=env_config,
        )
        engine.set_role_envelope(role_env)
        applied_envelopes += 1

    # Bridges
    for spec in loaded.bridges:
        from pact.governance import PactBridge

        compiled = engine.get_org()
        role_a_node = compiled.get_node_by_role_id(spec.role_a)
        role_b_node = compiled.get_node_by_role_id(spec.role_b)
        if role_a_node is None or role_b_node is None:
            error_console.print(
                f"  [yellow]Warning:[/yellow] Could not resolve bridge "
                f"role_a='{spec.role_a}' or role_b='{spec.role_b}', skipping."
            )
            continue

        from pact_platform.build.config.schema import ConfidentialityLevel

        bridge = PactBridge(
            id=spec.id,
            role_a_address=role_a_node.address,
            role_b_address=role_b_node.address,
            bridge_type=spec.bridge_type,
            max_classification=ConfidentialityLevel(spec.max_classification),
            bilateral=spec.bilateral,
        )
        engine.create_bridge(bridge)
        applied_bridges += 1

    # KSPs
    for spec in loaded.ksps:
        from pact.governance import KnowledgeSharePolicy

        compiled = engine.get_org()
        # KSP source/target are unit addresses (dept/team IDs)
        ksp = KnowledgeSharePolicy(
            id=spec.id,
            source_unit_address=spec.source,
            target_unit_address=spec.target,
            max_classification=ConfidentialityLevel(spec.max_classification),
        )
        engine.create_ksp(ksp)
        applied_ksps += 1

    _engine = engine
    _agent_mapping = AgentRoleMapping()
    _agent_mapping.from_org(engine.get_org())

    console.print(f"  [green]Clearances:[/green] {applied_clearances}")
    console.print(f"  [green]Envelopes:[/green] {applied_envelopes}")
    console.print(f"  [green]Bridges:[/green] {applied_bridges}")
    console.print(f"  [green]KSPs:[/green] {applied_ksps}")

    console.print()
    console.print(
        Panel(
            f"[bold green]Loaded[/bold green] organization "
            f"'{loaded.org_definition.name}' from {yaml_file}\n\n"
            f"  Nodes: {len(org.nodes)}\n"
            f"  Clearances: {applied_clearances}\n"
            f"  Envelopes: {applied_envelopes}\n"
            f"  Bridges: {applied_bridges}\n"
            f"  KSPs: {applied_ksps}\n\n"
            f"State persisted when DataFlow storage is wired in M4.",
            title="PACT — Org Created",
            border_style="green",
        )
    )


@org.command("list")
def org_list() -> None:
    """List compiled organizations.

    Currently displays the in-memory org (if loaded). Persistent org store
    will be available when DataFlow integration is wired in M4.
    """
    engine = _get_engine()

    if engine is None:
        console.print()
        console.print(
            Panel(
                "[dim]No organizations loaded in this session.[/dim]\n\n"
                "Load an org to get started:\n"
                "  [cyan]pact quickstart --example university[/cyan]\n"
                "  [cyan]pact org create org.yaml[/cyan]\n\n"
                "[dim]Persistent org store available when DataFlow is wired in M4.[/dim]",
                title="PACT — Organizations",
                border_style="blue",
            )
        )
        return

    org = engine.get_org()
    table = Table(
        title="Loaded Organizations",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Org ID", style="bold")
    table.add_column("Name")
    table.add_column("Nodes")
    table.add_column("Root Roles")

    root_roles = sorted(org.root_roles) if hasattr(org, "root_roles") else []
    table.add_row(
        getattr(org, "org_id", "in-memory"),
        engine.org_name,
        str(len(org.nodes)),
        str(len(root_roles)),
    )

    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# Re-export existing build CLI commands into the org group
# ---------------------------------------------------------------------------

# Import the existing build CLI commands and add them
from pact_platform.build.cli import (
    org_validate,
    org_export,
    org_import_file,
    org_diff,
    org_deploy,
    org_status,
    org_list_templates,
    org_generate,
)

org.add_command(org_validate, "validate")
org.add_command(org_export, "export")
org.add_command(org_import_file, "import-file")
org.add_command(org_diff, "diff")
org.add_command(org_deploy, "deploy")
org.add_command(org_status, "status")
org.add_command(org_list_templates, "list-templates")
org.add_command(org_generate, "generate")


# ---------------------------------------------------------------------------
# role group
# ---------------------------------------------------------------------------


@main.group()
def role() -> None:
    """Role management — assign users or agents to D/T/R addresses."""


@role.command("assign")
@click.argument("address")
@click.argument("user")
def role_assign(address: str, user: str) -> None:
    """Assign a user or agent to a role at the given D/T/R address.

    ADDRESS is a D/T/R positional address (e.g. D1-R1-D1-R1-D1-R1-T1-R1).
    USER is a user ID or agent ID to assign to the role.
    """
    from pact.governance import Address

    # Validate address format
    try:
        Address.parse(address)
    except Exception as exc:
        error_console.print(
            f"[bold red]Invalid address:[/bold red] {address}\n"
            f"  {exc}\n\n"
            f"Addresses follow D/T/R grammar. Example: D1-R1-D1-R1-T1-R1"
        )
        sys.exit(1)

    console.print()
    console.print(
        Panel(
            f"[bold green]Assigned[/bold green] user '{user}' to role at "
            f"address [cyan]{address}[/cyan].\n\n"
            f"Configured. State persisted when DataFlow storage is wired in M4.",
            title="PACT — Role Assignment",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# clearance group
# ---------------------------------------------------------------------------

_CLEARANCE_LEVELS = ["public", "restricted", "confidential", "secret", "top_secret"]


@main.group()
def clearance() -> None:
    """Knowledge clearance management — grant or revoke clearance levels."""


@clearance.command("grant")
@click.argument("address")
@click.argument("level", type=click.Choice(_CLEARANCE_LEVELS, case_sensitive=False))
@click.option(
    "--compartment",
    "-c",
    multiple=True,
    help="Compartment(s) to grant access to. Can be specified multiple times.",
)
@click.option("--nda", is_flag=True, default=False, help="Mark NDA as signed.")
def clearance_grant(
    address: str,
    level: str,
    compartment: tuple[str, ...],
    nda: bool,
) -> None:
    """Grant a clearance level to the role at ADDRESS.

    ADDRESS is a D/T/R positional address.
    LEVEL is one of: public, restricted, confidential, secret, top_secret.
    """
    from pact.governance import Address

    # Validate address format
    try:
        Address.parse(address)
    except Exception as exc:
        error_console.print(f"[bold red]Invalid address:[/bold red] {address}\n  {exc}")
        sys.exit(1)

    engine = _get_engine()
    if engine is not None:
        from pact.governance import RoleClearance
        from pact_platform.build.config.schema import ConfidentialityLevel

        clr = RoleClearance(
            role_address=address,
            max_clearance=ConfidentialityLevel(level),
            compartments=frozenset(compartment),
            nda_signed=nda,
        )
        try:
            engine.grant_clearance(address, clr)
        except Exception as exc:
            error_console.print(f"[bold red]Failed to grant clearance:[/bold red] {exc}")
            sys.exit(1)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")
    table.add_row("Address", address)
    table.add_row("Level", level.upper())
    table.add_row("Compartments", ", ".join(compartment) if compartment else "(none)")
    table.add_row("NDA Signed", "Yes" if nda else "No")

    console.print()
    console.print(
        Panel(
            f"[bold green]Granted[/bold green] clearance "
            f"[bold]{level.upper()}[/bold] to [cyan]{address}[/cyan].",
            title="PACT — Clearance Grant",
            border_style="green",
        )
    )
    console.print(table)

    if engine is None:
        console.print("\n  [dim]No engine loaded. Load an org first for live governance.[/dim]")
    else:
        console.print("\n  Configured. State persisted when DataFlow storage is wired in M4.")


# ---------------------------------------------------------------------------
# bridge group
# ---------------------------------------------------------------------------


@main.group()
def bridge() -> None:
    """Cross-functional bridge management — create governed bridges between roles."""


@bridge.command("create")
@click.argument("role_a")
@click.argument("role_b")
@click.option(
    "--type",
    "bridge_type",
    default="bilateral",
    show_default=True,
    type=click.Choice(["bilateral", "unilateral"], case_sensitive=False),
    help="Bridge type: bilateral (both directions) or unilateral (A -> B only).",
)
@click.option(
    "--max-classification",
    default="restricted",
    show_default=True,
    type=click.Choice(_CLEARANCE_LEVELS, case_sensitive=False),
    help="Maximum classification level for information shared via this bridge.",
)
def bridge_create(
    role_a: str,
    role_b: str,
    bridge_type: str,
    max_classification: str,
) -> None:
    """Create a cross-functional bridge between ROLE_A and ROLE_B.

    ROLE_A and ROLE_B are D/T/R positional addresses.
    """
    from pact.governance import Address

    for addr_name, addr in [("ROLE_A", role_a), ("ROLE_B", role_b)]:
        try:
            Address.parse(addr)
        except Exception as exc:
            error_console.print(
                f"[bold red]Invalid {addr_name} address:[/bold red] {addr}\n  {exc}"
            )
            sys.exit(1)

    is_bilateral = bridge_type.lower() == "bilateral"

    engine = _get_engine()
    if engine is not None:
        from pact.governance import PactBridge
        from pact_platform.build.config.schema import ConfidentialityLevel

        bridge_obj = PactBridge(
            id=f"bridge-{role_a}-{role_b}",
            role_a_address=role_a,
            role_b_address=role_b,
            bridge_type=bridge_type,
            max_classification=ConfidentialityLevel(max_classification),
            bilateral=is_bilateral,
        )
        try:
            engine.create_bridge(bridge_obj)
        except Exception as exc:
            error_console.print(f"[bold red]Failed to create bridge:[/bold red] {exc}")
            sys.exit(1)

    direction = "A <-> B" if is_bilateral else "A -> B"

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")
    table.add_row("Role A", role_a)
    table.add_row("Role B", role_b)
    table.add_row("Direction", direction)
    table.add_row("Type", bridge_type)
    table.add_row("Max Classification", max_classification.upper())

    console.print()
    console.print(
        Panel(
            f"[bold green]Created[/bold green] bridge between "
            f"[cyan]{role_a}[/cyan] and [cyan]{role_b}[/cyan] "
            f"({direction}).",
            title="PACT — Bridge Created",
            border_style="green",
        )
    )
    console.print(table)

    if engine is None:
        console.print("\n  [dim]No engine loaded. Load an org first for live governance.[/dim]")
    else:
        console.print("\n  Configured. State persisted when DataFlow storage is wired in M4.")


# ---------------------------------------------------------------------------
# envelope group
# ---------------------------------------------------------------------------


@main.group()
def envelope() -> None:
    """Operating envelope management — view and inspect constraint envelopes."""


@envelope.command("show")
@click.argument("address")
def envelope_show(address: str) -> None:
    """Show the effective operating envelope for the role at ADDRESS.

    Displays all five constraint dimensions: Financial, Operational,
    Temporal, Data Access, and Communication.
    """
    from pact.governance import Address

    try:
        Address.parse(address)
    except Exception as exc:
        error_console.print(f"[bold red]Invalid address:[/bold red] {address}\n  {exc}")
        sys.exit(1)

    engine = _get_engine()
    if engine is None:
        error_console.print(
            "[bold red]No org loaded.[/bold red] "
            "Load an org first:\n"
            "  [cyan]pact quickstart --example university[/cyan]\n"
            "  [cyan]pact org create org.yaml[/cyan]"
        )
        sys.exit(1)

    envelope_config = engine.compute_envelope(address)
    if envelope_config is None:
        console.print()
        console.print(
            Panel(
                f"[dim]No envelope configured for[/dim] [cyan]{address}[/cyan].\n\n"
                f"The role at this address operates under default (maximally "
                f"restrictive) constraints.\n\n"
                f"Set an envelope with the governance engine or YAML config.",
                title="PACT — Envelope",
                border_style="yellow",
            )
        )
        return

    # --- Build a comprehensive table ---
    console.print()
    console.print(
        Panel(
            f"Effective envelope for [bold cyan]{address}[/bold cyan]",
            title="PACT — Operating Envelope",
            border_style="blue",
        )
    )

    # Financial
    fin = envelope_config.financial
    fin_table = Table(
        title="Financial Constraints",
        show_header=True,
        header_style="bold cyan",
    )
    fin_table.add_column("Constraint", style="dim")
    fin_table.add_column("Value")
    if fin is not None:
        fin_table.add_row(
            "Max Spend (USD)",
            f"${fin.max_spend_usd:,.2f}" if fin.max_spend_usd is not None else "unlimited",
        )
        fin_table.add_row(
            "Requires Approval Above (USD)",
            (
                f"${fin.requires_approval_above_usd:,.2f}"
                if fin.requires_approval_above_usd
                else "N/A"
            ),
        )
        api_budget = getattr(fin, "api_cost_budget_usd", None)
        fin_table.add_row(
            "API Cost Budget (USD)",
            f"${api_budget:,.2f}" if api_budget else "N/A",
        )
    else:
        fin_table.add_row("(no financial capability)", "—")
    console.print(fin_table)

    # Operational
    ops = envelope_config.operational
    ops_table = Table(
        title="Operational Constraints",
        show_header=True,
        header_style="bold cyan",
    )
    ops_table.add_column("Constraint", style="dim")
    ops_table.add_column("Value")
    ops_table.add_row(
        "Allowed Actions", ", ".join(ops.allowed_actions) if ops.allowed_actions else "(none)"
    )
    ops_table.add_row(
        "Blocked Actions", ", ".join(ops.blocked_actions) if ops.blocked_actions else "(none)"
    )
    max_day = getattr(ops, "max_actions_per_day", None)
    max_hour = getattr(ops, "max_actions_per_hour", None)
    ops_table.add_row("Max Actions/Day", str(max_day) if max_day else "unlimited")
    ops_table.add_row("Max Actions/Hour", str(max_hour) if max_hour else "unlimited")
    console.print(ops_table)

    # Temporal
    temp = envelope_config.temporal
    temp_table = Table(
        title="Temporal Constraints",
        show_header=True,
        header_style="bold cyan",
    )
    temp_table.add_column("Constraint", style="dim")
    temp_table.add_column("Value")
    start = getattr(temp, "active_hours_start", None)
    end = getattr(temp, "active_hours_end", None)
    tz = getattr(temp, "timezone", "UTC")
    temp_table.add_row("Active Hours", f"{start} – {end} ({tz})" if start and end else "24/7")
    blackout = getattr(temp, "blackout_periods", [])
    temp_table.add_row("Blackout Periods", str(len(blackout)) if blackout else "none")
    console.print(temp_table)

    # Data Access
    da = envelope_config.data_access
    da_table = Table(
        title="Data Access Constraints",
        show_header=True,
        header_style="bold cyan",
    )
    da_table.add_column("Constraint", style="dim")
    da_table.add_column("Value")
    read_paths = getattr(da, "read_paths", [])
    write_paths = getattr(da, "write_paths", [])
    blocked_types = getattr(da, "blocked_data_types", [])
    da_table.add_row("Read Paths", ", ".join(read_paths) if read_paths else "(all)")
    da_table.add_row("Write Paths", ", ".join(write_paths) if write_paths else "(all)")
    da_table.add_row("Blocked Data Types", ", ".join(blocked_types) if blocked_types else "(none)")
    console.print(da_table)

    # Communication
    comm = envelope_config.communication
    comm_table = Table(
        title="Communication Constraints",
        show_header=True,
        header_style="bold cyan",
    )
    comm_table.add_column("Constraint", style="dim")
    comm_table.add_column("Value")
    internal_only = getattr(comm, "internal_only", True)
    allowed_channels = getattr(comm, "allowed_channels", [])
    ext_approval = getattr(comm, "external_requires_approval", True)
    comm_table.add_row("Internal Only", "Yes" if internal_only else "No")
    comm_table.add_row(
        "Allowed Channels", ", ".join(allowed_channels) if allowed_channels else "(all)"
    )
    comm_table.add_row("External Requires Approval", "Yes" if ext_approval else "No")
    console.print(comm_table)


# ---------------------------------------------------------------------------
# agent group
# ---------------------------------------------------------------------------


@main.group()
def agent() -> None:
    """Agent management — register and inspect AI agents bound to roles."""


@agent.command("register")
@click.argument("agent_id")
@click.argument("role_address")
def agent_register(agent_id: str, role_address: str) -> None:
    """Register an agent with the given ID at ROLE_ADDRESS.

    AGENT_ID is a unique identifier for the agent (e.g. 'agent-cs-001').
    ROLE_ADDRESS is the D/T/R address the agent will operate under.
    """
    from pact.governance import Address, AgentRoleMapping

    try:
        Address.parse(role_address)
    except Exception as exc:
        error_console.print(f"[bold red]Invalid address:[/bold red] {role_address}\n  {exc}")
        sys.exit(1)

    global _agent_mapping
    if _agent_mapping is None:
        _agent_mapping = AgentRoleMapping()

    try:
        _agent_mapping.register(agent_id, role_address)
    except Exception as exc:
        error_console.print(f"[bold red]Registration failed:[/bold red] {exc}")
        sys.exit(1)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")
    table.add_row("Agent ID", agent_id)
    table.add_row("Role Address", role_address)

    engine = _get_engine()
    if engine is not None:
        node = engine.get_node(role_address)
        if node is not None:
            table.add_row("Role Name", getattr(node, "name", "—"))

    console.print()
    console.print(
        Panel(
            f"[bold green]Registered[/bold green] agent "
            f"[bold]{agent_id}[/bold] at [cyan]{role_address}[/cyan].\n\n"
            f"Configured. State persisted when DataFlow storage is wired in M4.",
            title="PACT — Agent Registered",
            border_style="green",
        )
    )
    console.print(table)


# ---------------------------------------------------------------------------
# audit group
# ---------------------------------------------------------------------------


@main.group()
def audit() -> None:
    """Audit trail management — export and inspect the EATP audit chain."""


@audit.command("export")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "csv"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Output format for the audit trail.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file path. Defaults to stdout.",
)
def audit_export(output_format: str, output: str | None) -> None:
    """Export the audit trail as JSON or CSV.

    When an org is loaded, exports the EATP audit chain. Otherwise,
    shows an empty audit trail.
    """
    engine = _get_engine()
    audit_chain = engine.audit_chain if engine is not None else None

    records: list[dict[str, Any]] = []

    if audit_chain is not None:
        # Extract records from the audit chain
        anchors = getattr(audit_chain, "anchors", None)
        if anchors is not None:
            for anchor in anchors:
                record = anchor.to_dict() if hasattr(anchor, "to_dict") else {"anchor": str(anchor)}
                records.append(record)
        else:
            # Try to get all records via iteration or list-like access
            chain_records = getattr(audit_chain, "records", None)
            if chain_records is not None:
                for rec in chain_records:
                    record = rec.to_dict() if hasattr(rec, "to_dict") else {"record": str(rec)}
                    records.append(record)

    if not records:
        # Generate a summary record showing what governance state exists
        if engine is not None:
            org = engine.get_org()
            records.append(
                {
                    "type": "governance_snapshot",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "org_name": engine.org_name,
                    "total_nodes": len(org.nodes),
                    "note": "Detailed audit anchors require EATP audit chain configuration.",
                }
            )

    if output_format == "json":
        content = json.dumps(records, indent=2, default=str)
    else:
        # CSV
        if records:
            all_keys: list[str] = []
            seen_keys: set[str] = set()
            for r in records:
                for k in r:
                    if k not in seen_keys:
                        all_keys.append(k)
                        seen_keys.add(k)
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=all_keys)
            writer.writeheader()
            for r in records:
                writer.writerow(r)
            content = buf.getvalue()
        else:
            content = "type,timestamp,note\n"

    if output:
        Path(output).write_text(content)
        console.print()
        console.print(
            Panel(
                f"[bold green]Exported[/bold green] {len(records)} audit record(s) "
                f"to [cyan]{output}[/cyan] ({output_format.upper()}).",
                title="PACT — Audit Export",
                border_style="green",
            )
        )
    else:
        click.echo(content)

    if engine is None:
        error_console.print("\n  [dim]No org loaded. Load an org for a full audit trail.[/dim]")


# ---------------------------------------------------------------------------
# validate — import from existing build CLI
# ---------------------------------------------------------------------------

from pact_platform.build.cli import validate as _build_validate

main.add_command(_build_validate, "validate")


# ---------------------------------------------------------------------------
# status — import from existing build CLI
# ---------------------------------------------------------------------------

from pact_platform.build.cli import status as _build_status

main.add_command(_build_status, "status")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
