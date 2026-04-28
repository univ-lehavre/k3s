from k3sremote import CommandResult
from k3sremote.actions import EnsurePackagePresent, SetSysctlValue, WriteRemoteFile


class FakeExecutor:
    def __init__(self, results: dict[str, CommandResult] | None = None) -> None:
        self.results: dict[str, CommandResult] = results or {}
        self.calls: list[str] = []

    def run(self, command: str) -> CommandResult:
        self.calls.append(command)
        return self.results.get(command, CommandResult(command, "", "", 0))


def ok(command: str, stdout: str = "") -> CommandResult:
    return CommandResult(command=command, stdout=stdout, stderr="", return_code=0)


def fail(command: str) -> CommandResult:
    return CommandResult(command=command, stdout="", stderr="failed", return_code=1)


# --- EnsurePackagePresent ---


def test_ensure_package_snapshot_installed() -> None:
    executor = FakeExecutor({"dpkg-query -W -f='${Status}' curl": ok("", "install ok installed")})
    action = EnsurePackagePresent(executor, "curl")
    assert action.snapshot() is True


def test_ensure_package_snapshot_absent() -> None:
    executor = FakeExecutor({"dpkg-query -W -f='${Status}' curl": fail("")})
    action = EnsurePackagePresent(executor, "curl")
    assert action.snapshot() is False


def test_ensure_package_apply_calls_apt() -> None:
    executor = FakeExecutor()
    EnsurePackagePresent(executor, "curl").apply()
    assert any("apt-get install" in cmd and "curl" in cmd for cmd in executor.calls)


def test_ensure_package_verify_returns_true_when_installed() -> None:
    executor = FakeExecutor({"dpkg-query -W -f='${Status}' curl": ok("", "install ok installed")})
    assert EnsurePackagePresent(executor, "curl").verify() is True


def test_ensure_package_rollback_removes_if_not_preexisting() -> None:
    executor = FakeExecutor()
    EnsurePackagePresent(executor, "curl").rollback(False)
    assert any("apt-get remove" in cmd and "curl" in cmd for cmd in executor.calls)


def test_ensure_package_rollback_noop_if_preexisting() -> None:
    executor = FakeExecutor()
    EnsurePackagePresent(executor, "curl").rollback(True)
    assert not executor.calls


# --- WriteRemoteFile ---


def test_write_remote_file_snapshot_existing() -> None:
    executor = FakeExecutor({"cat /etc/foo.conf 2>/dev/null": ok("", "old content")})
    action = WriteRemoteFile(executor, "/etc/foo.conf", "new content")
    assert action.snapshot() == "old content"


def test_write_remote_file_snapshot_absent() -> None:
    executor = FakeExecutor({"cat /etc/foo.conf 2>/dev/null": fail("")})
    action = WriteRemoteFile(executor, "/etc/foo.conf", "new content")
    assert action.snapshot() is None


def test_write_remote_file_apply_writes_base64() -> None:
    executor = FakeExecutor()
    action = WriteRemoteFile(executor, "/etc/foo.conf", "hello")
    action.apply()
    assert any("base64 -d" in cmd and "/etc/foo.conf" in cmd for cmd in executor.calls)


def test_write_remote_file_verify_matches_content() -> None:
    executor = FakeExecutor({"cat /etc/foo.conf 2>/dev/null": ok("", "hello")})
    assert WriteRemoteFile(executor, "/etc/foo.conf", "hello").verify() is True


def test_write_remote_file_verify_fails_on_mismatch() -> None:
    executor = FakeExecutor({"cat /etc/foo.conf 2>/dev/null": ok("", "old")})
    assert WriteRemoteFile(executor, "/etc/foo.conf", "new").verify() is False


def test_write_remote_file_rollback_restores_content() -> None:
    executor = FakeExecutor()
    WriteRemoteFile(executor, "/etc/foo.conf", "new").rollback("old content")
    assert any("base64 -d" in cmd and "/etc/foo.conf" in cmd for cmd in executor.calls)


def test_write_remote_file_rollback_deletes_when_absent() -> None:
    executor = FakeExecutor()
    WriteRemoteFile(executor, "/etc/foo.conf", "new").rollback(None)
    assert any("rm -f" in cmd and "/etc/foo.conf" in cmd for cmd in executor.calls)


# --- SetSysctlValue ---


def test_sysctl_snapshot_returns_current_value() -> None:
    executor = FakeExecutor({"sysctl -n net.ipv4.ip_forward": ok("", "0")})
    assert SetSysctlValue(executor, "net.ipv4.ip_forward", "1").snapshot() == "0"


def test_sysctl_apply_writes_value() -> None:
    executor = FakeExecutor()
    SetSysctlValue(executor, "net.ipv4.ip_forward", "1").apply()
    assert any("sysctl -w" in cmd and "net.ipv4.ip_forward=1" in cmd for cmd in executor.calls)


def test_sysctl_verify_returns_true_when_matches() -> None:
    executor = FakeExecutor({"sysctl -n net.ipv4.ip_forward": ok("", "1")})
    assert SetSysctlValue(executor, "net.ipv4.ip_forward", "1").verify() is True


def test_sysctl_verify_returns_false_on_mismatch() -> None:
    executor = FakeExecutor({"sysctl -n net.ipv4.ip_forward": ok("", "0")})
    assert SetSysctlValue(executor, "net.ipv4.ip_forward", "1").verify() is False


def test_sysctl_rollback_restores_previous_value() -> None:
    executor = FakeExecutor()
    SetSysctlValue(executor, "net.ipv4.ip_forward", "1").rollback("0")
    assert any("sysctl -w" in cmd and "net.ipv4.ip_forward=0" in cmd for cmd in executor.calls)


def test_sysctl_rollback_noop_when_no_previous_value() -> None:
    executor = FakeExecutor()
    SetSysctlValue(executor, "net.ipv4.ip_forward", "1").rollback(None)
    assert not executor.calls
