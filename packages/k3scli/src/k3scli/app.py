from pathlib import Path

import typer
from k3splan import Connection, load_inventory, load_manifest, resolve_connection
from k3splan.planner import build_initial_plan
from k3sremote import SshExecutor, inspect_machine
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Declarative k3s machine reconciler.")
console = Console()


def resolve_manifest_connection(manifest: Path, inventory: Path | None) -> tuple[str, Connection]:
    desired = load_manifest(manifest)
    loaded_inventory = load_inventory(inventory) if inventory is not None else None
    try:
        return desired.metadata.name, resolve_connection(desired, loaded_inventory)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def validate(manifest: Path, inventory: Path | None = None) -> None:
    """Validate a machine manifest."""
    desired = load_manifest(manifest)
    if inventory is not None:
        loaded_inventory = load_inventory(inventory)
        try:
            resolve_connection(desired, loaded_inventory)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    console.print(f"[green]OK[/] {desired.kind} {desired.metadata.name}")


@app.command()
def plan(manifest: Path) -> None:
    """Show the actions required to reach the desired state."""
    desired = load_manifest(manifest)
    generated_plan = build_initial_plan(desired)

    table = Table(title=f"Plan: {generated_plan.target}")
    table.add_column("#", justify="right")
    table.add_column("Action")
    table.add_column("Risk")
    table.add_column("Rollback")

    for index, action in enumerate(generated_plan.actions, start=1):
        table.add_row(str(index), action.description, action.risk, action.rollback)

    console.print(table)


@app.command()
def inspect(manifest: Path, inventory: Path | None = None) -> None:
    """Inspect the target machine without modifying it."""
    target, connection = resolve_manifest_connection(manifest, inventory)
    observed = inspect_machine(target, SshExecutor(connection))

    table = Table(title=f"Inspect: {observed.target}")
    table.add_column("Check")
    table.add_column("Value")

    table.add_row("SSH", "available" if observed.sshAvailable else "unavailable")
    table.add_row("OS", observed.system.os or "unknown")
    table.add_row("Architecture", observed.system.architecture or "unknown")
    table.add_row("systemd", "yes" if observed.system.systemd else "no")
    table.add_row("Disk / used", format_percent(observed.system.disk.usedPercent))
    table.add_row("Memory available", format_mib(observed.system.memory.availableMiB))
    table.add_row("k3s installed", "yes" if observed.k3s.installed else "no")
    table.add_row("k3s version", observed.k3s.version or "unknown")
    table.add_row("k3s service active", format_optional_bool(observed.k3s.serviceActive))
    table.add_row("k3s service enabled", format_optional_bool(observed.k3s.serviceEnabled))

    console.print(table)

    for error in observed.errors:
        console.print(f"[red]error[/] {error}")


def format_percent(value: int | None) -> str:
    return "unknown" if value is None else f"{value}%"


def format_mib(value: int | None) -> str:
    return "unknown" if value is None else f"{value} MiB"


def format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"
