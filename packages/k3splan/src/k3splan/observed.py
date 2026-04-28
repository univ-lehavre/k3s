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


class SystemState(BaseModel):
    os: str | None = None
    architecture: str | None = None
    systemd: bool = False
    disk: DiskState = Field(default_factory=DiskState)
    memory: MemoryState = Field(default_factory=MemoryState)


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
