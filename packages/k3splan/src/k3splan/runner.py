from dataclasses import dataclass

from k3splan.actions import Action
from k3splan.journal import Journal


@dataclass
class RunResult:
    success: bool
    applied: int
    failed_action: str | None = None
    error: str | None = None


class Runner:
    def __init__(self, journal: Journal) -> None:
        self._journal = journal

    def run(self, target: str, actions: list[Action]) -> RunResult:
        self._journal.start_run(target)
        applied: list[tuple[Action, object]] = []

        for action in actions:
            try:
                action.precheck()
            except Exception as exc:
                self._journal.record_started(action.id, action.description, None)
                self._journal.record_failed(action.id, "failed_apply", str(exc))
                self._journal.complete_run(success=False)
                self._journal.save()
                return RunResult(
                    success=False,
                    applied=len(applied),
                    failed_action=action.id,
                    error=str(exc),
                )

            snapshot = action.snapshot()
            self._journal.record_started(action.id, action.description, snapshot)

            try:
                action.apply()
            except Exception as exc:
                self._journal.record_failed(action.id, "failed_apply", str(exc))
                self._do_rollback(applied)
                self._journal.complete_run(success=False)
                self._journal.save()
                return RunResult(
                    success=False,
                    applied=len(applied),
                    failed_action=action.id,
                    error=str(exc),
                )

            if not action.verify():
                error = f"verification failed for {action.id}"
                self._journal.record_failed(action.id, "failed_verify", error)
                self._do_rollback(applied)
                self._journal.complete_run(success=False)
                self._journal.save()
                return RunResult(
                    success=False,
                    applied=len(applied),
                    failed_action=action.id,
                    error=error,
                )

            self._journal.record_committed(action.id)
            applied.append((action, snapshot))

        self._journal.complete_run(success=True)
        self._journal.save()
        return RunResult(success=True, applied=len(applied))

    def _do_rollback(self, applied: list[tuple[Action, object]]) -> None:
        for action, snapshot in reversed(applied):
            if action.rollback_mode == "none":
                continue
            try:
                action.rollback(snapshot)
                self._journal.record_rolled_back(action.id)
            except Exception:
                self._journal.record_rollback_failed(action.id)
