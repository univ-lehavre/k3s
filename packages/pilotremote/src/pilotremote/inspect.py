from collections.abc import Callable

from pilotplan import (
    AptState,
    CpuState,
    DiskState,
    K3sState,
    MemoryState,
    ObservedState,
    SystemState,
)

from pilotremote.executor import CommandResult, RemoteExecutor

OS_RELEASE_COMMAND = (
    "awk -F= '/^(ID|VERSION_ID|PRETTY_NAME)=/ "
    '{gsub(/^"|"$/, "", $2); values[$1]=$2} '
    'END {print values["ID"]; print values["VERSION_ID"]; print values["PRETTY_NAME"]}\' '
    "/etc/os-release"
)
APT_LAST_UPDATE_COMMAND = (
    "sh -c 'stamp=/var/lib/apt/periodic/update-success-stamp; "
    "target=/var/lib/apt/lists; "
    'if [ -e "$stamp" ]; then target="$stamp"; fi; '
    'last=$(stat -c %Y "$target" 2>/dev/null) || exit 1; '
    "now=$(date +%s); "
    'date -d "@$last" -Iseconds; '
    "echo $((now - last))'"
)
APT_UPGRADABLE_COMMAND = "sh -c 'apt list --upgradable 2>/dev/null | tail -n +2 | wc -l'"
APT_FRESHNESS_SECONDS = 24 * 60 * 60
CPU_USAGE_COMMAND = (
    "awk '/^cpu / {idle=$5; total=0; for (i=2; i<=NF; i++) total+=$i; "
    "print idle, total}' /proc/stat && sleep 1 && "
    "awk '/^cpu / {idle=$5; total=0; for (i=2; i<=NF; i++) total+=$i; "
    "print idle, total}' /proc/stat"
)


def inspect_machine(
    target: str,
    executor: RemoteExecutor,
    package_names: list[str] | None = None,
    sysctl_keys: list[str] | None = None,
) -> ObservedState:
    errors: list[str] = []

    probe = executor.run("true")
    if not probe.ok:
        return ObservedState(
            target=target,
            sshAvailable=False,
            errors=[format_error(probe)],
        )

    os_release = inspect_os_release(executor.run)
    system = SystemState(
        os=optional_stdout(executor.run("uname -s"), errors),
        architecture=optional_stdout(executor.run("uname -m"), errors),
        distribution=os_release.distribution,
        distributionVersion=os_release.version,
        distributionPrettyName=os_release.pretty_name,
        systemd=executor.run("command -v systemctl").ok,
        cpu=inspect_cpu(executor.run),
        disk=inspect_disk(executor.run),
        memory=inspect_memory(executor.run),
        apt=inspect_apt(executor.run),
        packages=inspect_packages(executor.run, package_names or []),
        sysctl=inspect_sysctl(executor.run, sysctl_keys or []),
    )
    k3s = inspect_k3s(executor.run, system.systemd)

    return ObservedState(target=target, sshAvailable=True, system=system, k3s=k3s, errors=errors)


class OsRelease:
    def __init__(
        self,
        distribution: str | None = None,
        version: str | None = None,
        pretty_name: str | None = None,
    ) -> None:
        self.distribution = distribution
        self.version = version
        self.pretty_name = pretty_name


def inspect_os_release(run: Callable[[str], CommandResult]) -> OsRelease:
    result = run(OS_RELEASE_COMMAND)
    if not result.ok:
        return OsRelease()

    lines = result.stdout.splitlines()
    if len(lines) < 3:
        return OsRelease()

    return OsRelease(
        distribution=lines[0] or None,
        version=lines[1] or None,
        pretty_name=lines[2] or None,
    )


def optional_stdout(result: CommandResult, errors: list[str]) -> str | None:
    if result.ok:
        return result.stdout

    errors.append(format_error(result))
    return None


def inspect_disk(run: Callable[[str], CommandResult]) -> DiskState:
    result = run("df -Pm / | awk 'NR==2 {print $2,$3,$4,$5}'")
    if not result.ok:
        return DiskState()

    parts = result.stdout.replace("%", "").split()
    if len(parts) != 4:
        return DiskState()

    try:
        total, used, available, used_percent = [int(part) for part in parts]
    except ValueError:
        return DiskState()

    return DiskState(
        totalMiB=total,
        usedMiB=used,
        availableMiB=available,
        usedPercent=used_percent,
    )


