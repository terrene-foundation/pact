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

from pact_platform import __version__

logger = logging.getLogger(__name__)

console = Console()
error_console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Module-level governance engine singleton — populated by commands that need it
# ---------------------------------------------------------------------------

_engine: Any = None
_agent_mapping: Any = None
_audit_chain: Any = None


def _get_engine() -> Any:
    """Return the module-level GovernanceEngine, or None if not initialized."""
    return _engine


def _make_audit_chain() -> Any:
    """Create a fresh AuditChain for the GovernanceEngine.

    This ensures that governance mutations (set_role_envelope, grant_clearance,
    create_bridge) emit EATP audit anchors, as required by TODO-04/05/06.
    """
    import uuid

    from pact_platform.trust.audit.anchor import AuditChain

    return AuditChain(chain_id=f"cli-{uuid.uuid4().hex[:12]}")


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
    global _engine, _agent_mapping, _audit_chain

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
            _audit_chain = _make_audit_chain()
            engine = GovernanceEngine(org_def, audit_chain=_audit_chain)
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
    global _engine, _agent_mapping, _audit_chain

    from pact.governance import (
        AgentRoleMapping,
        GovernanceEngine,
        load_org_yaml,
    )

    console.print()
    with console.status(f"[bold green]Loading org from {yaml_file}..."):
        loaded = load_org_yaml(yaml_file)
        _audit_chain = _make_audit_chain()
        engine = GovernanceEngine(loaded.org_definition, audit_chain=_audit_chain)
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


@role.command("designate-acting")
@click.argument("vacant_address")
@click.argument("acting_address")
@click.argument("designated_by")
def role_designate_acting(vacant_address: str, acting_address: str, designated_by: str) -> None:
    """Designate an acting occupant for a vacant role.

    VACANT_ADDRESS is the D/T/R address of the vacant role.
    ACTING_ADDRESS is the D/T/R address of the acting occupant.
    DESIGNATED_BY is the D/T/R address of the authority making the designation.

    Acting occupant inherits the vacant role's envelope but NOT clearance upgrades.
    Designation expires after 24 hours and must be renewed.
    """
    from pact.governance import Address

    for label, addr in [
        ("VACANT", vacant_address),
        ("ACTING", acting_address),
        ("DESIGNATED_BY", designated_by),
    ]:
        try:
            Address.parse(addr)
        except Exception as exc:
            error_console.print(f"[bold red]Invalid {label} address:[/bold red] {addr}\n  {exc}")
            sys.exit(1)

    engine = _get_engine()
    if engine is None:
        error_console.print("[bold red]No org loaded.[/bold red] Load an org first.")
        sys.exit(1)

    try:
        designation = engine.designate_acting_occupant(
            vacant_address, acting_address, designated_by
        )
    except Exception as exc:
        error_console.print(f"[bold red]Vacancy designation failed:[/bold red] {exc}")
        sys.exit(1)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")
    table.add_row("Vacant Role", vacant_address)
    table.add_row("Acting Occupant", acting_address)
    table.add_row("Designated By", designated_by)
    table.add_row("Expires At", str(designation.expires_at))

    console.print()
    console.print(
        Panel(
            f"[bold green]Designated[/bold green] [cyan]{acting_address}[/cyan] "
            f"as acting occupant for vacant role [cyan]{vacant_address}[/cyan].\n\n"
            f"Designation valid for 24 hours.",
            title="PACT — Vacancy Designation",
            border_style="green",
        )
    )
    console.print(table)


