"""Logic chấm điểm của eval — thuần, không DB."""

from datetime import date

from app.domain.task import PlanSlot, Task, TaskStatus, WeekPlan
from eval.loader import Assert
from eval.scorers import score

WK = date(2026, 9, 7)  # thứ Hai


def _slot(task_id, day, hours, title="x"):
    return PlanSlot(id=0, task_id=task_id, task_title=title, day=day, planned_hours=hours)


def _task(tid, *, hours=None, deadline=None, priority=2, status="todo"):
    return Task(id=tid, title=f"t{tid}", estimate_hours=hours, deadline=deadline,
                priority=priority, status=TaskStatus(status))


def _plan(*slots):
    return WeekPlan(week_start=WK, slots=list(slots))


def test_no_plan_fails_everything_except_plan_absent():
    assert score(Assert("plan_exists"), None, []).ok is False
    assert score(Assert("plan_absent"), None, []).ok is True


def test_no_day_over():
    p = _plan(_slot(1, WK, 4), _slot(2, WK, 3))  # 7h thứ Hai
    assert score(Assert("no_day_over", {"hours": 6}), p, []).ok is False
    assert score(Assert("no_day_over", {"hours": 8}), p, []).ok is True


def test_nothing_after_deadline():
    tasks = [_task(1, deadline=date(2026, 9, 9))]
    good = _plan(_slot(1, date(2026, 9, 8), 2))
    bad = _plan(_slot(1, date(2026, 9, 8), 2), _slot(1, date(2026, 9, 11), 1))
    assert score(Assert("nothing_after_deadline"), good, tasks).ok is True
    assert score(Assert("nothing_after_deadline"), bad, tasks).ok is False


def test_all_p1_scheduled_ignores_done():
    tasks = [_task(1, priority=1), _task(2, priority=1, status="done"), _task(3, priority=2)]
    p = _plan(_slot(1, WK, 2))  # chỉ xếp #1
    assert score(Assert("all_p1_scheduled"), p, tasks).ok is True  # #2 done → bỏ qua, #3 P2 → không tính


def test_all_p1_scheduled_fails_when_p1_missing():
    tasks = [_task(1, priority=1), _task(2, priority=1)]
    p = _plan(_slot(1, WK, 2))
    assert score(Assert("all_p1_scheduled"), p, tasks).ok is False


def test_total_hours_within():
    tasks = [_task(1, hours=4), _task(2, hours=3)]  # est 7h
    p = _plan(_slot(1, WK, 4), _slot(2, WK, 2))  # planned 6h, Δ=1
    assert score(Assert("total_hours_within", {"slack": 2}), p, tasks).ok is True
    assert score(Assert("total_hours_within", {"slack": 0.5}), p, tasks).ok is False
