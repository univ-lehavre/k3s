from pathlib import Path

from pilotplan import (
    K3sState,
    ObservedState,
    SystemState,
    load_inventory,
    load_manifest,
    resolve_connection,
)
from pilotplan.planner import build_initial_plan, build_plan
from pydantic import ValidationError


def test_load_manifest() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))

    assert desired.metadata.name == "prod-1"
    assert desired.spec.connectionRef == "prod-1"
    assert desired.spec.k3s.state == "present"


def test_resolve_connection_from_inventory() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    inventory = load_inventory(Path("examples/inventory.example.yaml"))

    connection = resolve_connection(desired, inventory)

    assert connection.host == "192.0.2.10"
    assert connection.user == "root"


def test_manifest_requires_one_connection_source() -> None:
    try:
        load_manifest(Path("examples/invalid-missing-connection.yaml"))
    except ValidationError as exc:
        assert "spec must define exactly one of connection or connectionRef" in str(exc)
    else:
        raise AssertionError("manifest should be invalid without a connection source")


def test_build_initial_plan() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_initial_plan(desired)

    assert plan.target == "prod-1"
    assert [action.id for action in plan.actions] == [
        "package.present.curl",
        "package.present.iptables",
        "package.present.ca-certificates",
        "sysctl.net.ipv4.ip_forward",
        "sysctl.net.bridge.bridge-nf-call-iptables",
        "k3s.config.write",
        "k3s.install",
        "systemd.k3s.enable",
        "systemd.k3s.start",
        "k3s.node.ready",
        "k3s.kubeconfig.fetch",
    ]


def test_build_observed_plan_skips_install_when_k3s_is_present() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_plan(
        desired,
        ObservedState(
            target="prod-1",
            sshAvailable=True,
            k3s=K3sState(
                installed=True,
                version="k3s version v1.30.5+k3s1",
                serviceActive=True,
                serviceEnabled=True,
            ),
        ),
    )

    assert "k3s.install" not in [action.id for action in plan.actions]
    assert "systemd.k3s.start" not in [action.id for action in plan.actions]
    assert "systemd.k3s.enable" not in [action.id for action in plan.actions]


def test_build_observed_plan_skips_matching_packages_and_sysctl() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_plan(
        desired,
        ObservedState(
            target="prod-1",
            sshAvailable=True,
            system=SystemState(
                packages={
                    "curl": True,
                    "iptables": True,
                    "ca-certificates": True,
                },
                sysctl={
                    "net.ipv4.ip_forward": "1",
                    "net.bridge.bridge-nf-call-iptables": "1",
                },
            ),
        ),
    )

    action_ids = [action.id for action in plan.actions]

    assert "package.present.curl" not in action_ids
    assert "package.present.iptables" not in action_ids
    assert "package.present.ca-certificates" not in action_ids
    assert "sysctl.net.ipv4.ip_forward" not in action_ids
    assert "sysctl.net.bridge.bridge-nf-call-iptables" not in action_ids


def test_build_observed_plan_upgrades_k3s_on_version_drift() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_plan(
        desired,
        ObservedState(
            target="prod-1",
            sshAvailable=True,
            k3s=K3sState(
                installed=True,
                version="k3s version v1.29.0+k3s1",
                serviceActive=True,
                serviceEnabled=True,
            ),
        ),
    )

    action_ids = [action.id for action in plan.actions]
    assert "k3s.upgrade" in action_ids
    assert "k3s.install" not in action_ids


def test_build_observed_plan_enables_service_when_disabled() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_plan(
        desired,
        ObservedState(
            target="prod-1",
            sshAvailable=True,
            k3s=K3sState(installed=True, version="k3s version v1.30.5+k3s1", serviceEnabled=False),
        ),
    )

    assert "systemd.k3s.enable" in [action.id for action in plan.actions]


def test_build_observed_plan_starts_service_when_stopped() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_plan(
        desired,
        ObservedState(
            target="prod-1",
            sshAvailable=True,
            k3s=K3sState(installed=True, version="k3s version v1.30.5+k3s1", serviceActive=False),
        ),
    )

    assert "systemd.k3s.start" in [action.id for action in plan.actions]


def test_build_observed_plan_blocks_when_ssh_is_unavailable() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_plan(desired, ObservedState(target="prod-1", sshAvailable=False))

    assert [action.id for action in plan.actions] == ["ssh.unavailable"]


def test_load_cilium_manifest() -> None:
    desired = load_manifest(Path("examples/cilium-server.yaml"))

    assert desired.spec.networking.cni == "cilium"
    assert desired.spec.networking.cilium.version == "1.19.3"
    assert desired.spec.networking.cilium.kubeProxyReplacement is True


def test_build_initial_plan_with_cilium() -> None:
    desired = load_manifest(Path("examples/cilium-server.yaml"))
    plan = build_initial_plan(desired)

    action_ids = [action.id for action in plan.actions]
    cilium_idx = action_ids.index("cilium.helmchart.write")
    config_idx = action_ids.index("k3s.config.write")

    assert cilium_idx < config_idx


def test_build_observed_plan_with_cilium() -> None:
    desired = load_manifest(Path("examples/cilium-server.yaml"))
    plan = build_plan(desired, ObservedState(target="prod-1", sshAvailable=True))

    action_ids = [action.id for action in plan.actions]
    assert "cilium.helmchart.write" in action_ids
    assert action_ids.index("cilium.helmchart.write") < action_ids.index("k3s.config.write")


def test_flannel_manifest_has_no_cilium_action() -> None:
    desired = load_manifest(Path("examples/single-server.yaml"))
    plan = build_initial_plan(desired)

    assert "cilium.helmchart.write" not in [action.id for action in plan.actions]