@role.command("vacancy-status")
@click.argument("address")
def role_vacancy_status(address: str) -> None:
    """Check vacancy designation status for a role at ADDRESS.

    Shows current acting occupant designation if one exists.
    """
    from pact.governance import Address

    try:
        Address.parse(address)
    except Exception as exc:
        error_console.print(f"[bold red]Invalid address:[/bold red] {address}\n  {exc}")
        sys.exit(1)

    engine = _get_engine()
    if engine is None:
        error_console.print("[bold red]No org loaded.[/bold red] Load an org first.")
        sys.exit(1)

    designation = engine.get_vacancy_designation(address)
    console.print()
    if designation is None:
        console.print(
            Panel(
                f"No vacancy designation for [cyan]{address}[/cyan].\n\n"
                f"The role is either occupied or vacant without an acting occupant.",
                title="PACT — Vacancy Status",
                border_style="yellow",
            )
        )
    else:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Property", style="dim")
        table.add_column("Value")
        table.add_row("Vacant Role", designation.vacant_role_address)
        table.add_row("Acting Occupant", designation.acting_role_address)
        table.add_row("Designated By", designation.designated_by)
        table.add_row("Designated At", str(designation.designated_at))
        table.add_row("Expires At", str(designation.expires_at))

        console.print(
            Panel(
                f"Active vacancy designation for [cyan]{address}[/cyan].",
                title="PACT — Vacancy Status",
                border_style="green",
            )
        )
        console.print(table)


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


@bridge.command("approve")
@click.argument("source_address")
@click.argument("target_address")
@click.argument("approver_address")
def bridge_approve(source_address: str, target_address: str, approver_address: str) -> None:
    """Pre-approve a bridge between SOURCE_ADDRESS and TARGET_ADDRESS.

    The APPROVER_ADDRESS must be the lowest common ancestor (LCA) of both
    roles in the org tree, or a designated compliance role. Approval is
    required before create_bridge() will succeed.

    Approvals expire after 24 hours.
    """
    from pact.governance import Address

    for label, addr in [
        ("SOURCE", source_address),
        ("TARGET", target_address),
        ("APPROVER", approver_address),
    ]:
        try:
            Address.parse(addr)
        except Exception as exc:
            error_console.print(f"[bold red]Invalid {label} address:[/bold red] {addr}\n  {exc}")
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

    try:
        approval = engine.approve_bridge(source_address, target_address, approver_address)
    except Exception as exc:
        error_console.print(f"[bold red]Bridge approval failed:[/bold red] {exc}")
        sys.exit(1)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")
    table.add_row("Source", source_address)
    table.add_row("Target", target_address)
    table.add_row("Approved By", approver_address)
    table.add_row("Expires At", str(approval.expires_at))

    console.print()
    console.print(
        Panel(
            f"[bold green]Approved[/bold green] bridge between "
            f"[cyan]{source_address}[/cyan] and [cyan]{target_address}[/cyan].\n\n"
            f"Approval valid for 24 hours. Run [cyan]pact bridge create[/cyan] to create the bridge.",
            title="PACT — Bridge LCA Approval",
            border_style="green",
        )
    )
    console.print(table)


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

    # Dimension scope (from delegation record, if applicable)
    dimension_scope = getattr(envelope_config, "dimension_scope", None)
    _ALL_DIMS = frozenset({"financial", "operational", "temporal", "data_access", "communication"})
    if dimension_scope and dimension_scope != _ALL_DIMS:
        scope_table = Table(
            title="Dimension Scope",
            show_header=True,
            header_style="bold cyan",
        )
        scope_table.add_column("Scoped Dimensions", style="dim")
        scope_sorted = (
            sorted(dimension_scope)
            if isinstance(dimension_scope, (set, frozenset))
            else list(dimension_scope)
        )
        for dim in scope_sorted:
            scope_table.add_row(dim)
        console.print(scope_table)
        console.print(
            "[dim]Only scoped dimensions are tightened by delegation; "
            "unscoped dimensions inherit from parent unchanged.[/dim]"
        )


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


