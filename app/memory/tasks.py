"""TaskRepo — CRUD task / checklist / plan trên Postgres.

Map Row ↔ domain entity XẢY RA Ở ĐÂY. tools/ và api/ đều gọi qua repo này —
1 nguồn logic, 2 lối vào (chat + HTTP). Xem thiết kế: docs/task-agent.md

Để trong memory/ vì memory/ đã làm chủ Postgres. App lớn hơn → tách repositories/.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.task import ChecklistItem, PlanSlot, Task, TaskStatus, WeekPlan
from app.memory.tables import ChecklistItemRow, PlanRow, PlanSlotRow, TaskRow

_TASK_FIELDS = {
    "title",
    "notes",
    "estimate_hours",
    "deadline",
    "priority",
    "project",
    "status",
}
_SLOT_FIELDS = {"day", "planned_hours", "start_minute", "position", "done"}


def monday_of(d: date) -> date:
    """Thứ Hai của tuần chứa `d` — mọi plan neo vào mốc này."""
    return d - timedelta(days=d.weekday())


def _as_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


class TaskRepo:
    def __init__(self, dsn: str) -> None:
        self._engine = create_async_engine(dsn)
        self._Session = async_sessionmaker(self._engine, expire_on_commit=False)

    # ---------- map Row -> domain ----------

    @staticmethod
    def _task(row: TaskRow, items: list[ChecklistItemRow] | None = None) -> Task:
        return Task(
            id=row.id,
            title=row.title,
            notes=row.notes,
            status=TaskStatus(row.status),
            priority=row.priority,
            estimate_hours=(
                float(row.estimate_hours) if row.estimate_hours is not None else None
            ),
            deadline=row.deadline,
            project=row.project,
            checklist=[
                ChecklistItem(id=i.id, text=i.text, done=i.done, position=i.position)
                for i in sorted(items or [], key=lambda x: x.position)
            ],
        )

    @staticmethod
    def _slot(row: PlanSlotRow, task_title: str) -> PlanSlot:
        return PlanSlot(
            id=row.id,
            task_id=row.task_id,
            task_title=task_title,
            day=row.day,
            start_minute=row.start_minute,
            planned_hours=float(row.planned_hours),
            position=row.position,
            done=row.done,
        )

    # ---------- tasks ----------

    async def add_task(
        self,
        title: str,
        *,
        notes: str = "",
        estimate_hours: float | None = None,
        deadline: date | None = None,
        priority: int = 2,
        project: str | None = None,
        source: str = "chat",
    ) -> Task:
        async with self._Session() as s, s.begin():
            row = TaskRow(
                title=title,
                notes=notes,
                estimate_hours=estimate_hours,
                deadline=_as_date(deadline) if deadline is not None else None,
                priority=priority,
                project=project,
                source=source,
            )
            s.add(row)
            await s.flush()
            return self._task(row)

    async def list_tasks(
        self, *, status: str | None = None, project: str | None = None
    ) -> list[Task]:
        async with self._Session() as s:
            stmt = select(TaskRow).order_by(TaskRow.priority, TaskRow.id)
            if status:
                stmt = stmt.where(TaskRow.status == status)
            if project:
                stmt = stmt.where(TaskRow.project == project)
            rows = (await s.execute(stmt)).scalars().all()
            return [self._task(r) for r in rows]

    async def get_task(self, task_id: int) -> Task | None:
        async with self._Session() as s:
            row = await s.get(TaskRow, task_id)
            if row is None:
                return None
            items = (
                (
                    await s.execute(
                        select(ChecklistItemRow).where(
                            ChecklistItemRow.task_id == task_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            return self._task(row, list(items))

    async def update_task(self, task_id: int, **fields: Any) -> Task | None:
        patch = {k: v for k, v in fields.items() if k in _TASK_FIELDS and v is not None}
        if "deadline" in patch:
            patch["deadline"] = _as_date(patch["deadline"])
        async with self._Session() as s, s.begin():
            row = await s.get(TaskRow, task_id)
            if row is None:
                return None
            for k, v in patch.items():
                setattr(row, k, v)
            if patch.get("status") == "done" and row.done_at is None:
                row.done_at = datetime.now(timezone.utc)
            await s.flush()
            return self._task(row)

    async def complete_task(self, task_id: int) -> Task | None:
        return await self.update_task(task_id, status="done")

    async def delete_task(self, task_id: int) -> bool:
        async with self._Session() as s, s.begin():
            row = await s.get(TaskRow, task_id)
            if row is None:
                return False
            await s.delete(row)  # checklist_items + plan_slots cascade ở DB
            return True

    # ---------- checklist ----------

    async def set_checklist(
        self, task_id: int, items: list[str]
    ) -> list[ChecklistItem]:
        async with self._Session() as s, s.begin():
            await s.execute(
                delete(ChecklistItemRow).where(ChecklistItemRow.task_id == task_id)
            )
            rows = [
                ChecklistItemRow(task_id=task_id, text=t, position=i)
                for i, t in enumerate(items)
            ]
            s.add_all(rows)
            await s.flush()
            return [
                ChecklistItem(id=r.id, text=r.text, done=r.done, position=r.position)
                for r in rows
            ]

    async def check_item(self, item_id: int, done: bool = True) -> bool:
        async with self._Session() as s, s.begin():
            row = await s.get(ChecklistItemRow, item_id)
            if row is None:
                return False
            row.done = done
            return True

    # ---------- plans ----------

    async def get_plan(self, week_start: date | None = None) -> WeekPlan | None:
        today = date.today()  # noqa: DTZ011 — giờ địa phương là đúng cho lịch cá nhân
        week = monday_of(_as_date(week_start) if week_start else today)
        async with self._Session() as s:
            plan = (
                await s.execute(
                    select(PlanRow)
                    .where(PlanRow.week_start == week, PlanRow.is_active.is_(True))
                    .order_by(PlanRow.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if plan is None:
                return None
            rows = (
                await s.execute(
                    select(PlanSlotRow, TaskRow.title)
                    .join(TaskRow, TaskRow.id == PlanSlotRow.task_id)
                    .where(PlanSlotRow.plan_id == plan.id)
                    .order_by(PlanSlotRow.day, PlanSlotRow.position)
                )
            ).all()
            return WeekPlan(
                week_start=plan.week_start,
                note=plan.note,
                slots=[self._slot(r[0], r[1]) for r in rows],
            )

    async def save_plan(
        self,
        week_start: date,
        slots: list[dict],
        *,
        note: str = "",
        created_by: str = "chat",
    ) -> WeekPlan:
        """Tạo `plans` mới cho tuần (plan cũ cùng tuần → inactive, giữ lịch sử revision)."""
        week = monday_of(_as_date(week_start))
        async with self._Session() as s, s.begin():
            await s.execute(
                update(PlanRow)
                .where(PlanRow.week_start == week, PlanRow.is_active.is_(True))
                .values(is_active=False)
            )
            plan = PlanRow(
                week_start=week, note=note, created_by=created_by, is_active=True
            )
            s.add(plan)
            await s.flush()

            slot_rows: list[PlanSlotRow] = []
            for i, sl in enumerate(slots):
                slot_rows.append(
                    PlanSlotRow(
                        plan_id=plan.id,
                        task_id=int(sl["task_id"]),
                        day=_as_date(sl["day"]),
                        start_minute=sl.get("start_minute"),
                        planned_hours=float(
                            sl.get("planned_hours")
                            if sl.get("planned_hours") is not None
                            else sl.get("hours") or 0
                        ),
                        position=int(sl.get("position", i)),
                    )
                )
            s.add_all(slot_rows)
            await s.flush()

            titles = dict(
                (
                    await s.execute(
                        select(TaskRow.id, TaskRow.title).where(
                            TaskRow.id.in_({r.task_id for r in slot_rows})
                        )
                    )
                ).all()
            )
            return WeekPlan(
                week_start=week,
                note=note,
                slots=[
                    self._slot(r, titles.get(r.task_id, f"#{r.task_id}"))
                    for r in slot_rows
                ],
            )

    async def update_slot(self, slot_id: int, **fields: Any) -> PlanSlot | None:
        patch = {k: v for k, v in fields.items() if k in _SLOT_FIELDS and v is not None}
        if "day" in patch:
            patch["day"] = _as_date(patch["day"])
        async with self._Session() as s, s.begin():
            row = await s.get(PlanSlotRow, slot_id)
            if row is None:
                return None
            for k, v in patch.items():
                setattr(row, k, v)
            await s.flush()
            task = await s.get(TaskRow, row.task_id)
            return self._slot(row, task.title if task else f"#{row.task_id}")

    async def roll_over(self, from_day: date, to_day: date) -> int:
        """Slot ngày `from_day` chưa done → dời sang `to_day`. Trả số slot đã dời."""
        async with self._Session() as s, s.begin():
            res = await s.execute(
                update(PlanSlotRow)
                .where(
                    PlanSlotRow.day == _as_date(from_day), PlanSlotRow.done.is_(False)
                )
                .values(day=_as_date(to_day))
            )
            return res.rowcount or 0
