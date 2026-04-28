from pathlib import Path

from k3sremote import CommandResult
from k3sremote.actions import (
    EnsurePackagePresent,
    FetchKubeconfig,
    InstallK3s,
    SetSysctlValue,
    SystemdServiceEnable,
    SystemdServiceStart,
    UninstallK3s,
    WaitK3sNodeReady,
    WriteRemoteFile,
)


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


# --- InstallK3s ---


def test_install_k3s_snapshot_absent() -> None:
    executor = FakeExecutor({"command -v k3s": fail("")})
    assert InstallK3s(executor, "v1.35.3+k3s1").snapshot() is None


def test_install_k3s_snapshot_installed() -> None:
    executor = FakeExecutor(
        {
            "command -v k3s": ok("", "/usr/local/bin/k3s"),
            "k3s --version | head -n 1": ok("", "k3s version v1.35.3+k3s1"),
        }
    )
    assert InstallK3s(executor, "v1.35.3+k3s1").snapshot() == "k3s version v1.35.3+k3s1"


def test_install_k3s_apply_uses_version_env() -> None:
    executor = FakeExecutor()
    InstallK3s(executor, "v1.35.3+k3s1").apply()
    assert any("INSTALL_K3S_VERSION" in cmd and "v1.35.3" in cmd for cmd in executor.calls)


def test_install_k3s_apply_uses_channel_when_no_version() -> None:
    executor = FakeExecutor()
    InstallK3s(executor, None, channel="stable").apply()
    assert any("INSTALL_K3S_CHANNEL" in cmd and "stable" in cmd for cmd in executor.calls)


def test_install_k3s_verify_ok() -> None:
    executor = FakeExecutor({"command -v k3s": ok("", "/usr/local/bin/k3s")})
    assert InstallK3s(executor, None).verify() is True


def test_install_k3s_rollback_uninstalls_when_not_preexisting() -> None:
    executor = FakeExecutor()
    InstallK3s(executor, None).rollback(None)
    assert any("k3s-uninstall.sh" in cmd for cmd in executor.calls)


def test_install_k3s_rollback_noop_when_preexisting() -> None:
    executor = FakeExecutor()
    InstallK3s(executor, None).rollback("k3s version v1.30.0+k3s1")
    assert not executor.calls


# --- SystemdServiceEnable ---


def test_systemd_enable_snapshot_enabled() -> None:
    executor = FakeExecutor({"systemctl is-enabled --quiet k3s": ok("")})
    assert SystemdServiceEnable(executor, "k3s").snapshot() is True


def test_systemd_enable_apply() -> None:
    executor = FakeExecutor()
    SystemdServiceEnable(executor, "k3s").apply()
    assert any("systemctl enable" in cmd and "k3s" in cmd for cmd in executor.calls)


def test_systemd_enable_rollback_disables_when_not_preexisting() -> None:
    executor = FakeExecutor()
    SystemdServiceEnable(executor, "k3s").rollback(False)
    assert any("systemctl disable" in cmd for cmd in executor.calls)


def test_systemd_enable_rollback_noop_when_preexisting() -> None:
    executor = FakeExecutor()
    SystemdServiceEnable(executor, "k3s").rollback(True)
    assert not executor.calls


# --- SystemdServiceStart ---


def test_systemd_start_snapshot_active() -> None:
    executor = FakeExecutor({"systemctl is-active --quiet k3s": ok("")})
    assert SystemdServiceStart(executor, "k3s").snapshot() is True


def test_systemd_start_apply() -> None:
    executor = FakeExecutor()
    SystemdServiceStart(executor, "k3s").apply()
    assert any("systemctl start" in cmd and "k3s" in cmd for cmd in executor.calls)


def test_systemd_start_rollback_stops_when_not_preexisting() -> None:
    executor = FakeExecutor()
    SystemdServiceStart(executor, "k3s").rollback(False)
    assert any("systemctl stop" in cmd for cmd in executor.calls)


# --- WaitK3sNodeReady ---


def test_wait_node_ready_apply_runs_timeout_loop() -> None:
    executor = FakeExecutor()
    WaitK3sNodeReady(executor, "prod-1", 60).apply()
    assert any("timeout 60" in cmd and "prod-1" in cmd for cmd in executor.calls)


def test_wait_node_ready_verify_ok() -> None:
    executor = FakeExecutor(
        {"k3s kubectl get node prod-1 --no-headers 2>/dev/null | grep -q ' Ready '": ok("")}
    )
    assert WaitK3sNodeReady(executor, "prod-1").verify() is True


