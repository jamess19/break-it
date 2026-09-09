"""REST CRUD cho UI to-do list — sửa task / checklist / plan trực tiếp, không qua chat.

Cùng `TaskRepo` mà tool dùng → 1 nguồn logic, 2 lối vào. Body Pydantic ở đây là
HTTP schema (không phải domain) — biên HTTP dừng tại route.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import Runtime, build_runtime
from app.domain.task import ChecklistItem, PlanSlot, Task, WeekPlan
from app.engine.run import run
from app.memory.tasks import monday_of

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    title: str
    notes: str = ""
    estimate_hours: float | None = None
    deadline: date | None = None
    priority: int = 2
    project: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    notes: str | None = None
    estimate_hours: float | None = None
    deadline: date | None = None
    priority: int | None = None
    project: str | None = None
    status: str | None = None


class ChecklistBody(BaseModel):
    items: list[str]


class ItemPatch(BaseModel):
    done: bool = True


class SlotPatch(BaseModel):
    day: date | None = None
    planned_hours: float | None = None
    done: bool | None = None


class ReplanBody(BaseModel):
    week_start: date | None = None
    message: str = ""


# ---------- tasks ----------

@router.get("/tasks", response_model=list[Task])
async def list_tasks(
    status: str | None = None,
    project: str | None = None,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> list[Task]:
    return await rt.tasks.list_tasks(status=status, project=project)


@router.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    body: TaskCreate,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> Task:
    return await rt.tasks.add_task(
        body.title,
        notes=body.notes,
        estimate_hours=body.estimate_hours,
        deadline=body.deadline,
        priority=body.priority,
        project=body.project,
        source="api",
    )


@router.get("/tasks/{task_id}", response_model=Task)
async def get_task(
    task_id: int,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> Task:
    t = await rt.tasks.get_task(task_id)
    if t is None:
        raise HTTPException(404, "task không tồn tại")
    return t


@router.patch("/tasks/{task_id}", response_model=Task)
async def patch_task(
    task_id: int,
    body: TaskPatch,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> Task:
    t = await rt.tasks.update_task(task_id, **body.model_dump(exclude_none=True))
    if t is None:
        raise HTTPException(404, "task không tồn tại")
    return t


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> None:
    if not await rt.tasks.delete_task(task_id):
        raise HTTPException(404, "task không tồn tại")


# ---------- checklist ----------

@router.put("/tasks/{task_id}/checklist", response_model=list[ChecklistItem])
async def put_checklist(
    task_id: int,
    body: ChecklistBody,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> list[ChecklistItem]:
    return await rt.tasks.set_checklist(task_id, body.items)


@router.patch("/checklist/{item_id}")
async def patch_item(
    item_id: int,
    body: ItemPatch,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> dict:
    if not await rt.tasks.check_item(item_id, body.done):
        raise HTTPException(404, "checklist item không tồn tại")
    return {"ok": True}


# ---------- plan ----------

@router.get("/plan", response_model=WeekPlan)
async def get_plan(
    week: date | None = None,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> WeekPlan:
    p = await rt.tasks.get_plan(week)
    if p is None:
        raise HTTPException(404, "chưa có kế hoạch cho tuần này")
    return p


@router.patch("/plan/slots/{slot_id}", response_model=PlanSlot)
async def patch_slot(
    slot_id: int,
    body: SlotPatch,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> PlanSlot:
    sl = await rt.tasks.update_slot(slot_id, **body.model_dump(exclude_none=True))
    if sl is None:
        raise HTTPException(404, "slot không tồn tại")
    return sl


@router.post("/plan/replan")
async def replan(
    body: ReplanBody,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> dict:
    """Nhờ LLM xếp lại lịch tuần — cùng engine.run() như /chat, chỉ khác input source."""
    week = monday_of(body.week_start or date.today())  # noqa: DTZ011
    msg = body.message or (
        f"Xếp lịch làm việc cho tuần bắt đầu {week}. Gọi recall để lấy thói quen, "
        f"list_tasks để lấy việc chưa xong, rồi save_plan với các slot theo ngày."
    )
    result = await run(
        session_id=f"replan:{week}",
        user_message=msg,
        provider=rt.provider,
        registry=rt.registry,
        session=rt.session,
        trigger="api",
    )
    plan = await rt.tasks.get_plan(week)
    return {
        "reply": result.reply,
        "steps": result.steps,
        "tool_calls": result.tool_calls,
        "plan": plan.model_dump(mode="json") if plan else None,
    }
