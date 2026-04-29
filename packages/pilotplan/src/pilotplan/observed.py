from pydantic import BaseModel, Field


class DiskState(BaseModel):
    mount: str = "/"
    totalMiB: int | None = None
    usedMiB: int | None = None
    availableMiB: int | None = None
    usedPercent: int | None = None


class MemoryState(BaseModel):
    totalMiB: int | None = None
    availableMiB: int | None = None


class CpuState(BaseModel):
    cores: int | None = None
    usagePercent: float | None = None


class AptState(BaseModel):
    available: bool = False
    lastUpdate: str | None = None
    packageListsAgeSeconds: int | None = None
    packageListsFresh: bool | None = None
    upgradablePackages: int | None = None
    systemUpToDate: bool | None = None


class SystemState(BaseModel):
    os: str | None = None
    architecture: str | None = None
    distribution: str | None = None
    distributionVersion: str | None = None
    distributionPrettyName: str | None = None
    systemd: bool = False
    cpu: CpuState = Field(default_factory=CpuState)
    disk: DiskState = Field(default_factory=DiskState)
    memory: MemoryState = Field(default_factory=MemoryState)
    apt: AptState = Field(default_factory=AptState)
    packages: dict[str, bool] = Field(default_factory=dict)
    sysctl: dict[str, str | None] = Field(default_factory=dict)


class K3sState(BaseModel):
    installed: bool = False
    version: str | None = None
    serviceActive: bool | None = None
    serviceEnabled: bool | None = None


class ObservedState(BaseModel):
    target: str
    sshAvailable: bool
    system: SystemState = Field(default_factory=SystemState)
    k3s: K3sState = Field(default_factory=K3sState)
    errors: list[str] = Field(default_factory=list)