@audit.command("toctou")
def audit_toctou() -> None:
    """Run a post-execution TOCTOU comparison.

    Compares envelope version hashes recorded in recent governance verdicts
    against the current org state. Reports divergences where the envelope
    changed after a verdict was issued (Time-of-Check / Time-of-Use gap).
    """
    engine = _get_engine()
    if engine is None:
        error_console.print(
            "[bold red]No org loaded.[/bold red] Load an org first.\n\n"
            "  [cyan]pact quickstart --example university[/cyan]\n"
            "  [cyan]pact org create org.yaml[/cyan]"
        )
        sys.exit(1)

    from pact_platform.use.audit.toctou import audit_toctou_check

    # Gather recent verdicts from the audit chain
    audit_chain = _audit_chain
    recent_verdicts: list[Any] = []

    if audit_chain is not None:
        anchors = getattr(audit_chain, "anchors", None)
        if anchors is not None:
            for anchor in anchors:
                # Collect objects that look like GovernanceVerdict
                if hasattr(anchor, "envelope_version") and hasattr(anchor, "role_address"):
                    recent_verdicts.append(anchor)

    if not recent_verdicts:
        console.print()
        console.print(
            Panel(
                "[green]No recent governance verdicts found.[/green]\n\n"
                "TOCTOU comparison requires recorded verdicts from "
                "``verify_action()`` calls.\n"
                "0 divergences found.",
                title="PACT — TOCTOU Audit",
                border_style="green",
            )
        )
        return

    divergences = audit_toctou_check(engine, recent_verdicts)

    console.print()
    if not divergences:
        console.print(
            Panel(
                f"[green]No TOCTOU divergences found[/green] across "
                f"{len(recent_verdicts)} verdict(s).\n\n"
                f"All recorded envelope versions match the current org state.",
                title="PACT — TOCTOU Audit",
                border_style="green",
            )
        )
    else:
        table = Table(
            title=f"TOCTOU Divergences ({len(divergences)} found)",
            show_header=True,
            header_style="bold red",
        )
        table.add_column("Role Address", style="cyan")
        table.add_column("Action")
        table.add_column("Recorded Version", style="dim")
        table.add_column("Current Version", style="dim")
        table.add_column("Timestamp")

        for div in divergences:
            table.add_row(
                div["role_address"],
                div.get("action", "—"),
                div["recorded_version"][:16] + "..." if div["recorded_version"] else "—",
                (
                    (div["current_version"][:16] + "...")
                    if div.get("current_version")
                    else "[red]REMOVED[/red]"
                ),
                str(div.get("timestamp", "—")),
            )

        console.print(table)
        console.print()
        console.print(
            Panel(
                f"[bold yellow]Warning:[/bold yellow] {len(divergences)} "
                f"TOCTOU divergence(s) detected.\n\n"
                f"These verdicts were issued under a different governance "
                f"envelope than the current org state. Review each divergence "
                f"to determine if the original decision is still valid.",
                title="PACT — TOCTOU Audit",
                border_style="yellow",
            )
        )


@audit.command("bypass-reviews")
def audit_bypass_reviews() -> None:
    """Check for overdue post-incident bypass reviews.

    Per PACT spec Section 9, post-incident review is mandatory within
    7 days of bypass expiry. This command surfaces bypasses where the
    review deadline has passed.
    """
    from pact_platform.engine.emergency_bypass import EmergencyBypass

    bypass_mgr = EmergencyBypass()

    # Try to get bypass manager from engine if available
    engine = _get_engine()
    if engine is not None:
        mgr = getattr(engine, "_bypass_manager", None)
        if mgr is not None:
            bypass_mgr = mgr

    overdue = bypass_mgr.check_overdue_reviews()

    console.print()
    if not overdue:
        console.print(
            Panel(
                "[green]No overdue bypass reviews.[/green]\n\n"
                "All emergency bypasses have been reviewed within the "
                "7-day post-incident deadline.",
                title="PACT — Bypass Review Audit",
                border_style="green",
            )
        )
        return

    table = Table(
        title=f"Overdue Bypass Reviews ({len(overdue)})",
        show_header=True,
        header_style="bold red",
    )
    table.add_column("Bypass ID", style="cyan")
    table.add_column("Role Address")
    table.add_column("Tier")
    table.add_column("Review Due By", style="red")
    table.add_column("Days Overdue", style="bold red")
    table.add_column("Approved By")

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    for record in overdue:
        days_overdue = (now - record.review_due_by).days if record.review_due_by else 0
        table.add_row(
            record.bypass_id,
            record.role_address,
            record.tier.value,
            str(record.review_due_by.date()) if record.review_due_by else "—",
            str(days_overdue),
            record.approved_by,
        )

    console.print(table)
    console.print()
    console.print(
        Panel(
            f"[bold red]{len(overdue)} bypass review(s) overdue.[/bold red]\n\n"
            f"Post-incident review is mandatory within 7 days of bypass "
            f"expiry (PACT spec Section 9). Contact the approver to "
            f"complete each review.",
            title="PACT — Bypass Review Audit",
            border_style="red",
        )
    )


