import base64
import shlex
from pathlib import Path, PurePosixPath

from k3splan.actions import Action, RiskLevel, RollbackMode

from k3sremote.executor import RemoteExecutor


class EnsurePackagePresent(Action):
    def __init__(self, executor: RemoteExecutor, package: str) -> None:
        self._executor = executor
        self._package = package

    @property
    def id(self) -> str:
        return f"package.present.{self._package}"

    @property
    def description(self) -> str:
        return f"Ensure package {self._package} is present"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "compensating"

    def _is_installed(self) -> bool:
        result = self._executor.run(f"dpkg-query -W -f='${{Status}}' {shlex.quote(self._package)}")
        return result.ok and "install ok installed" in result.stdout

    def snapshot(self) -> bool:
        return self._is_installed()

    def apply(self) -> None:
        self._executor.run(
            f"DEBIAN_FRONTEND=noninteractive apt-get install -y {shlex.quote(self._package)}"
        )

    def verify(self) -> bool:
        return self._is_installed()

    def rollback(self, snapshot: object) -> None:
        if not snapshot:
            self._executor.run(
                f"DEBIAN_FRONTEND=noninteractive apt-get remove -y {shlex.quote(self._package)}"
            )


class WriteRemoteFile(Action):
    def __init__(self, executor: RemoteExecutor, path: str, content: str) -> None:
        self._executor = executor
        self._path = path
        self._content = content

    @property
    def id(self) -> str:
        return f"file.write.{PurePosixPath(self._path).name}"

    @property
    def description(self) -> str:
        return f"Write {self._path}"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "reversible"

    def snapshot(self) -> str | None:
        result = self._executor.run(f"cat {shlex.quote(self._path)} 2>/dev/null")
        return result.stdout if result.ok else None

    def apply(self) -> None:
        content_b64 = base64.b64encode(self._content.encode()).decode()
        self._executor.run(
            f"mkdir -p {shlex.quote(str(PurePosixPath(self._path).parent))}"
            f" && echo {shlex.quote(content_b64)} | base64 -d > {shlex.quote(self._path)}"
        )

    def verify(self) -> bool:
        result = self._executor.run(f"cat {shlex.quote(self._path)} 2>/dev/null")
        return result.ok and result.stdout == self._content

    def rollback(self, snapshot: object) -> None:
        if snapshot is None:
            self._executor.run(f"rm -f {shlex.quote(self._path)}")
        else:
            content_b64 = base64.b64encode(str(snapshot).encode()).decode()
            self._executor.run(
                f"echo {shlex.quote(content_b64)} | base64 -d > {shlex.quote(self._path)}"
            )


class SetSysctlValue(Action):
    def __init__(self, executor: RemoteExecutor, key: str, value: str) -> None:
        self._executor = executor
        self._key = key
        self._value = value

    @property
    def id(self) -> str:
        return f"sysctl.{self._key}"

    @property
    def description(self) -> str:
        return f"Set sysctl {self._key} = {self._value}"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "reversible"

    def _current_value(self) -> str | None:
        result = self._executor.run(f"sysctl -n {shlex.quote(self._key)}")
        return result.stdout if result.ok else None

    def snapshot(self) -> str | None:
        return self._current_value()

    def apply(self) -> None:
        self._executor.run(f"sysctl -w {shlex.quote(self._key + '=' + self._value)}")

    def verify(self) -> bool:
        return self._current_value() == self._value

    def rollback(self, snapshot: object) -> None:
        if snapshot is not None:
            self._executor.run(f"sysctl -w {shlex.quote(self._key + '=' + str(snapshot))}")


class InstallK3s(Action):
    def __init__(
        self, executor: RemoteExecutor, version: str | None, channel: str = "stable"
    ) -> None:
        self._executor = executor
        self._version = version
        self._channel = channel

    @property
    def id(self) -> str:
        return "k3s.install"

    @property
    def description(self) -> str:
        label = self._version or f"channel:{self._channel}"
        return f"Install k3s {label}"

    @property
    def risk(self) -> RiskLevel:
        return "medium"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "compensating"

    def snapshot(self) -> str | None:
        result = self._executor.run("command -v k3s")
        if not result.ok:
            return None
        version = self._executor.run("k3s --version | head -n 1")
        return version.stdout if version.ok else None

    def apply(self) -> None:
        if self._version:
            env = f"INSTALL_K3S_VERSION={shlex.quote(self._version)}"
        else:
            env = f"INSTALL_K3S_CHANNEL={shlex.quote(self._channel)}"
        self._executor.run(f"curl -sfL https://get.k3s.io | {env} sh -")

    def verify(self) -> bool:
        return self._executor.run("command -v k3s").ok

    def rollback(self, snapshot: object) -> None:
        if snapshot is None:
            self._executor.run("/usr/local/bin/k3s-uninstall.sh")


