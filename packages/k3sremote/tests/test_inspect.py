from k3sremote import CommandResult, inspect_machine


class FakeExecutor:
    def __init__(self, results: dict[str, CommandResult]) -> None:
        self.results = results

    def run(self, command: str) -> CommandResult:
        return self.results.get(command, CommandResult(command, "", "not found", 127))


def ok(command: str, stdout: str = "") -> CommandResult:
    return CommandResult(command=command, stdout=stdout, stderr="", return_code=0)


def fail(command: str, stderr: str = "failed") -> CommandResult:
    return CommandResult(command=command, stdout="", stderr=stderr, return_code=1)


def test_inspect_machine_collects_system_and_k3s_state() -> None:
    executor = FakeExecutor(
        {
            "true": ok("true"),
            "uname -s": ok("uname -s", "Linux"),
            "uname -m": ok("uname -m", "aarch64"),
            "command -v systemctl": ok("command -v systemctl", "/usr/bin/systemctl"),
            "df -Pm / | awk 'NR==2 {print $2,$3,$4,$5}'": ok(
                "df -Pm / | awk 'NR==2 {print $2,$3,$4,$5}'",
                "10000 4000 6000 40%",
            ),
            "awk '/MemTotal:/ {total=$2} /MemAvailable:/ {available=$2} "
            "END {print int(total/1024), int(available/1024)}' /proc/meminfo": ok(
                "awk",
                "2048 1024",
            ),
            "command -v k3s": ok("command -v k3s", "/usr/local/bin/k3s"),
            "k3s --version | head -n 1": ok(
                "k3s --version | head -n 1",
                "k3s version v1.30.5+k3s1",
            ),
            "systemctl is-active --quiet k3s": ok("systemctl is-active --quiet k3s"),
            "systemctl is-enabled --quiet k3s": ok("systemctl is-enabled --quiet k3s"),
        }
    )

    observed = inspect_machine("prod-1", executor)

    assert observed.sshAvailable is True
    assert observed.system.os == "Linux"
    assert observed.system.architecture == "aarch64"
    assert observed.system.systemd is True
    assert observed.system.disk.usedPercent == 40
    assert observed.system.memory.availableMiB == 1024
    assert observed.k3s.installed is True
    assert observed.k3s.version == "k3s version v1.30.5+k3s1"
    assert observed.k3s.serviceActive is True
    assert observed.k3s.serviceEnabled is True
    assert '"target":"prod-1"' in observed.model_dump_json()


def test_inspect_machine_handles_unavailable_ssh() -> None:
    observed = inspect_machine("prod-1", FakeExecutor({"true": fail("true", "connection failed")}))

    assert observed.sshAvailable is False
    assert observed.errors == ["true failed with exit code 1: connection failed"]


def test_inspect_machine_handles_missing_k3s() -> None:
    executor = FakeExecutor(
        {
            "true": ok("true"),
            "uname -s": ok("uname -s", "Linux"),
            "uname -m": ok("uname -m", "x86_64"),
            "command -v systemctl": ok("command -v systemctl", "/usr/bin/systemctl"),
            "command -v k3s": fail("command -v k3s"),
        }
    )

    observed = inspect_machine("prod-1", executor)

    assert observed.sshAvailable is True
    assert observed.k3s.installed is False
    assert observed.k3s.version is None
