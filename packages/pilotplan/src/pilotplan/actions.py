from abc import ABC, abstractmethod
from typing import Literal

RiskLevel = Literal["low", "medium", "high", "destructive"]
RollbackMode = Literal["none", "reversible", "compensating"]


class Action(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    def risk(self) -> RiskLevel:
        return "low"

    @property
    def rollback_mode(self) -> RollbackMode:
        return "none"

    def precheck(self) -> None:  # default no-op; override to add pre-flight checks
        return

    @abstractmethod
    def snapshot(self) -> object: ...

    @abstractmethod
    def apply(self) -> None: ...

    @abstractmethod
    def verify(self) -> bool: ...

    def rollback(self, snapshot: object) -> None:
        raise NotImplementedError(f"rollback not implemented for {self.id}")
