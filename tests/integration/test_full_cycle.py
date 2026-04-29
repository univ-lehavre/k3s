"""Integration tests: full apply → doctor → uninstall cycle against a real container."""

import io
import subprocess
import sys
from pathlib import Path


def pilot(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a pilot command, streaming output live and capturing it for assertions."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    with subprocess.Popen(
        ["uv", "run", "pilot", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
    ) as proc:
        assert proc.stdout is not None
        assert proc.stderr is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            stdout_buf.write(line)
        for line in proc.stderr:
            sys.stderr.write(line)
            sys.stderr.flush()
            stderr_buf.write(line)

    return subprocess.CompletedProcess(
        args=proc.args,
        returncode=proc.returncode,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
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
