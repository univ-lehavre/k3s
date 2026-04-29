import subprocess
import time
from pathlib import Path

import pytest
import yaml

SSH_HOST = "127.0.0.1"
SSH_PORT = 2222
SSH_USER = "pilot"
KEY_PATH = Path(__file__).parent / "test_key"
MANIFEST_PATH = Path(__file__).parent / "fixtures" / "machine.yaml"
INVENTORY_PATH = Path(__file__).parent / "fixtures" / "inventory.yaml"


def _write_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    manifest = tmp_path / "machine.yaml"
    inventory = tmp_path / "inventory.yaml"

    manifest.write_text(
        yaml.dump(
            {
                "apiVersion": "cluster-pilot.dev/v1alpha1",
                "kind": "Machine",
                "metadata": {"name": "integ-target"},
                "spec": {
                    "connectionRef": "integ-target",
                    "system": {
                        "packages": {"present": ["curl", "iptables", "ca-certificates"]},
                        "sysctl": {"net.ipv4.ip_forward": "1"},
                    },
                    "k3s": {
                        "state": "present",
                        "role": "server",
                        "version": "v1.35.4+k3s1",
                        "install": {"channel": "stable", "method": "official-script"},
                        "config": {
                            "write-kubeconfig-mode": "0644",
                            "disable": ["traefik", "servicelb"],
                        },
                        "service": {"enabled": True, "running": True},
                    },
                    "health": {
                        "require": ["ssh.available", "system.os.supported"],
                        "thresholds": {"diskFreePercent": 5, "memoryFreeMiB": 128},
                    },
                    "execution": {
                        "mode": "transactional",
                        "verify": {"afterEachAction": True, "timeoutSeconds": 300},
                        "rollback": {
                            "enabled": True,
                            "on": ["applyFailure", "verifyFailure"],
                            "requireConfirmFor": [],
                            "strategy": "reverse-applied-actions",
                        },
                        "journal": {"location": "local", "path": str(tmp_path / "runs"), "keep": 5},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    inventory.write_text(
        yaml.dump(
            {
                "connections": {
                    "integ-target": {
                        "type": "ssh",
                        "host": SSH_HOST,
                        "user": SSH_USER,
                        "port": SSH_PORT,
                        "identityFile": str(KEY_PATH),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    return manifest, inventory


@pytest.fixture(scope="session")
def ssh_key(tmp_path_factory: pytest.TempPathFactory) -> Path:
    key = tmp_path_factory.mktemp("keys") / "id_ed25519"
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )
    return key


@pytest.fixture(scope="session")
def target_container(ssh_key: Path):
    pub_key = (ssh_key.parent / "id_ed25519.pub").read_text().strip()

    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--privileged",
            "--cgroupns=host",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup:rw",
            "-p",
            f"{SSH_PORT}:22",
            "cluster-pilot-test-target",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    container_id = result.stdout.strip()

    # Wait for sshd to be ready
    deadline = time.time() + 30
    while time.time() < deadline:
        r = subprocess.run(
            ["docker", "exec", container_id, "bash", "-c", "ss -tln | grep -q ':22'"],
            capture_output=True,
        )
        if r.returncode == 0:
            break
        time.sleep(1)

    # Inject public key
    subprocess.run(
        [
            "docker",
            "exec",
            container_id,
            "bash",
            "-c",
            f"echo '{pub_key}' >> /home/pilot/.ssh/authorized_keys && "
            "chown pilot:pilot /home/pilot/.ssh/authorized_keys && "
            "chmod 600 /home/pilot/.ssh/authorized_keys && "
            "service ssh start",
        ],
        check=True,
        capture_output=True,
    )

    # Wait for SSH to accept connections
    deadline = time.time() + 30
    while time.time() < deadline:
        r = subprocess.run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ConnectTimeout=2",
                "-i",
                str(ssh_key),
                "-p",
                str(SSH_PORT),
                f"{SSH_USER}@{SSH_HOST}",
                "true",
            ],
            capture_output=True,
        )
        if r.returncode == 0:
            break
        time.sleep(1)

    yield container_id, ssh_key

    subprocess.run(["docker", "stop", container_id], capture_output=True)


@pytest.fixture()
def integ_env(tmp_path: Path, target_container):
    container_id, ssh_key = target_container
    manifest, inventory = _write_fixtures(tmp_path)
    # Override key path in inventory with session key
    inv_data = yaml.safe_load(inventory.read_text())
    inv_data["connections"]["integ-target"]["identityFile"] = str(ssh_key)
    inventory.write_text(yaml.dump(inv_data), encoding="utf-8")
    return manifest, inventory, tmp_path