def test_wait_node_ready_verify_fails() -> None:
    executor = FakeExecutor(
        {"k3s kubectl get node prod-1 --no-headers 2>/dev/null | grep -q ' Ready '": fail("")}
    )
    assert WaitK3sNodeReady(executor, "prod-1").verify() is False


# --- FetchKubeconfig ---


def test_fetch_kubeconfig_snapshot_existing(tmp_path: Path) -> None:
    kubeconfig = tmp_path / "k3s.yaml"
    kubeconfig.write_text("existing", encoding="utf-8")
    assert FetchKubeconfig(FakeExecutor(), kubeconfig).snapshot() == "existing"


def test_fetch_kubeconfig_snapshot_absent(tmp_path: Path) -> None:
    assert FetchKubeconfig(FakeExecutor(), tmp_path / "k3s.yaml").snapshot() is None


def test_fetch_kubeconfig_apply_writes_local_file(tmp_path: Path) -> None:
    executor = FakeExecutor({"cat /etc/rancher/k3s/k3s.yaml": ok("", "kubeconfig-content")})
    kubeconfig = tmp_path / "k3s.yaml"
    FetchKubeconfig(executor, kubeconfig).apply()
    assert kubeconfig.read_text(encoding="utf-8") == "kubeconfig-content"


def test_fetch_kubeconfig_verify_ok(tmp_path: Path) -> None:
    kubeconfig = tmp_path / "k3s.yaml"
    kubeconfig.write_text("x", encoding="utf-8")
    assert FetchKubeconfig(FakeExecutor(), kubeconfig).verify() is True


def test_fetch_kubeconfig_rollback_deletes_when_absent(tmp_path: Path) -> None:
    kubeconfig = tmp_path / "k3s.yaml"
    kubeconfig.write_text("x", encoding="utf-8")
    FetchKubeconfig(FakeExecutor(), kubeconfig).rollback(None)
    assert not kubeconfig.exists()


def test_fetch_kubeconfig_rollback_restores_content(tmp_path: Path) -> None:
    kubeconfig = tmp_path / "k3s.yaml"
    FetchKubeconfig(FakeExecutor(), kubeconfig).rollback("old-content")
    assert kubeconfig.read_text(encoding="utf-8") == "old-content"


# --- UninstallK3s ---


def test_uninstall_k3s_snapshot_returns_version() -> None:
    executor = FakeExecutor({"k3s --version | head -n 1": ok("", "k3s version v1.35.3+k3s1")})
    assert UninstallK3s(executor).snapshot() == "k3s version v1.35.3+k3s1"


def test_uninstall_k3s_apply_runs_uninstall_script_when_remove_data() -> None:
    executor = FakeExecutor()
    UninstallK3s(executor, remove_data=True).apply()
    assert any("k3s-uninstall.sh" in cmd for cmd in executor.calls)


def test_uninstall_k3s_apply_keeps_data_directory() -> None:
    executor = FakeExecutor()
    UninstallK3s(executor, remove_data=False).apply()
    assert not any("k3s-uninstall.sh" in cmd for cmd in executor.calls)
    assert any("rm -f /usr/local/bin/k3s" in cmd for cmd in executor.calls)


def test_uninstall_k3s_apply_removes_kubeconfig(tmp_path: Path) -> None:
    kubeconfig = tmp_path / "k3s.yaml"
    kubeconfig.write_text("x", encoding="utf-8")
    UninstallK3s(FakeExecutor(), remove_kubeconfig=True, local_kubeconfig=kubeconfig).apply()
    assert not kubeconfig.exists()


def test_uninstall_k3s_verify_ok_when_absent() -> None:
    executor = FakeExecutor({"command -v k3s": fail("")})
    assert UninstallK3s(executor).verify() is True


def test_uninstall_k3s_verify_fails_when_still_present() -> None:
    executor = FakeExecutor({"command -v k3s": ok("", "/usr/local/bin/k3s")})
    assert UninstallK3s(executor).verify() is False


def test_uninstall_k3s_risk_high_when_remove_data() -> None:
    assert UninstallK3s(FakeExecutor(), remove_data=True).risk == "high"


def test_uninstall_k3s_risk_medium_when_keep_data() -> None:
    assert UninstallK3s(FakeExecutor(), remove_data=False).risk == "medium"
