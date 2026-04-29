"""Integration tests: full apply → doctor → uninstall cycle against a real container."""

import subprocess
import sys
from pathlib import Path


def _pilot(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pilotcli.app", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def pilot(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "pilot", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_inspect(integ_env):
    manifest, inventory, tmp = integ_env
    result = pilot(["inspect", str(manifest), "--inventory", str(inventory)])
    assert result.returncode == 0, result.stderr
    assert "ubuntu" in result.stdout.lower() or "SSH" in result.stdout


def test_validate(integ_env):
    manifest, inventory, tmp = integ_env
    result = pilot(["validate", str(manifest), "--inventory", str(inventory)])
    assert result.returncode == 0, result.stderr


def test_plan(integ_env):
    manifest, inventory, tmp = integ_env
    result = pilot(["plan", str(manifest), "--inventory", str(inventory)])
    assert result.returncode == 0, result.stderr
    assert "k3s" in result.stdout.lower()


def test_apply_and_doctor(integ_env):
    manifest, inventory, tmp = integ_env
    result = pilot(["apply", str(manifest), "--inventory", str(inventory)])
    assert result.returncode == 0, result.stderr + result.stdout

    result = pilot(["doctor", str(manifest), "--inventory", str(inventory)])
    assert result.returncode == 0, result.stderr + result.stdout


def test_drift_after_apply(integ_env):
    manifest, inventory, tmp = integ_env
    # After apply the machine should be in sync
    result = pilot(["drift", str(manifest), "--inventory", str(inventory)])
    assert result.returncode == 0, result.stderr + result.stdout
    assert "in sync" in result.stdout


def test_uninstall(integ_env, tmp_path):
    manifest, inventory, tmp = integ_env
    uninstall_manifest = tmp_path / "uninstall.yaml"
    import yaml

    data = yaml.safe_load(manifest.read_text())
    data["spec"]["k3s"]["state"] = "absent"
    data["spec"]["k3s"].setdefault("uninstall", {})
    data["spec"]["k3s"]["uninstall"]["removeData"] = True
    data["spec"]["k3s"]["uninstall"]["removeKubeconfig"] = False
    uninstall_manifest.write_text(yaml.dump(data), encoding="utf-8")

    result = pilot(["apply", str(uninstall_manifest), "--inventory", str(inventory)])
    assert result.returncode == 0, result.stderr + result.stdout
