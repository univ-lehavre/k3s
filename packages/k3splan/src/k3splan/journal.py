import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

ActionStatus = Literal[
    "pending",
    "started",
    "committed",
    "failed_apply",
    "failed_verify",
    "rolled_back",
    "rollback_failed",
]


@dataclass
class ActionRecord:
    id: str
    description: str
    status: ActionStatus = "pending"
    snapshot: object = None
    error: str | None = None


@dataclass
class RunRecord:
    run_id: str
    target: str
    started_at: str
    actions: list[ActionRecord] = field(default_factory=list)
    success: bool | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "target": self.target,
            "started_at": self.started_at,
            "success": self.success,
            "actions": [
                {
                    "id": a.id,
                    "description": a.description,
                    "status": a.status,
                    "snapshot": a.snapshot,
                    "error": a.error,
                }
                for a in self.actions
            ],
        }


class Journal:
    def __init__(self, path: Path, keep: int = 20) -> None:
        self._path = path
        self._keep = keep
        self._current: RunRecord | None = None

    def start_run(self, target: str) -> RunRecord:
        now = datetime.now(UTC)
        run_id = now.strftime("%Y%m%dT%H%M%SZ")
        self._current = RunRecord(
            run_id=run_id,
            target=target,
            started_at=now.isoformat(),
        )
        return self._current

    def _find(self, action_id: str) -> ActionRecord:
        assert self._current is not None
        for record in self._current.actions:
            if record.id == action_id:
                return record
        raise KeyError(action_id)

    def record_started(self, action_id: str, description: str, snapshot: object) -> None:
        assert self._current is not None
        self._current.actions.append(
            ActionRecord(id=action_id, description=description, status="started", snapshot=snapshot)
        )

    def record_committed(self, action_id: str) -> None:
        self._find(action_id).status = "committed"

    def record_failed(self, action_id: str, status: ActionStatus, error: str) -> None:
        record = self._find(action_id)
        record.status = status
        record.error = error

    def record_rolled_back(self, action_id: str) -> None:
        self._find(action_id).status = "rolled_back"

    def record_rollback_failed(self, action_id: str) -> None:
        self._find(action_id).status = "rollback_failed"

    def complete_run(self, *, success: bool) -> None:
        assert self._current is not None
        self._current.success = success

    def save(self) -> None:
        assert self._current is not None
        self._path.mkdir(parents=True, exist_ok=True)
        run_file = self._path / f"{self._current.run_id}.json"
        run_file.write_text(json.dumps(self._current.to_dict(), indent=2), encoding="utf-8")
        self._prune()

    def _prune(self) -> None:
        runs = sorted(self._path.glob("*.json"), key=lambda p: p.name)
        for old in runs[: -self._keep]:
            old.unlink()

    def list_runs(self) -> list[RunRecord]:
        runs = []
        for path in sorted(self._path.glob("*.json"), reverse=True):
            data = json.loads(path.read_text(encoding="utf-8"))
            runs.append(
                RunRecord(
                    run_id=data["run_id"],
                    target=data["target"],
                    started_at=data["started_at"],
                    success=data.get("success"),
                )
            )
        return runs