class SystemdServiceEnable(Action):
    def __init__(self, executor: RemoteExecutor, service: str) -> None:
        self._executor = executor
        self._service = service

    @property
    def id(self) -> str:
        return f"systemd.{self._service}.enable"

    @property
    def description(self) -> str:
        return f"Enable {self._service} service"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "reversible"

    def _is_enabled(self) -> bool:
        return self._executor.run(f"systemctl is-enabled --quiet {shlex.quote(self._service)}").ok

    def snapshot(self) -> bool:
        return self._is_enabled()

    def apply(self) -> None:
        self._executor.run(f"systemctl enable {shlex.quote(self._service)}")

    def verify(self) -> bool:
        return self._is_enabled()

    def rollback(self, snapshot: object) -> None:
        if not snapshot:
            self._executor.run(f"systemctl disable {shlex.quote(self._service)}")


class SystemdServiceStart(Action):
    def __init__(self, executor: RemoteExecutor, service: str) -> None:
        self._executor = executor
        self._service = service

    @property
    def id(self) -> str:
        return f"systemd.{self._service}.start"

    @property
    def description(self) -> str:
        return f"Start {self._service} service"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "reversible"

    def _is_active(self) -> bool:
        return self._executor.run(f"systemctl is-active --quiet {shlex.quote(self._service)}").ok

    def snapshot(self) -> bool:
        return self._is_active()

    def apply(self) -> None:
        self._executor.run(f"systemctl start {shlex.quote(self._service)}")

    def verify(self) -> bool:
        return self._is_active()

    def rollback(self, snapshot: object) -> None:
        if not snapshot:
            self._executor.run(f"systemctl stop {shlex.quote(self._service)}")


class WaitK3sNodeReady(Action):
    def __init__(self, executor: RemoteExecutor, node: str, timeout_seconds: int = 120) -> None:
        self._executor = executor
        self._node = node
        self._timeout = timeout_seconds

    @property
    def id(self) -> str:
        return "k3s.node.ready"

    @property
    def description(self) -> str:
        return "Wait for node Ready"

    def snapshot(self) -> None:
        return None

    def apply(self) -> None:
        node_q = shlex.quote(self._node)
        self._executor.run(
            f"timeout {self._timeout} bash -c "
            f"'until k3s kubectl get node {node_q} --no-headers 2>/dev/null"
            f' | grep -q " Ready "; do sleep 2; done\''
        )

    def verify(self) -> bool:
        node_q = shlex.quote(self._node)
        return self._executor.run(
            f"k3s kubectl get node {node_q} --no-headers 2>/dev/null | grep -q ' Ready '"
        ).ok


class FetchKubeconfig(Action):
    def __init__(self, executor: RemoteExecutor, local_path: Path) -> None:
        self._executor = executor
        self._local_path = local_path

    @property
    def id(self) -> str:
        return "k3s.kubeconfig.fetch"

    @property
    def description(self) -> str:
        return f"Fetch kubeconfig to {self._local_path}"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "reversible"

    def snapshot(self) -> str | None:
        if self._local_path.exists():
            return self._local_path.read_text(encoding="utf-8")
        return None

    def apply(self) -> None:
        result = self._executor.run("cat /etc/rancher/k3s/k3s.yaml")
        if result.ok:
            self._local_path.parent.mkdir(parents=True, exist_ok=True)
            self._local_path.write_text(result.stdout, encoding="utf-8")

    def verify(self) -> bool:
        return self._local_path.exists()

    def rollback(self, snapshot: object) -> None:
        if snapshot is None:
            self._local_path.unlink(missing_ok=True)
        else:
            self._local_path.write_text(str(snapshot), encoding="utf-8")


class UninstallK3s(Action):
    def __init__(
        self,
        executor: RemoteExecutor,
        remove_data: bool = False,
        remove_kubeconfig: bool = False,
        local_kubeconfig: Path | None = None,
    ) -> None:
        self._executor = executor
        self._remove_data = remove_data
        self._remove_kubeconfig = remove_kubeconfig
        self._local_kubeconfig = local_kubeconfig

    @property
    def id(self) -> str:
        return "k3s.uninstall"

    @property
    def description(self) -> str:
        return "Uninstall k3s"

    @property
    def risk(self) -> RiskLevel:
        return "high" if self._remove_data else "medium"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "none"

    def snapshot(self) -> str | None:
        result = self._executor.run("k3s --version | head -n 1")
        return result.stdout if result.ok else None

    def apply(self) -> None:
        if self._remove_data:
            self._executor.run("/usr/local/bin/k3s-uninstall.sh")
        else:
            self._executor.run("systemctl stop k3s 2>/dev/null || true")
            self._executor.run("systemctl disable k3s 2>/dev/null || true")
            self._executor.run("rm -f /usr/local/bin/k3s")
            self._executor.run("rm -f /etc/systemd/system/k3s.service")
            self._executor.run("systemctl daemon-reload")

        if self._remove_kubeconfig and self._local_kubeconfig is not None:
            self._local_kubeconfig.unlink(missing_ok=True)

    def verify(self) -> bool:
        return not self._executor.run("command -v k3s").ok
