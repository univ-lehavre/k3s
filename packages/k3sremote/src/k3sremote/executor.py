from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fabric import Connection as FabricConnection  # type: ignore[import-untyped]
from k3splan import Connection


@dataclass(frozen=True)
class CommandResult:
    command: str
    stdout: str
    stderr: str
    return_code: int

    @property
    def ok(self) -> bool:
        return self.return_code == 0


class RemoteExecutor(Protocol):
    def run(self, command: str) -> CommandResult: ...


class SshExecutor:
    def __init__(self, connection: Connection) -> None:
        connect_kwargs: dict[str, str] = {}
        if connection.identityFile is not None:
            connect_kwargs["key_filename"] = expand_identity_file(connection.identityFile)

        self._connection = FabricConnection(
            host=connection.host,
            user=connection.user,
            port=connection.port,
            connect_kwargs=connect_kwargs,
        )

    def run(self, command: str) -> CommandResult:
        try:
            result = self._connection.run(command, hide=True, warn=True)
        except Exception as exc:
            return CommandResult(command=command, stdout="", stderr=str(exc), return_code=1)

        return CommandResult(
            command=command,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            return_code=result.return_code,
        )


def expand_identity_file(identity_file: str) -> str:
    return str(Path(identity_file).expanduser())
