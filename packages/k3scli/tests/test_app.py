from k3scli.app import app
from typer.testing import CliRunner


def test_validate_command() -> None:
    result = CliRunner().invoke(app, ["validate", "examples/single-server.yaml"])

    assert result.exit_code == 0
    assert "OK" in result.stdout
    assert "prod-1" in result.stdout


def test_validate_command_with_inventory() -> None:
    result = CliRunner().invoke(
        app,
        [
            "validate",
            "examples/single-server.yaml",
            "--inventory",
            "examples/inventory.example.yaml",
        ],
    )

    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_plan_command() -> None:
    result = CliRunner().invoke(app, ["plan", "examples/single-server.yaml"])

    assert result.exit_code == 0
    assert "Plan: prod-1" in result.stdout
    assert "Install k3s" in result.stdout


def test_inspect_requires_inventory_for_connection_ref() -> None:
    result = CliRunner().invoke(app, ["inspect", "examples/single-server.yaml"])

    assert result.exit_code != 0
    assert "manifest uses connectionRef but no inventory was provided" in result.output
