"""`/plan` — xem / sửa kế hoạch tuần. `POST /plan/replan` nhờ LLM xếp lại.

`replan` dùng cùng `orchestration.graph.run()` như `/chat` — chỉ khác input source.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import Runtime, build_runtime
from app.domain.task import PlanSlot, WeekPlan
from app.orchestration.graph import run
from app.services.tasks import monday_of

router = APIRouter(prefix="/plan", tags=["plans"])


class SlotPatch(BaseModel):
    day: date | None = None
    planned_hours: float | None = None
    done: bool | None = None


class ReplanBody(BaseModel):
    week_start: date | None = None
    message: str = ""


@router.get("", response_model=WeekPlan)
async def get_plan(
    week: date | None = None,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> WeekPlan:
    p = await rt.tasks.get_plan(week)
    if p is None:
        raise HTTPException(404, "chưa có kế hoạch cho tuần này")
    return p


@router.patch("/slots/{slot_id}", response_model=PlanSlot)
async def patch_slot(
    slot_id: int,
    body: SlotPatch,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> PlanSlot:
    sl = await rt.tasks.update_slot(slot_id, **body.model_dump(exclude_none=True))
    if sl is None:
        raise HTTPException(404, "slot không tồn tại")
    return sl


@router.post("/replan")
async def replan(
    body: ReplanBody,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> dict:
    week = monday_of(body.week_start or date.today())  # noqa: DTZ011
    msg = body.message or (
        f"Xếp lịch làm việc cho tuần bắt đầu {week}. Gọi recall để lấy thói quen, "
        f"list_tasks để lấy việc chưa xong, rồi save_plan với các slot theo ngày."
    )
    result = await run(
        session_id=f"replan:{week}",
        user_message=msg,
        graph=rt.graph,
        session=rt.session,
        trigger="api",
    )
    plan = await rt.tasks.get_plan(week)
    return {
        "reply": result.reply,
        "steps": result.steps,
        "tool_calls": result.tool_calls,
        "usage": result.usage.model_dump() if result.usage else None,
        "cost_usd": result.cost_usd,
        "plan": plan.model_dump(mode="json") if plan else None,
    }
