from pathlib import Path

from pilotplan.actions import Action, RollbackMode
from pilotplan.journal import Journal
from pilotplan.runner import Runner


class OkAction(Action):
    def __init__(self, action_id: str, rollback_mode: RollbackMode = "none") -> None:
        self._id = action_id
        self._rollback_mode = rollback_mode
        self.rolled_back = False

    @property
    def id(self) -> str:
        return self._id

    @property
    def description(self) -> str:
        return self._id

    @property
    def rollback_mode(self) -> RollbackMode:
        return self._rollback_mode

    def snapshot(self) -> object:
        return "snap"

    def apply(self) -> None:
        pass

    def verify(self) -> bool:
        return True

    def rollback(self, snapshot: object) -> None:
        self.rolled_back = True


class FailApplyAction(OkAction):
    def apply(self) -> None:
        raise RuntimeError("apply failed")


class FailVerifyAction(OkAction):
    def verify(self) -> bool:
        return False


class FailPrecheckAction(OkAction):
    def precheck(self) -> None:
        raise RuntimeError("precheck failed")


def make_runner(tmp_path: Path) -> Runner:
    journal = Journal(tmp_path / ".k3sp" / "runs")
    return Runner(journal)


def test_runner_succeeds_with_all_ok_actions(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    result = runner.run("prod-1", [OkAction("a"), OkAction("b")])

    assert result.success is True
    assert result.applied == 2
    assert result.failed_action is None


def test_runner_writes_journal_on_success(tmp_path: Path) -> None:
    journal = Journal(tmp_path / ".k3sp" / "runs")
    runner = Runner(journal)
    runner.run("prod-1", [OkAction("a")])

    runs = journal.list_runs()
    assert len(runs) == 1
    assert runs[0].target == "prod-1"
    assert runs[0].success is True


def test_runner_stops_and_rolls_back_on_apply_failure(tmp_path: Path) -> None:
    a = OkAction("a", rollback_mode="reversible")
    b = FailApplyAction("b")
    runner = make_runner(tmp_path)
    result = runner.run("prod-1", [a, b])

    assert result.success is False
    assert result.failed_action == "b"
    assert a.rolled_back is True


def test_runner_stops_and_rolls_back_on_verify_failure(tmp_path: Path) -> None:
    a = OkAction("a", rollback_mode="reversible")
    b = FailVerifyAction("b")
    runner = make_runner(tmp_path)
    result = runner.run("prod-1", [a, b])

    assert result.success is False
    assert result.failed_action == "b"
    assert a.rolled_back is True


def test_runner_stops_on_precheck_failure_without_rollback(tmp_path: Path) -> None:
    a = OkAction("a", rollback_mode="reversible")
    b = FailPrecheckAction("b")
    runner = make_runner(tmp_path)
    result = runner.run("prod-1", [a, b])

    assert result.success is False
    assert result.failed_action == "b"
    assert a.rolled_back is False


def test_runner_skips_rollback_for_none_mode(tmp_path: Path) -> None:
    a = OkAction("a", rollback_mode="none")
    b = FailApplyAction("b")
    runner = make_runner(tmp_path)
    runner.run("prod-1", [a, b])

    assert a.rolled_back is False


def test_runner_empty_plan_succeeds(tmp_path: Path) -> None:
    result = make_runner(tmp_path).run("prod-1", [])
    assert result.success is True
    assert result.applied == 0
