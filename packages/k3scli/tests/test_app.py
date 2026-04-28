from pathlib import Path
from typing import Any

from k3scli.app import app, build_inspect_tables
from k3splan import AptState, CpuState, DiskState, MemoryState, ObservedState, SystemState
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[3]
SINGLE_SERVER = REPO_ROOT / "examples/single-server.yaml"
EXAMPLE_INVENTORY = REPO_ROOT / "examples/inventory.example.yaml"


def test_validate_command() -> None:
    result = CliRunner().invoke(app, ["validate", str(SINGLE_SERVER)])

    assert result.exit_code == 0
    assert "OK" in result.stdout
    assert "prod-1" in result.stdout


def test_validate_command_with_inventory() -> None:
    result = CliRunner().invoke(
        app,
        [
            "validate",
            str(SINGLE_SERVER),
            "--inventory",
            str(EXAMPLE_INVENTORY),
        ],
    )

    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_plan_command(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["plan", str(SINGLE_SERVER)])

    assert result.exit_code == 0
    assert "Plan: prod-1" in result.stdout
    assert "Install k3s" in result.stdout


def test_context_commands(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "machine.yaml"
    inventory = tmp_path / "inventory.local.yaml"
    manifest.write_text(
        SINGLE_SERVER.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    inventory.write_text(
        EXAMPLE_INVENTORY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    set_result = CliRunner().invoke(app, ["context", "set", "dev", str(manifest), str(inventory)])
    show_result = CliRunner().invoke(app, ["context", "show"])
    list_result = CliRunner().invoke(app, ["context", "list"])
    validate_result = CliRunner().invoke(app, ["validate"])

    assert set_result.exit_code == 0
    assert show_result.exit_code == 0
    assert "manifest" in show_result.stdout
    assert "inventory" in show_result.stdout
    assert list_result.exit_code == 0
    assert "dev" in list_result.stdout
    assert validate_result.exit_code == 0
    assert "OK" in validate_result.stdout


def test_context_use(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "machine.yaml"
    inventory = tmp_path / "inventory.local.yaml"
    manifest.write_text(SINGLE_SERVER.read_text(encoding="utf-8"), encoding="utf-8")
    inventory.write_text(EXAMPLE_INVENTORY.read_text(encoding="utf-8"), encoding="utf-8")

    runner = CliRunner()
    runner.invoke(app, ["context", "set", "dev", str(manifest), str(inventory)])
    runner.invoke(app, ["context", "set", "prod", str(manifest), str(inventory)])

    use_result = runner.invoke(app, ["context", "use", "prod"])
    show_result = runner.invoke(app, ["context", "show"])

    assert use_result.exit_code == 0
    assert "prod" in use_result.stdout
    assert "prod" in show_result.stdout


def test_context_use_unknown(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["context", "use", "ghost"])
    assert result.exit_code != 0


def test_inspect_requires_inventory_for_connection_ref(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["inspect", str(SINGLE_SERVER)])

    assert result.exit_code != 0
    assert "manifest uses connectionRef but no inventory was provided" in result.output


def test_inspect_tables_are_grouped() -> None:
    observed = ObservedState(
        target="prod-1",
        sshAvailable=True,
        system=SystemState(
            os="Linux",
            distributionPrettyName="Ubuntu 24.04.4 LTS",
            architecture="x86_64",
            cpu=CpuState(cores=12, usagePercent=0.1),
            disk=DiskState(totalMiB=1000, usedPercent=1),
            memory=MemoryState(availableMiB=512),
            apt=AptState(available=True, upgradablePackages=0, systemUpToDate=True),
        ),
    )

    tables = build_inspect_tables(observed)

    assert [table.title for table in tables] == ["Connection", "System", "Resources", "APT", "k3s"]
