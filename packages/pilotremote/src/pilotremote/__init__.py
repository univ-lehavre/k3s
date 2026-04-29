"""Remote execution adapters for pilot."""

from pilotremote.actions import EnsurePackagePresent, SetSysctlValue, WriteRemoteFile
from pilotremote.executor import CommandResult, RemoteExecutor, SshExecutor
from pilotremote.inspect import inspect_machine

__all__ = [
    "CommandResult",
    "EnsurePackagePresent",
    "RemoteExecutor",
    "SetSysctlValue",
    "SshExecutor",
    "WriteRemoteFile",
    "inspect_machine",
]
