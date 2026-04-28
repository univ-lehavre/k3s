"""Remote execution adapters for k3sctl."""

from k3sremote.executor import CommandResult, RemoteExecutor, SshExecutor
from k3sremote.inspect import inspect_machine

__all__ = ["CommandResult", "RemoteExecutor", "SshExecutor", "inspect_machine"]
