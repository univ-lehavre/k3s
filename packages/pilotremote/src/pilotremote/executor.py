from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fabric import Connection as FabricConnection  # type: ignore[import-untyped]
from pilotplan import Connection


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
    def run(self, command: str, stream: bool = False) -> CommandResult: ...


class _LineBuffer:
    """Accumulates streamed text line by line, calling a callback for each complete line."""

    def __init__(self, callback: Callable[[str], None] | None = None) -> None:
        self._callback = callback
        self._partial = ""
        self._lines: list[str] = []

    def write(self, data: str) -> int:
        self._partial += data
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            self._lines.append(line)
            if self._callback:
                self._callback(line)
        return len(data)

    def flush(self) -> None:
        pass

    @property
    def content(self) -> str:
        parts = self._lines[:]
        if self._partial:
            parts.append(self._partial)
        return "\n".join(parts)


class SshExecutor:
    def __init__(
        self,
        connection: Connection,
        on_output: Callable[[str], None] | None = None,
    ) -> None:
        connect_kwargs: dict[str, str] = {}
        if connection.identityFile is not None:
            connect_kwargs["key_filename"] = expand_identity_file(connection.identityFile)

        self._connection = FabricConnection(
            host=connection.host,
            user=connection.user,
            port=connection.port,
            connect_kwargs=connect_kwargs,
        )
        self._on_output = on_output

    def run(self, command: str, stream: bool = False) -> CommandResult:
        callback = self._on_output if stream else None
        out_buf = _LineBuffer(callback)
        err_buf = _LineBuffer(callback)
        try:
            result = self._connection.run(
                command,
                hide=True,
                warn=True,
                out_stream=out_buf,
                err_stream=err_buf,
            )
        except Exception as exc:
            return CommandResult(
                command=command, stdout=out_buf.content, stderr=str(exc), return_code=1
            )

        return CommandResult(
            command=command,
            stdout=out_buf.content,
            stderr=err_buf.content,
            return_code=result.return_code,
        )


def expand_identity_file(identity_file: str) -> str:
    return str(Path(identity_file).expanduser())
