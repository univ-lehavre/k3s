from pathlib import Path

from pilotplan import K3sState, ObservedState, SystemState, load_manifest
from pilotplan.health import check_health
from pilotplan.observed import AptState, DiskState, MemoryState

SINGLE_SERVER = Path("examples/single-server.yaml")


def _observed(**kwargs) -> ObservedState:  # type: ignore[no-untyped-def]
    return ObservedState(target="prod-1", sshAvailable=True, **kwargs)


def test_healthy_machine() -> None:
    desired = load_manifest(SINGLE_SERVER)
    observed = _observed(
        system=SystemState(
            os="Linux",
            distributionPrettyName="Ubuntu 24.04 LTS",
            disk=DiskState(usedPercent=40),
            memory=MemoryState(availableMiB=1024),
            apt=AptState(available=True, systemUpToDate=True),
        ),
        k3s=K3sState(
            installed=True,
            version="k3s version v1.35.3+k3s1",
            serviceActive=True,
            serviceEnabled=True,
        ),
    )

    report = check_health(desired, observed)

    assert report.verdict == "healthy"
    assert all(c.status in ("ok", "unknown") for c in report.checks)


def test_unhealthy_when_ssh_unavailable() -> None:
    desired = load_manifest(SINGLE_SERVER)
    observed = ObservedState(target="prod-1", sshAvailable=False)

    report = check_health(desired, observed)

    assert report.verdict == "unhealthy"
    assert report.checks[0].name == "ssh.available"
    assert report.checks[0].status == "error"


def test_degraded_on_version_drift() -> None:
    desired = load_manifest(SINGLE_SERVER)
    observed = _observed(
        system=SystemState(
            os="Linux",
            disk=DiskState(usedPercent=40),
            memory=MemoryState(availableMiB=1024),
        ),
        k3s=K3sState(installed=True, version="k3s version v1.30.0+k3s1", serviceActive=True),
    )

    report = check_health(desired, observed)

    version_check = next(c for c in report.checks if c.name == "k3s.version.matches")
    assert version_check.status == "warning"
    assert report.verdict == "degraded"


def test_error_on_low_disk() -> None:
    desired = load_manifest(SINGLE_SERVER)
    observed = _observed(
        system=SystemState(
            os="Linux",
            disk=DiskState(usedPercent=95),
            memory=MemoryState(availableMiB=1024),
        ),
    )

    report = check_health(desired, observed)

    disk_check = next(c for c in report.checks if c.name == "system.disk.available")
    assert disk_check.status == "error"
    assert report.verdict == "unhealthy"


def test_error_on_low_memory() -> None:
    desired = load_manifest(SINGLE_SERVER)
    observed = _observed(
        system=SystemState(
            os="Linux",
            disk=DiskState(usedPercent=40),
            memory=MemoryState(availableMiB=128),
        ),
    )

    report = check_health(desired, observed)

    mem_check = next(c for c in report.checks if c.name == "system.memory.available")
    assert mem_check.status == "error"


def test_apt_warning_when_upgrades_available() -> None:
    desired = load_manifest(SINGLE_SERVER)
    observed = _observed(
        system=SystemState(
            os="Linux",
            disk=DiskState(usedPercent=40),
            memory=MemoryState(availableMiB=1024),
            apt=AptState(available=True, upgradablePackages=5, systemUpToDate=False),
        ),
    )

    report = check_health(desired, observed)

    apt_check = next((c for c in report.checks if c.name == "system.apt.uptodate"), None)
    assert apt_check is not None
    assert apt_check.status == "warning"


def test_node_ready_check_is_unknown() -> None:
    desired = load_manifest(SINGLE_SERVER)
    observed = _observed(
        system=SystemState(os="Linux"),
        k3s=K3sState(installed=True, serviceActive=True),
    )

    report = check_health(desired, observed)

    node_check = next((c for c in report.checks if c.name == "k3s.node.ready"), None)
    assert node_check is not None
    assert node_check.status == "unknown"
