from pathlib import Path
from typing import Annotated, Any

import typer
from k3splan import Connection, load_inventory, load_manifest, resolve_connection
from k3splan.observed import ObservedState
from k3splan.planner import build_plan
from k3sremote import SshExecutor, inspect_machine
from rich.console import Console
from rich.table import Table
from ruamel.yaml import YAML

app = typer.Typer(help="Declarative k3s machine reconciler.")
context_app = typer.Typer(help="Manage local k3sctl context.")
app.add_typer(context_app, name="context")
console = Console()
DEFAULT_CONTEXT_PATH = Path(".k3sctl.yaml")


def _load_raw(path: Path = DEFAULT_CONTEXT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8")) or {}


def _write_raw(data: dict[str, Any], path: Path = DEFAULT_CONTEXT_PATH) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def load_active_context(path: Path = DEFAULT_CONTEXT_PATH) -> dict[str, Path]:
    raw = _load_raw(path)
    contexts = raw.get("contexts", {})
    current = raw.get("current-context")

    if not current or current not in contexts:
        return {}

    entry = contexts[current]
    result: dict[str, Path] = {}
    if "manifest" in entry:
        result["manifest"] = Path(str(entry["manifest"]))
    if "inventory" in entry:
        result["inventory"] = Path(str(entry["inventory"]))
    return result


def resolve_paths(manifest: Path | None, inventory: Path | None) -> tuple[Path, Path | None]:
    context = load_active_context()
    resolved_manifest = manifest or context.get("manifest")
    resolved_inventory = inventory or context.get("inventory")

    if resolved_manifest is None:
        raise typer.BadParameter("manifest is required or must be configured in .k3sctl.yaml")

    return resolved_manifest, resolved_inventory


def resolve_manifest_connection(manifest: Path, inventory: Path | None) -> tuple[str, Connection]:
    desired = load_manifest(manifest)
    loaded_inventory = load_inventory(inventory) if inventory is not None else None
    try:
        return desired.metadata.name, resolve_connection(desired, loaded_inventory)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@context_app.command("set")
def set_context(name: str, manifest: Path, inventory: Path) -> None:
    """Create or update a named context."""
    raw = _load_raw()
    raw.setdefault("contexts", {})[name] = {
        "manifest": str(manifest),
        "inventory": str(inventory),
    }
    if "current-context" not in raw:
        raw["current-context"] = name
    _write_raw(raw)
    console.print(f"[green]OK[/] context [bold]{name}[/] saved to {DEFAULT_CONTEXT_PATH}")


@context_app.command("use")
def use_context(name: str) -> None:
    """Switch the active context."""
    raw = _load_raw()
    contexts = raw.get("contexts", {})
    if name not in contexts:
        raise typer.BadParameter(f"context '{name}' not found")
    raw["current-context"] = name
    _write_raw(raw)
    console.print(f"[green]OK[/] switched to context [bold]{name}[/]")


@context_app.command("list")
def list_contexts() -> None:
    """List all contexts."""
    raw = _load_raw()
    contexts = raw.get("contexts", {})
    current = raw.get("current-context", "")

    if not contexts:
        console.print("[yellow]No contexts configured[/]")
        return

    table = Table(title="Contexts")
    table.add_column("")
    table.add_column("Name")
    table.add_column("Manifest")
    table.add_column("Inventory")
    for name, entry in contexts.items():
        marker = "[green]*[/]" if name == current else ""
        table.add_row(marker, name, entry.get("manifest", ""), entry.get("inventory", ""))
    console.print(table)


@context_app.command("show")
def show_context() -> None:
    """Show the active context."""
    raw = _load_raw()
    current = raw.get("current-context")
    contexts = raw.get("contexts", {})

    if not current or current not in contexts:
        console.print("[yellow]No active context[/]")
        return

    entry = contexts[current]
    table = Table(title=f"Context: {current}")
    table.add_column("Key")
    table.add_column("Path")
    for key, value in entry.items():
        table.add_row(key, str(value))
    console.print(table)


ManifestArgument = Annotated[Path | None, typer.Argument()]


@app.command()
def validate(manifest: ManifestArgument = None, inventory: Path | None = None) -> None:
    """Validate a machine manifest."""
    manifest, inventory = resolve_paths(manifest, inventory)
    desired = load_manifest(manifest)
    if inventory is not None:
        loaded_inventory = load_inventory(inventory)
        try:
            resolve_connection(desired, loaded_inventory)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    console.print(f"[green]OK[/] {desired.kind} {desired.metadata.name}")


@app.command()
def plan(manifest: ManifestArgument = None, inventory: Path | None = None) -> None:
    """Show the actions required to reach the desired state."""
    manifest, inventory = resolve_paths(manifest, inventory)
    desired = load_manifest(manifest)
    observed = None
    if inventory is not None:
        target, connection = resolve_manifest_connection(manifest, inventory)
        observed = inspect_machine(
            target,
            SshExecutor(connection),
            package_names=desired.spec.system.packages.present,
            sysctl_keys=list(desired.spec.system.sysctl),
        )

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
def inspect(manifest: ManifestArgument = None, inventory: Path | None = None) -> None:
    """Inspect the target machine without modifying it."""
    manifest, inventory = resolve_paths(manifest, inventory)
    target, connection = resolve_manifest_connection(manifest, inventory)
    desired = load_manifest(manifest)
    observed = inspect_machine(
        target,
        SshExecutor(connection),
        package_names=desired.spec.system.packages.present,
        sysctl_keys=list(desired.spec.system.sysctl),
    )

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