def inspect_cpu(run: Callable[[str], CommandResult]) -> CpuState:
    cores_result = run("getconf _NPROCESSORS_ONLN")
    usage_result = run(CPU_USAGE_COMMAND)

    cores: int | None = None
    if cores_result.ok:
        try:
            cores = int(cores_result.stdout.strip())
        except ValueError:
            cores = None

    usage_percent = parse_cpu_usage(usage_result.stdout) if usage_result.ok else None

    return CpuState(cores=cores, usagePercent=usage_percent)


def parse_cpu_usage(stdout: str) -> float | None:
    lines = stdout.splitlines()
    if len(lines) < 2:
        return None

    try:
        idle1, total1 = [int(value) for value in lines[0].split()]
        idle2, total2 = [int(value) for value in lines[1].split()]
    except ValueError:
        return None

    total_delta = total2 - total1
    idle_delta = idle2 - idle1
    if total_delta <= 0:
        return None

    return round(100 * (total_delta - idle_delta) / total_delta, 1)


def inspect_memory(run: Callable[[str], CommandResult]) -> MemoryState:
    result = run(
        "awk '/MemTotal:/ {total=$2} /MemAvailable:/ {available=$2} "
        "END {print int(total/1024), int(available/1024)}' /proc/meminfo"
    )
    if not result.ok:
        return MemoryState()

    parts = result.stdout.split()
    if len(parts) != 2:
        return MemoryState()

    try:
        total, available = [int(part) for part in parts]
    except ValueError:
        return MemoryState()

    return MemoryState(totalMiB=total, availableMiB=available)


def inspect_apt(run: Callable[[str], CommandResult]) -> AptState:
    if not run("command -v apt-get").ok:
        return AptState(available=False)

    last_update_result = run(APT_LAST_UPDATE_COMMAND)
    upgradable_result = run(APT_UPGRADABLE_COMMAND)

    last_update: str | None = None
    package_lists_age_seconds: int | None = None
    if last_update_result.ok:
        lines = last_update_result.stdout.splitlines()
        if lines:
            last_update = lines[0]
        if len(lines) >= 2:
            try:
                package_lists_age_seconds = int(lines[1])
            except ValueError:
                package_lists_age_seconds = None

    package_lists_fresh = (
        package_lists_age_seconds <= APT_FRESHNESS_SECONDS
        if package_lists_age_seconds is not None
        else None
    )

    upgradable_packages: int | None = None
    if upgradable_result.ok:
        try:
            upgradable_packages = int(upgradable_result.stdout.strip())
        except ValueError:
            upgradable_packages = None

    system_up_to_date = (
        package_lists_fresh is True and upgradable_packages == 0
        if upgradable_packages is not None
        else None
    )

    return AptState(
        available=True,
        lastUpdate=last_update,
        packageListsAgeSeconds=package_lists_age_seconds,
        packageListsFresh=package_lists_fresh,
        upgradablePackages=upgradable_packages,
        systemUpToDate=system_up_to_date,
    )


def inspect_packages(
    run: Callable[[str], CommandResult], package_names: list[str]
) -> dict[str, bool]:
    packages: dict[str, bool] = {}

    for package_name in package_names:
        result = run(f"dpkg-query -W -f='${{Status}}' {shell_quote(package_name)}")
        packages[package_name] = result.ok and result.stdout == "install ok installed"

    return packages


def inspect_sysctl(
    run: Callable[[str], CommandResult], sysctl_keys: list[str]
) -> dict[str, str | None]:
    values: dict[str, str | None] = {}

    for key in sysctl_keys:
        result = run(f"sysctl -n {shell_quote(key)}")
        values[key] = result.stdout.strip() if result.ok else None

    return values


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def inspect_k3s(run: Callable[[str], CommandResult], has_systemd: bool) -> K3sState:
    k3s_path = run("command -v k3s")
    if not k3s_path.ok:
        return K3sState(installed=False)

    version_result = run("k3s --version | head -n 1")
    service_active: bool | None = None
    service_enabled: bool | None = None

    if has_systemd:
        service_active = run("systemctl is-active --quiet k3s").ok
        service_enabled = run("systemctl is-enabled --quiet k3s").ok

    return K3sState(
        installed=True,
        version=version_result.stdout if version_result.ok else None,
        serviceActive=service_active,
        serviceEnabled=service_enabled,
    )


def format_error(result: CommandResult) -> str:
    detail = result.stderr or result.stdout or "no output"
    return f"{result.command} failed with exit code {result.return_code}: {detail}"
