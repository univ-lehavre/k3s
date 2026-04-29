from dataclasses import dataclass
from typing import Literal

from pilotplan.manifest import DesiredState
from pilotplan.observed import ObservedState

CheckStatus = Literal["ok", "warning", "error", "unknown"]
Verdict = Literal["healthy", "degraded", "unhealthy"]


@dataclass
class HealthCheck:
    name: str
    status: CheckStatus
    message: str


@dataclass
class HealthReport:
    target: str
    checks: list[HealthCheck]

    @property
    def verdict(self) -> Verdict:
        statuses = {c.status for c in self.checks}
        if "error" in statuses:
            return "unhealthy"
        if "warning" in statuses:
            return "degraded"
        return "healthy"


def check_health(desired: DesiredState, observed: ObservedState) -> HealthReport:
    required = set(desired.spec.health.require)
    thresholds = desired.spec.health.thresholds
    disk_threshold = thresholds.get("diskFreePercent", 15)
    memory_threshold = thresholds.get("memoryFreeMiB", 512)

    checks: list[HealthCheck] = []

    # SSH
    if observed.sshAvailable:
        checks.append(HealthCheck("ssh.available", "ok", "SSH reachable"))
    else:
        checks.append(HealthCheck("ssh.available", "error", "SSH unreachable"))
        return HealthReport(target=observed.target, checks=checks)

    # OS
    os_ok = observed.system.os == "Linux"
    if "system.os.supported" in required:
        checks.append(
            HealthCheck(
                "system.os.supported",
                "ok" if os_ok else "error",
                observed.system.distributionPrettyName or observed.system.os or "unknown",
            )
        )

    # Disk
    if "system.disk.available" in required:
        used = observed.system.disk.usedPercent
        if used is None:
            checks.append(HealthCheck("system.disk.available", "unknown", "disk usage unknown"))
        else:
            free = 100 - used
            if free >= disk_threshold:
                checks.append(
                    HealthCheck(
                        "system.disk.available", "ok", f"{free}% free (threshold {disk_threshold}%)"
                    )
                )
            elif free >= disk_threshold // 2:
                checks.append(
                    HealthCheck(
                        "system.disk.available",
                        "warning",
                        f"{free}% free (threshold {disk_threshold}%)",
                    )
                )
            else:
                checks.append(
                    HealthCheck(
                        "system.disk.available",
                        "error",
                        f"{free}% free (threshold {disk_threshold}%)",
                    )
                )

    # Memory
    if "system.memory.available" in required:
        available = observed.system.memory.availableMiB
        if available is None:
            checks.append(
                HealthCheck("system.memory.available", "unknown", "memory info unavailable")
            )
        elif available >= memory_threshold:
            checks.append(
                HealthCheck(
                    "system.memory.available",
                    "ok",
                    f"{available} MiB free (threshold {memory_threshold} MiB)",
                )
            )
        else:
            checks.append(
                HealthCheck(
                    "system.memory.available",
                    "error",
                    f"{available} MiB free (threshold {memory_threshold} MiB)",
                )
            )

    # k3s service running
    if "systemd.k3s.running" in required:
        active = observed.k3s.serviceActive
        if active is None:
            checks.append(HealthCheck("systemd.k3s.running", "unknown", "service state unknown"))
        elif active:
            checks.append(HealthCheck("systemd.k3s.running", "ok", "k3s service active"))
        else:
            checks.append(HealthCheck("systemd.k3s.running", "error", "k3s service inactive"))

    # k3s version
    if "k3s.version.matches" in required:
        desired_version = desired.spec.k3s.version
        observed_version = observed.k3s.version
        if desired_version is None:
            checks.append(HealthCheck("k3s.version.matches", "ok", "no version pinned"))
        elif observed_version is None:
            checks.append(HealthCheck("k3s.version.matches", "unknown", "k3s not installed"))
        elif desired_version in observed_version:
            checks.append(
                HealthCheck("k3s.version.matches", "ok", f"version {desired_version} found")
            )
        else:
            checks.append(
                HealthCheck(
                    "k3s.version.matches",
                    "warning",
                    f"desired {desired_version}, observed {observed_version}",
                )
            )

    # k3s node ready — not observable without kubectl in current ObservedState
    for check_name in ("k3s.node.ready", "k3s.systemPods.healthy"):
        if check_name in required:
            checks.append(HealthCheck(check_name, "unknown", "requires live kubectl access"))

    # APT — always included as informational
    apt = observed.system.apt
    if apt.available:
        if apt.systemUpToDate is True:
            checks.append(HealthCheck("system.apt.uptodate", "ok", "system up to date"))
        elif apt.systemUpToDate is False:
            msg = f"{apt.upgradablePackages} package(s) upgradable"
            checks.append(HealthCheck("system.apt.uptodate", "warning", msg))

    return HealthReport(target=observed.target, checks=checks)
