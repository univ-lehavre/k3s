from pathlib import Path

import typer
from k3splan import Connection, load_inventory, load_manifest, resolve_connection
from k3splan.observed import ObservedState
from k3splan.planner import build_plan
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
def plan(manifest: Path, inventory: Path | None = None) -> None:
    """Show the actions required to reach the desired state."""
    desired = load_manifest(manifest)
    observed = None
    if inventory is not None:
        target, connection = resolve_manifest_connection(manifest, inventory)
        observed = inspect_machine(target, SshExecutor(connection))

    generated_plan = build_plan(desired, observed)

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

    console.print(f"[bold]Inspect: {observed.target}[/]")
    for table in build_inspect_tables(observed):
        console.print(table)

    for error in observed.errors:
        console.print(f"[red]error[/] {error}")


def build_inspect_tables(observed: ObservedState) -> list[Table]:
    connection = metric_table("Connection")
    connection.add_row("SSH", "available" if observed.sshAvailable else "unavailable")

    system = metric_table("System")
    system.add_row("OS", observed.system.os or "unknown")
    system.add_row("Distribution", observed.system.distributionPrettyName or "unknown")
    system.add_row("Architecture", observed.system.architecture or "unknown")
    system.add_row("systemd", "yes" if observed.system.systemd else "no")

    resources = metric_table("Resources")
    resources.add_row("CPU cores", format_optional_int(observed.system.cpu.cores))
    resources.add_row("CPU usage", format_percent_float(observed.system.cpu.usagePercent))
    resources.add_row("Disk / size", format_mib(observed.system.disk.totalMiB))
    resources.add_row("Disk / used", format_percent(observed.system.disk.usedPercent))
    resources.add_row("Memory available", format_mib(observed.system.memory.availableMiB))

    apt = metric_table("APT")
    apt.add_row("apt-get", "available" if observed.system.apt.available else "unavailable")
    apt.add_row("last update", observed.system.apt.lastUpdate or "unknown")
    apt.add_row("lists fresh", format_optional_bool(observed.system.apt.packageListsFresh))
    apt.add_row("upgradable packages", format_optional_int(observed.system.apt.upgradablePackages))
    apt.add_row("system up to date", format_optional_bool(observed.system.apt.systemUpToDate))

    k3s = metric_table("k3s")
    k3s.add_row("installed", "yes" if observed.k3s.installed else "no")
    k3s.add_row("version", observed.k3s.version or "unknown")
    k3s.add_row("service active", format_optional_bool(observed.k3s.serviceActive))
    k3s.add_row("service enabled", format_optional_bool(observed.k3s.serviceEnabled))

    return [connection, system, resources, apt, k3s]


def metric_table(title: str) -> Table:
    table = Table(title=title)
    table.add_column("Check")
    table.add_column("Value")
    return table


def format_percent(value: int | None) -> str:
    return "unknown" if value is None else f"{value}%"


def format_percent_float(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.1f}%"


def format_mib(value: int | None) -> str:
    return "unknown" if value is None else f"{value} MiB"


def format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def format_optional_int(value: int | None) -> str:
    return "unknown" if value is None else str(value)
