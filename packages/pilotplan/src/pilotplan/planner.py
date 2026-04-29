from dataclasses import dataclass

from pilotplan.manifest import DesiredState
from pilotplan.observed import ObservedState


@dataclass(frozen=True)
class PlannedAction:
    id: str
    description: str
    risk: str = "low"
    rollback: str = "none"


@dataclass(frozen=True)
class Plan:
    target: str
    actions: list[PlannedAction]

    @property
    def empty(self) -> bool:
        return not self.actions


def build_initial_plan(desired: DesiredState) -> Plan:
    actions: list[PlannedAction] = []

    for package in desired.spec.system.packages.present:
        actions.append(
            PlannedAction(
                id=f"package.present.{package}",
                description=f"Ensure package {package} is present",
                rollback="none",
            )
        )

    for key, value in desired.spec.system.sysctl.items():
        actions.append(
            PlannedAction(
                id=f"sysctl.{key}",
                description=f"Set sysctl {key} = {value}",
                rollback="reversible",
            )
        )

    if desired.spec.k3s.state == "present":
        version = desired.spec.k3s.version or desired.spec.k3s.install.channel
        actions.extend(
            [
                *_plan_networking(desired),
                PlannedAction(
                    id="k3s.config.write",
                    description="Write /etc/rancher/k3s/config.yaml",
                    rollback="reversible",
                ),
                PlannedAction(
                    id="k3s.install",
                    description=f"Install k3s {version}",
                    risk="medium",
                    rollback="compensating",
                ),
                PlannedAction(
                    id="systemd.k3s.enable",
                    description="Enable k3s service",
                    rollback="reversible",
                ),
                PlannedAction(
                    id="systemd.k3s.start",
                    description="Start k3s service",
                    rollback="reversible",
                ),
                PlannedAction(
                    id="k3s.node.ready",
                    description="Wait for node Ready",
                    rollback="none",
                ),
                PlannedAction(
                    id="k3s.kubeconfig.fetch",
                    description="Fetch kubeconfig",
                    rollback="reversible",
                ),
            ]
        )
    else:
        actions.append(
            PlannedAction(
                id="k3s.uninstall",
                description="Uninstall k3s",
                risk="high" if desired.spec.k3s.uninstall.removeData else "medium",
                rollback="compensating",
            )
        )

    return Plan(target=desired.metadata.name, actions=actions)


def build_plan(desired: DesiredState, observed: ObservedState | None = None) -> Plan:
    if observed is None:
        return build_initial_plan(desired)

    actions: list[PlannedAction] = []

    if not observed.sshAvailable:
        actions.append(
            PlannedAction(
                id="ssh.unavailable",
                description="Fix SSH connectivity before applying changes",
                risk="high",
                rollback="none",
            )
        )
        return Plan(target=desired.metadata.name, actions=actions)

    actions.extend(plan_system_prerequisites(desired, observed))

    if desired.spec.k3s.state == "present":
        actions.extend(plan_k3s_present(desired, observed))
    else:
        actions.extend(plan_k3s_absent(desired, observed))

    return Plan(target=desired.metadata.name, actions=actions)


def plan_system_prerequisites(
    desired: DesiredState,
    observed: ObservedState | None = None,
) -> list[PlannedAction]:
    actions: list[PlannedAction] = []

    for package in desired.spec.system.packages.present:
        if observed is not None and observed.system.packages.get(package) is True:
            continue

        actions.append(
            PlannedAction(
                id=f"package.present.{package}",
                description=f"Ensure package {package} is present",
                rollback="none",
            )
        )

    for key, value in desired.spec.system.sysctl.items():
        if observed is not None and observed.system.sysctl.get(key) == value:
            continue

        actions.append(
            PlannedAction(
                id=f"sysctl.{key}",
                description=f"Set sysctl {key} = {value}",
                rollback="reversible",
            )
        )

    return actions


def _plan_networking(desired: DesiredState) -> list[PlannedAction]:
    if desired.spec.networking.cni != "cilium":
        return []

    cilium = desired.spec.networking.cilium
    return [
        PlannedAction(
            id="cilium.helmchart.write",
            description=f"Write Cilium HelmChart manifest (v{cilium.version})",
            rollback="reversible",
        )
    ]


def plan_k3s_present(desired: DesiredState, observed: ObservedState) -> list[PlannedAction]:
    actions: list[PlannedAction] = []
    version = desired.spec.k3s.version or desired.spec.k3s.install.channel

    actions.extend(_plan_networking(desired))
    actions.append(
        PlannedAction(
            id="k3s.config.write",
            description="Write /etc/rancher/k3s/config.yaml",
            rollback="reversible",
        )
    )

    if not observed.k3s.installed:
        actions.append(
            PlannedAction(
                id="k3s.install",
                description=f"Install k3s {version}",
                risk="medium",
                rollback="compensating",
            )
        )
    elif desired.spec.k3s.version is not None and desired.spec.k3s.version not in (
        observed.k3s.version or ""
    ):
        actions.append(
            PlannedAction(
                id="k3s.upgrade",
                description=f"Change k3s version to {desired.spec.k3s.version}",
                risk="high",
                rollback="compensating",
            )
        )

    if desired.spec.k3s.service.enabled and observed.k3s.serviceEnabled is not True:
        actions.append(
            PlannedAction(
                id="systemd.k3s.enable",
                description="Enable k3s service",
                rollback="reversible",
            )
        )

    if desired.spec.k3s.service.running and observed.k3s.serviceActive is not True:
        actions.append(
            PlannedAction(
                id="systemd.k3s.start",
                description="Start k3s service",
                rollback="reversible",
            )
        )

    actions.append(
        PlannedAction(
            id="k3s.node.ready",
            description="Wait for node Ready",
            rollback="none",
        )
    )
    actions.append(
        PlannedAction(
            id="k3s.kubeconfig.fetch",
            description="Fetch kubeconfig",
            rollback="reversible",
        )
    )

    return actions


def plan_k3s_absent(desired: DesiredState, observed: ObservedState) -> list[PlannedAction]:
    if not observed.k3s.installed:
        return []

    return [
        PlannedAction(
            id="k3s.uninstall",
            description="Uninstall k3s",
            risk="high" if desired.spec.k3s.uninstall.removeData else "medium",
            rollback="compensating",
        )
    ]
