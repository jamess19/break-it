"""Chấm 1 assert trên (plan, tasks) sau khi agent chạy xong.

Toàn logic thuần — không DB, không network. Mỗi hàm trả `Check(ok, detail)`.
`detail` CHỈ điền khi fail (giải thích vì sao), để đọc report/JSON gọn.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.domain.task import Task, WeekPlan
from eval.loader import Assert

_EPS = 1e-6


@dataclass
class Check:
    type: str
    ok: bool
    detail: str = ""
    soft: bool = False  # từ Assert.soft — fail soft không làm case FAIL


def _ok() -> tuple[bool, str]:
    return True, ""


def _hours_by_day(plan: WeekPlan) -> dict:
    d: dict = defaultdict(float)
    for s in plan.slots:
        d[s.day] += s.planned_hours
    return d


def _last_slot_day(plan: WeekPlan) -> dict:
    d: dict = {}
    for s in plan.slots:
        d[s.task_id] = max(d.get(s.task_id, s.day), s.day)
    return d


def _active(tasks: list[Task]) -> list[Task]:
    return [t for t in tasks if t.status.value not in ("done", "cancelled")]


def _check(a: Assert, plan: WeekPlan | None, tasks: list[Task]) -> tuple[bool, str]:
    t, p = a.type, a.params

    if t == "plan_absent":
        absent = plan is None or not plan.slots
        return absent, "" if absent else "plan có tồn tại (đáng lẽ không)"

    if plan is None or not plan.slots:
        return False, "agent không tạo plan (get_plan trả rỗng)"

    if t == "plan_exists":
        return _ok()

    if t == "all_tasks_scheduled":
        sched = {s.task_id for s in plan.slots}
        miss = [f"#{x.id} {x.title}" for x in _active(tasks) if x.id not in sched]
        return (not miss), ("chưa xếp: " + "; ".join(miss) if miss else "")

    if t == "all_p1_scheduled":
        sched = {s.task_id for s in plan.slots}
        miss = [f"#{x.id} {x.title}" for x in _active(tasks) if x.priority == 1 and x.id not in sched]
        return (not miss), ("P1 chưa xếp: " + "; ".join(miss) if miss else "")

    if t == "no_day_over":
        cap = float(p["hours"])
        over = [f"{d}={h:g}h" for d, h in sorted(_hours_by_day(plan).items()) if h > cap + _EPS]
        return (not over), (f"quá trần {cap:g}h: " + ", ".join(over) if over else "")

    if t == "nothing_after_deadline":
        last = _last_slot_day(plan)
        by_id = {x.id: x for x in tasks}
        bad = [
            f"#{tid} slot cuối {day} > hạn {by_id[tid].deadline}"
            for tid, day in last.items()
            if by_id.get(tid) and by_id[tid].deadline and day > by_id[tid].deadline
        ]
        return (not bad), "; ".join(bad)

    if t == "total_hours_within":
        slack = float(p["slack"])
        planned = sum(s.planned_hours for s in plan.slots)
        est = sum(x.estimate_hours or 0.0 for x in _active(tasks))
        diff = abs(planned - est)
        ok = diff <= slack + _EPS
        return ok, ("" if ok else f"planned={planned:g}h est={est:g}h |Δ|={diff:g}h > slack {slack:g}h")

    return False, f"scorer chưa biết assert type '{t}'"


def score(a: Assert, plan: WeekPlan | None, tasks: list[Task]) -> Check:
    ok, detail = _check(a, plan, tasks)
    return Check(a.type, ok, "" if ok else detail, soft=a.soft)
