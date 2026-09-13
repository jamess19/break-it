"""`/tasks` — REST CRUD cho UI to-do list: sửa task / checklist trực tiếp, không qua chat.

Cùng `TaskRepo` mà tool dùng → 1 nguồn logic, 2 lối vào. Body Pydantic ở đây là
HTTP schema (không phải domain) — biên HTTP dừng tại route.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import Runtime, build_runtime
from app.domain.task import ChecklistItem, Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


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


# ---------- tasks ----------

@router.get("", response_model=list[Task])
async def list_tasks(
    status: str | None = None,
    project: str | None = None,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> list[Task]:
    return await rt.tasks.list_tasks(status=status, project=project)


@router.post("", response_model=Task, status_code=201)
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


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: int,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> Task:
    t = await rt.tasks.get_task(task_id)
    if t is None:
        raise HTTPException(404, "task không tồn tại")
    return t


@router.patch("/{task_id}", response_model=Task)
async def patch_task(
    task_id: int,
    body: TaskPatch,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> Task:
    t = await rt.tasks.update_task(task_id, **body.model_dump(exclude_none=True))
    if t is None:
        raise HTTPException(404, "task không tồn tại")
    return t


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> None:
    if not await rt.tasks.delete_task(task_id):
        raise HTTPException(404, "task không tồn tại")


# ---------- checklist ----------

@router.put("/{task_id}/checklist", response_model=list[ChecklistItem])
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
