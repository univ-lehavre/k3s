import base64
import shlex
from pathlib import PurePosixPath

from k3splan.actions import Action, RollbackMode

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
