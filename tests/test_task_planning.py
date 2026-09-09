"""Logic thuần của Task Agent — không cần DB.

Kiểm ràng buộc cứng của kế hoạch (trần giờ/ngày, deadline) + mốc thứ Hai của tuần.
"""

from datetime import date

from app.domain.task import PlanSlot, Task
from app.memory.tasks import monday_of
from app.tools.tasks import DAILY_CAPACITY_HOURS, _validate_plan


def _slot(task_id: int, day: date, hours: float) -> PlanSlot:
    return PlanSlot(id=0, task_id=task_id, task_title=f"#{task_id}", day=day, planned_hours=hours)


def test_monday_of_snaps_to_week_start():
    assert monday_of(date(2026, 9, 3)) == date(2026, 8, 31)  # thứ 5 → thứ 2
    assert monday_of(date(2026, 8, 31)) == date(2026, 8, 31)  # thứ 2 → chính nó


def test_validate_plan_flags_overloaded_day():
    d = date(2026, 9, 1)
    slots = [_slot(1, d, 4), _slot(2, d, 4)]  # 8h > trần 6h
    warnings = _validate_plan(slots, tasks=[])
    assert any("vượt trần" in w for w in warnings)


def test_validate_plan_ok_when_within_capacity():
    d = date(2026, 9, 1)
    slots = [_slot(1, d, DAILY_CAPACITY_HOURS)]
    assert _validate_plan(slots, tasks=[]) == []


def test_validate_plan_flags_slot_after_deadline():
    task = Task(id=1, title="báo cáo", deadline=date(2026, 9, 2))
    slots = [_slot(1, date(2026, 9, 4), 2)]  # slot sau deadline
    warnings = _validate_plan(slots, tasks=[task])
    assert any("trễ hơn deadline" in w for w in warnings)