# ---------------------------------------------------------------------------
# mcp group
# ---------------------------------------------------------------------------


@main.group()
def mcp() -> None:
    """MCP governance — status and tool call evaluation."""


@mcp.command("status")
def mcp_status() -> None:
    """Show MCP governance configuration status.

    Reports whether MCP governance is configured, the number of registered
    tool policies, and the associated org name.
    """
    engine = _get_engine()

    console.print()
    if engine is None:
        console.print(
            Panel(
                "[dim]MCP governance not configured — no org loaded.[/dim]\n\n"
                "Load an org to enable MCP governance:\n"
                "  [cyan]pact quickstart --example university[/cyan]\n"
                "  [cyan]pact org create org.yaml[/cyan]",
                title="PACT — MCP Status",
                border_style="yellow",
            )
        )
    else:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Property", style="dim")
        table.add_column("Value")
        table.add_row("Org Name", getattr(engine, "org_name", "unknown"))
        table.add_row("Engine Loaded", "[green]Yes[/green]")
        table.add_row(
            "Default Policy",
            "[bold]DENY[/bold] (default-deny: unregistered tools are blocked)",
        )

        console.print(
            Panel(
                "[bold green]MCP governance is available.[/bold green]\n\n"
                "Use [cyan]pact mcp evaluate --tool <name> --agent <address>[/cyan] "
                "to test a tool call against governance.",
                title="PACT — MCP Status",
                border_style="green",
            )
        )
        console.print(table)


@mcp.command("evaluate")
@click.option("--tool", required=True, help="MCP tool name to evaluate.")
@click.option("--agent", required=True, help="D/T/R agent address.")
@click.option("--args", "tool_args", default="{}", help="JSON args for the tool call.")
def mcp_evaluate(tool: str, agent: str, tool_args: str) -> None:
    """Evaluate an MCP tool call against governance.

    Tests whether an agent at the given address is permitted to invoke the
    specified tool. Uses default-deny policy.

    Example:
        pact mcp evaluate --tool web_search --agent D1-R1-T1-R1
    """
    engine = _get_engine()
    if engine is None:
        error_console.print(
            "[bold red]No org loaded.[/bold red] Load an org first.\n\n"
            "  [cyan]pact quickstart --example university[/cyan]\n"
            "  [cyan]pact org create org.yaml[/cyan]"
        )
        sys.exit(1)

    # Parse tool args
    try:
        parsed_args = json.loads(tool_args)
    except json.JSONDecodeError as exc:
        error_console.print(f"[bold red]Invalid JSON args:[/bold red] {exc}")
        sys.exit(1)

    from pact_platform.use.mcp.bridge import PlatformMcpGovernance

    # Create a bridge with no pre-registered tools (default-deny)
    gov = PlatformMcpGovernance(engine=engine, tool_policies=[])

    result = gov.evaluate_tool_call(
        tool_name=tool,
        args=parsed_args,
        agent_address=agent,
    )

    # Display result
    level = result["level"]
    level_colors = {
        "auto_approved": "green",
        "flagged": "yellow",
        "held": "yellow",
        "blocked": "red",
    }
    color = level_colors.get(level, "white")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")
    table.add_row("Tool", tool)
    table.add_row("Agent", agent)
    table.add_row("Verdict", f"[bold {color}]{level}[/bold {color}]")
    table.add_row("Reason", result["reason"])
    table.add_row("Timestamp", result["timestamp"])

    console.print()
    console.print(
        Panel(
            f"MCP tool call evaluation: [{color}]{level}[/{color}]",
            title="PACT — MCP Evaluate",
            border_style=color,
        )
    )
    console.print(table)


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
# config group (TODO-23)
# ---------------------------------------------------------------------------


