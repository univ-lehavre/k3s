from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from ruamel.yaml import YAML


class Metadata(BaseModel):
    name: str
    labels: dict[str, str] = Field(default_factory=dict)


class Connection(BaseModel):
    type: Literal["ssh"]
    host: str
    user: str
    port: int = 22
    identityFile: str | None = None


class Inventory(BaseModel):
    connections: dict[str, Connection] = Field(default_factory=dict)


class Packages(BaseModel):
    present: list[str] = Field(default_factory=list)


class System(BaseModel):
    packages: Packages = Field(default_factory=Packages)
    sysctl: dict[str, str] = Field(default_factory=dict)


class CiliumConfig(BaseModel):
    version: str = "1.19.3"
    kubeProxyReplacement: bool = False
    helmValues: dict[str, object] = Field(default_factory=dict)


class Networking(BaseModel):
    cni: Literal["flannel", "cilium"] = "flannel"
    cilium: CiliumConfig = Field(default_factory=CiliumConfig)


class K3sInstall(BaseModel):
    channel: str = "stable"
    method: Literal["official-script"] = "official-script"


class K3sService(BaseModel):
    enabled: bool = True
    running: bool = True


class K3sUninstall(BaseModel):
    removeData: bool = False
    removeKubeconfig: bool = False


class K3s(BaseModel):
    state: Literal["present", "absent"]
    role: Literal["server", "agent"] | None = None
    version: str | None = None
    install: K3sInstall = Field(default_factory=K3sInstall)
    config: dict[str, object] = Field(default_factory=dict)
    service: K3sService = Field(default_factory=K3sService)
    uninstall: K3sUninstall = Field(default_factory=K3sUninstall)


class Health(BaseModel):
    require: list[str] = Field(default_factory=list)
    thresholds: dict[str, int] = Field(default_factory=dict)


class PlanOptions(BaseModel):
    showDiff: bool = True
    includeNoop: bool = False


class VerifyOptions(BaseModel):
    afterEachAction: bool = True
    timeoutSeconds: int = 120


class RollbackOptions(BaseModel):
    enabled: bool = True
    on: list[str] = Field(default_factory=lambda: ["applyFailure", "verifyFailure"])
    requireConfirmFor: list[str] = Field(default_factory=list)
    strategy: str = "reverse-applied-actions"


class JournalOptions(BaseModel):
    location: Literal["local"] = "local"
    path: str = ".k3sp/runs"
    keep: int = 20


class Execution(BaseModel):
    mode: Literal["transactional"] = "transactional"
    plan: PlanOptions = Field(default_factory=PlanOptions)
    verify: VerifyOptions = Field(default_factory=VerifyOptions)
    rollback: RollbackOptions = Field(default_factory=RollbackOptions)
    journal: JournalOptions = Field(default_factory=JournalOptions)


class Spec(BaseModel):
    connection: Connection | None = None
    connectionRef: str | None = None
    system: System = Field(default_factory=System)
    networking: Networking = Field(default_factory=Networking)
    k3s: K3s
    health: Health = Field(default_factory=Health)
    execution: Execution = Field(default_factory=Execution)

    @model_validator(mode="after")
    def validate_connection_source(self) -> "Spec":
        has_inline_connection = self.connection is not None
        has_connection_ref = self.connectionRef is not None

        if has_inline_connection == has_connection_ref:
            raise ValueError("spec must define exactly one of connection or connectionRef")

        return self


class DesiredState(BaseModel):
    apiVersion: Literal["k3s-pilot.dev/v1alpha1"]
    kind: Literal["Machine"]
    metadata: Metadata
    spec: Spec


def load_manifest(path: Path) -> DesiredState:
    yaml = YAML(typ="safe")
    raw = yaml.load(path.read_text(encoding="utf-8"))
    return DesiredState.model_validate(raw)


def load_inventory(path: Path) -> Inventory:
    yaml = YAML(typ="safe")
    raw = yaml.load(path.read_text(encoding="utf-8"))
    return Inventory.model_validate(raw)


def resolve_connection(desired: DesiredState, inventory: Inventory | None = None) -> Connection:
    if desired.spec.connection is not None:
        return desired.spec.connection

    if inventory is None:
        raise ValueError("manifest uses connectionRef but no inventory was provided")

    ref = desired.spec.connectionRef
    if ref is None:
        raise ValueError("manifest does not define a connection source")

    try:
        return inventory.connections[ref]
    except KeyError as exc:
        raise ValueError(f"connectionRef '{ref}' was not found in inventory") from exc
