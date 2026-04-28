from collections.abc import Callable

from k3splan import DiskState, K3sState, MemoryState, ObservedState, SystemState

from k3sremote.executor import CommandResult, RemoteExecutor


def inspect_machine(target: str, executor: RemoteExecutor) -> ObservedState:
    errors: list[str] = []

    probe = executor.run("true")
    if not probe.ok:
        return ObservedState(
            target=target,
            sshAvailable=False,
            errors=[format_error(probe)],
        )

    system = SystemState(
        os=optional_stdout(executor.run("uname -s"), errors),
        architecture=optional_stdout(executor.run("uname -m"), errors),
        systemd=executor.run("command -v systemctl").ok,
        disk=inspect_disk(executor.run),
        memory=inspect_memory(executor.run),
    )
    k3s = inspect_k3s(executor.run, system.systemd)

    return ObservedState(target=target, sshAvailable=True, system=system, k3s=k3s, errors=errors)


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