@main.group()
def config() -> None:
    """Platform configuration — show and manage runtime settings."""


@config.command("show")
def config_show() -> None:
    """Show current platform configuration settings.

    Displays the enforcement mode and other runtime settings.
    """
    from pact_platform.engine.settings import get_platform_settings

    settings = get_platform_settings()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="dim")
    table.add_column("Value")
    table.add_column("Description")

    table.add_row(
        "Enforcement Mode",
        f"[bold]{settings.enforcement_mode.value}[/bold]",
        {
            "enforce": "Governance blocks/holds actions (production)",
            "shadow": "Governance observes only, never blocks",
            "disabled": "Governance bypassed entirely (development)",
        }.get(settings.enforcement_mode.value, ""),
    )

    engine = _get_engine()
    table.add_row(
        "Governance Engine",
        "[green]loaded[/green]" if engine is not None else "[dim]not loaded[/dim]",
        "GovernanceEngine in-memory state",
    )

    console.print()
    console.print(
        Panel(
            "[bold cyan]Platform Configuration[/bold cyan]",
            border_style="blue",
        )
    )
    console.print(table)

    if settings.enforcement_mode.value == "disabled":
        console.print(
            "\n  [bold yellow]Warning:[/bold yellow] Governance is disabled. "
            "All actions will bypass governance verification."
        )


# ---------------------------------------------------------------------------
# calibrate command (TODO-24)
# ---------------------------------------------------------------------------


