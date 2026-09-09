"""Task, ChecklistItem, PlanSlot, WeekPlan — entity của Task Agent.

domain/ ở trung tâm — KHÔNG import tầng nào. engine / tools / api / memory dùng chung.
Xem thiết kế: docs/task-agent.md
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    todo = "todo"
    doing = "doing"
    done = "done"
    cancelled = "cancelled"


class ChecklistItem(BaseModel):
    id: int
    text: str
    done: bool = False
    position: int = 0


class Task(BaseModel):
    id: int
    title: str
    notes: str = ""
    status: TaskStatus = TaskStatus.todo
    priority: int = 2  # 1 cao … 3 thấp
    estimate_hours: float | None = None
    deadline: date | None = None
    project: str | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)


class PlanSlot(BaseModel):
    id: int
    task_id: int
    task_title: str  # denormalize để hiển thị không cần join
    day: date
    start_minute: int | None = None  # phút từ 0h; None = "trong ngày"
    planned_hours: float
    position: int = 0
    done: bool = False


class WeekPlan(BaseModel):
    week_start: date  # thứ Hai
    note: str = ""
    slots: list[PlanSlot] = Field(default_factory=list)
