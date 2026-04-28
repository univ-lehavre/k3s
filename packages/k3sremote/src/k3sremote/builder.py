from io import StringIO
from pathlib import Path

from k3splan.actions import Action
from k3splan.manifest import DesiredState
from k3splan.planner import Plan
from ruamel.yaml import YAML

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
from k3sremote.executor import RemoteExecutor


def build_actions(
    desired: DesiredState,
    plan: Plan,
    executor: RemoteExecutor,
) -> tuple[list[Action], list[str]]:
    """Return (executable actions, skipped action ids not yet implemented)."""
    actions: list[Action] = []
    skipped: list[str] = []

    for planned in plan.actions:
        action = _build_action(planned.id, desired, executor)
        if action is not None:
            actions.append(action)
        else:
            skipped.append(planned.id)

    return actions, skipped


def _build_action(action_id: str, desired: DesiredState, executor: RemoteExecutor) -> Action | None:
    if action_id.startswith("package.present."):
        return EnsurePackagePresent(executor, action_id[len("package.present.") :])

    if action_id.startswith("sysctl."):
        key = action_id[len("sysctl.") :]
        value = desired.spec.system.sysctl.get(key, "")
        return SetSysctlValue(executor, key, value)

    if action_id == "cilium.helmchart.write":
        content = _render_cilium_helmchart(desired)
        return WriteRemoteFile(
            executor, "/var/lib/rancher/k3s/server/manifests/cilium.yaml", content
        )

    if action_id == "k3s.config.write":
        content = _render_k3s_config(desired)
        return WriteRemoteFile(executor, "/etc/rancher/k3s/config.yaml", content)

    if action_id in ("k3s.install", "k3s.upgrade"):
        return InstallK3s(executor, desired.spec.k3s.version, desired.spec.k3s.install.channel)

    if action_id == "systemd.k3s.enable":
        return SystemdServiceEnable(executor, "k3s")

    if action_id == "systemd.k3s.start":
        return SystemdServiceStart(executor, "k3s")

    if action_id == "k3s.node.ready":
        timeout = desired.spec.execution.verify.timeoutSeconds
        return WaitK3sNodeReady(executor, desired.metadata.name, timeout)

    if action_id == "k3s.kubeconfig.fetch":
        return FetchKubeconfig(executor, Path("k3s.yaml"))

    if action_id == "k3s.uninstall":
        uninstall = desired.spec.k3s.uninstall
        return UninstallK3s(
            executor,
            remove_data=uninstall.removeData,
            remove_kubeconfig=uninstall.removeKubeconfig,
            local_kubeconfig=Path("k3s.yaml") if uninstall.removeKubeconfig else None,
        )

    return None


def _render_k3s_config(desired: DesiredState) -> str:
    config = dict(desired.spec.k3s.config)
    if desired.spec.networking.cni == "cilium":
        config["flannel-backend"] = "none"
        if desired.spec.networking.cilium.kubeProxyReplacement:
            config["disable-kube-proxy"] = True

    yaml = YAML()
    yaml.default_flow_style = False
    stream = StringIO()
    yaml.dump(config, stream)
    return stream.getvalue()


def _render_cilium_helmchart(desired: DesiredState) -> str:
    cilium = desired.spec.networking.cilium
    values = dict(cilium.helmValues)
    if cilium.kubeProxyReplacement:
        values.setdefault("kubeProxyReplacement", True)

    yaml = YAML()
    yaml.default_flow_style = False
    stream = StringIO()
    yaml.dump(
        {
            "apiVersion": "helm.cattle.io/v1",
            "kind": "HelmChart",
            "metadata": {"name": "cilium", "namespace": "kube-system"},
            "spec": {
                "repo": "https://helm.cilium.io/",
                "chart": "cilium",
                "version": cilium.version,
                "targetNamespace": "kube-system",
                "valuesContent": _render_values_content(values),
            },
        },
        stream,
    )
    return stream.getvalue()


def _render_values_content(values: dict[str, object]) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    stream = StringIO()
    yaml.dump(values, stream)
    return stream.getvalue()