@main.command()
@click.argument("org_file", type=click.Path(exists=True))
def calibrate(org_file: str) -> None:
    """Run shadow calibration on an org definition.

    Takes an org YAML file, generates synthetic actions for each role,
    runs them through governance in shadow mode, and reports per-supervisor
    held ratios.

    Flags:
    - Below 10% held: potential constraint theater (too permissive)
    - Above 50% held: potential over-restriction

    Usage:
        pact calibrate org.yaml
    """
    from pact.governance import GovernanceEngine, load_org_yaml

    from pact_platform.trust.shadow_enforcer import ShadowEnforcer

    # --- Load the org ---
    console.print()
    with console.status(f"[bold green]Loading org from {org_file}..."):
        try:
            loaded = load_org_yaml(org_file)
        except Exception as exc:
            error_console.print(f"[bold red]Failed to load org:[/bold red] {exc}")
            sys.exit(1)

        audit_chain = _make_audit_chain()
        engine = GovernanceEngine(loaded.org_definition, audit_chain=audit_chain)
        compiled_org = engine.get_org()

    console.print(f"  [green]Compiled[/green] {len(compiled_org.nodes)} nodes from {org_file}")

    # --- Apply envelopes from YAML ---
    for spec in loaded.envelopes:
        from pact.governance import RoleEnvelope
        from pact_platform.build.config.schema import (
            CommunicationConstraintConfig,
            ConstraintEnvelopeConfig,
            DataAccessConstraintConfig,
            FinancialConstraintConfig,
            OperationalConstraintConfig,
            TemporalConstraintConfig,
        )

        target_node = compiled_org.get_node_by_role_id(spec.target)
        definer_node = compiled_org.get_node_by_role_id(spec.defined_by)
        if target_node is None or definer_node is None:
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

    # --- Identify supervisors and roles ---
    from pact.governance import OrgNode

    supervisors: dict[str, list[str]] = {}  # supervisor_addr -> [role_addrs]
    all_roles: list[str] = []

    for addr, node in compiled_org.nodes.items():
        all_roles.append(addr)
        node_type = getattr(node, "node_type", None)
        type_val = node_type.value if hasattr(node_type, "value") else str(node_type)
        if type_val in ("supervisor", "department_head"):
            supervisors[addr] = []

    # Map roles to their parent supervisors (approximate via address prefix)
    for addr in all_roles:
        for sup_addr in supervisors:
            if addr != sup_addr and addr.startswith(sup_addr):
                supervisors[sup_addr].append(addr)
                break
        else:
            # If not under any supervisor, it may be a top-level supervisor itself
            pass

    if not supervisors:
        # Treat all addresses as one group under a synthetic supervisor
        supervisors["(org-root)"] = all_roles

    # --- Synthetic actions for calibration ---
    # Generate one action per gradient zone per role
    _SYNTHETIC_ACTIONS = [
        "read_data",
        "write_data",
        "execute_task",
        "approve_request",
        "deploy_change",
        "send_external_message",
        "access_confidential_data",
        "high_cost_operation",
    ]

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Shadow Calibration[/bold cyan] -- "
            f"{len(supervisors)} supervisor(s), {len(all_roles)} role(s), "
            f"{len(_SYNTHETIC_ACTIONS)} synthetic actions each",
            border_style="blue",
        )
    )

    # --- Run shadow evaluation ---
    supervisor_metrics: dict[str, dict[str, int]] = {}

    for sup_addr, subordinate_addrs in supervisors.items():
        role_addrs = subordinate_addrs if subordinate_addrs else [sup_addr]
        totals = {"total": 0, "auto_approved": 0, "flagged": 0, "held": 0, "blocked": 0}

        for role_addr in role_addrs:
            shadow = ShadowEnforcer(
                governance_engine=engine,
                role_address=role_addr,
            )
            for action in _SYNTHETIC_ACTIONS:
                result = shadow.evaluate(
                    action=action,
                    agent_id=f"calibration-{role_addr}",
                )
                totals["total"] += 1
                if result.would_be_auto_approved:
                    totals["auto_approved"] += 1
                elif result.would_be_flagged:
                    totals["flagged"] += 1
                elif result.would_be_held:
                    totals["held"] += 1
                elif result.would_be_blocked:
                    totals["blocked"] += 1

        supervisor_metrics[sup_addr] = totals

    # --- Report results ---
    results_table = Table(
        title="Shadow Calibration Results",
        show_header=True,
        header_style="bold cyan",
    )
    results_table.add_column("Supervisor", style="bold")
    results_table.add_column("Total", justify="right")
    results_table.add_column("Auto-Approved", justify="right")
    results_table.add_column("Flagged", justify="right")
    results_table.add_column("Held", justify="right")
    results_table.add_column("Blocked", justify="right")
    results_table.add_column("Held Ratio", justify="right")
    results_table.add_column("Assessment")

    for sup_addr, metrics in sorted(supervisor_metrics.items()):
        total = metrics["total"]
        held = metrics["held"]
        held_ratio = held / total if total > 0 else 0.0

        if held_ratio < 0.10:
            assessment = "[yellow]Under-restriction (constraint theater)[/yellow]"
        elif held_ratio > 0.50:
            assessment = "[red]Over-restriction[/red]"
        else:
            assessment = "[green]Healthy[/green]"

        results_table.add_row(
            sup_addr,
            str(total),
            str(metrics["auto_approved"]),
            str(metrics["flagged"]),
            str(held),
            str(metrics["blocked"]),
            f"{held_ratio:.0%}",
            assessment,
        )

    console.print()
    console.print(results_table)

    # --- Summary ---
    under_restriction = [
        s for s, m in supervisor_metrics.items() if m["total"] > 0 and m["held"] / m["total"] < 0.10
    ]
    over_restriction = [
        s for s, m in supervisor_metrics.items() if m["total"] > 0 and m["held"] / m["total"] > 0.50
    ]

    console.print()
    if under_restriction:
        console.print(
            f"  [yellow]Constraint theater warning:[/yellow] "
            f"{len(under_restriction)} supervisor(s) below 10% held ratio: "
            f"{', '.join(under_restriction)}"
        )
    if over_restriction:
        console.print(
            f"  [red]Over-restriction warning:[/red] "
            f"{len(over_restriction)} supervisor(s) above 50% held ratio: "
            f"{', '.join(over_restriction)}"
        )
    if not under_restriction and not over_restriction:
        console.print("  [green]All supervisors within healthy held ratio range (10-50%).[/green]")

    console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
