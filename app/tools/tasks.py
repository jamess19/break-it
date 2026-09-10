"""9 tool Task Agent — wrap TaskRepo. Đăng ký qua register_task_tools().

Nguyên tắc: tool trả TÓM TẮT gọn (1 dòng/task), không dump raw row — tiết kiệm context.
Model làm phần suy luận; save_plan làm phần lưu + kiểm tra ràng buộc cứng.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.domain.task import PlanSlot, Task
from app.domain.tool import ToolDef, ToolResult
from app.memory.tasks import TaskRepo
from app.tools.registry import ToolRegistry

DAILY_CAPACITY_HOURS = 6.0  # trần giờ làm việc/ngày khi validate kế hoạch


def _obj_schema(props: dict, required: list[str] | None = None) -> dict:
    """Bọc boilerplate JSON Schema object. Optional param được provider tự cho phép
    null lúc gửi đi (xem openai.py) — ở đây khai type "thật" cho gọn."""
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


# ---------- format helpers ----------

def _task_line(t: Task) -> str:
    bits = [f"#{t.id} {t.title}", t.status.value]
    if t.estimate_hours:
        bits.append(f"~{t.estimate_hours:g}h")
    if t.deadline:
        bits.append(f"hạn {t.deadline}")
    if t.priority != 2:
        bits.append(f"P{t.priority}")
    if t.project:
        bits.append(f"[{t.project}]")
    return " · ".join(bits)


def _plan_text(slots: list[PlanSlot]) -> str:
    if not slots:
        return "(kế hoạch trống)"
    by_day: dict[date, list[PlanSlot]] = {}
    for sl in slots:
        by_day.setdefault(sl.day, []).append(sl)
    lines = []
    for day in sorted(by_day):
        total = sum(s.planned_hours for s in by_day[day])
        lines.append(f"{day} ({total:g}h):")
        for s in sorted(by_day[day], key=lambda x: x.position):
            mark = "✓" if s.done else "•"
            lines.append(f"  {mark} #{s.task_id} {s.task_title} — {s.planned_hours:g}h")
    return "\n".join(lines)


# ---------- tools ----------

class _RepoTool:
    def __init__(self, repo: TaskRepo) -> None:
        self._repo = repo


class AddTask(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="add_task",
            description=(
                "Thêm 1 việc vào danh sách. Khi user liệt kê nhiều việc, gọi nhiều lần. "
                "Tự tách tiêu đề, ước tính giờ và deadline từ câu nói của user."
            ),
            parameters=_obj_schema(
                {
                    "title": {"type": "string"},
                    "notes": {"type": "string"},
                    "estimate_hours": {"type": "number", "description": "ước tính giờ hoàn thành"},
                    "deadline": {"type": "string", "description": "YYYY-MM-DD"},
                    "priority": {"type": "integer", "description": "1 cao, 2 thường, 3 thấp"},
                    "project": {"type": "string"},
                },
                required=["title"],
            ),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        t = await self._repo.add_task(
            arguments["title"],
            notes=arguments.get("notes", ""),
            estimate_hours=arguments.get("estimate_hours"),
            deadline=arguments.get("deadline"),
            priority=int(arguments.get("priority", 2)),
            project=arguments.get("project"),
        )
        return ToolResult(content=f"Đã thêm {_task_line(t)}")


class ListTasks(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="list_tasks",
            description="Liệt kê việc. Lọc theo status (todo/doing/done/cancelled) hoặc project.",
            parameters=_obj_schema(
                {
                    "status": {"type": "string"},
                    "project": {"type": "string"},
                }
            ),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        tasks = await self._repo.list_tasks(
            status=arguments.get("status"), project=arguments.get("project")
        )
        if not tasks:
            return ToolResult(content="(không có việc nào khớp)")
        return ToolResult(content="\n".join(_task_line(t) for t in tasks))


class UpdateTask(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="update_task",
            description="Sửa 1 việc: đổi tiêu đề, ghi chú, ước tính, deadline, priority, project, status.",
            parameters=_obj_schema(
                {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                    "notes": {"type": "string"},
                    "estimate_hours": {"type": "number"},
                    "deadline": {"type": "string", "description": "YYYY-MM-DD"},
                    "priority": {"type": "integer"},
                    "project": {"type": "string"},
                    "status": {"type": "string"},
                },
                required=["id"],
            ),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        t = await self._repo.update_task(
            int(arguments["id"]), **{k: v for k, v in arguments.items() if k != "id"}
        )
        if t is None:
            return ToolResult(content=f"Không tìm thấy việc #{arguments['id']}", is_error=True)
        return ToolResult(content=f"Đã cập nhật {_task_line(t)}")


class CompleteTask(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="complete_task",
            description="Đánh dấu 1 việc là đã xong.",
            parameters=_obj_schema({"id": {"type": "integer"}}, required=["id"]),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        t = await self._repo.complete_task(int(arguments["id"]))
        if t is None:
            return ToolResult(content=f"Không tìm thấy việc #{arguments['id']}", is_error=True)
        return ToolResult(content=f"Xong: {_task_line(t)}")


class SetChecklist(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="set_checklist",
            description="Đặt checklist các bước cho 1 việc (ghi đè toàn bộ checklist cũ).",
            parameters=_obj_schema(
                {
                    "task_id": {"type": "integer"},
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                required=["task_id", "items"],
            ),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        items = await self._repo.set_checklist(
            int(arguments["task_id"]), [str(x) for x in arguments.get("items", [])]
        )
        return ToolResult(content=f"Checklist ({len(items)} bước) cho việc #{arguments['task_id']}")


class CheckItem(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="check_item",
            description="Tick / bỏ tick 1 bước trong checklist theo item_id.",
            parameters=_obj_schema(
                {
                    "item_id": {"type": "integer"},
                    "done": {"type": "boolean"},
                },
                required=["item_id"],
            ),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ok = await self._repo.check_item(
            int(arguments["item_id"]), bool(arguments.get("done", True))
        )
        if not ok:
            return ToolResult(content=f"Không tìm thấy item #{arguments['item_id']}", is_error=True)
        return ToolResult(content="Đã cập nhật checklist item")


class GetPlan(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="get_plan",
            description="Xem kế hoạch tuần hiện tại (đang active). week_start YYYY-MM-DD, bỏ trống = tuần này.",
            parameters=_obj_schema({"week_start": {"type": "string"}}),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ws = arguments.get("week_start")
        plan = await self._repo.get_plan(date.fromisoformat(ws) if ws else None)
        if plan is None:
            return ToolResult(content="(chưa có kế hoạch cho tuần này)")
        head = f"Kế hoạch tuần {plan.week_start}" + (f" — {plan.note}" if plan.note else "")
        return ToolResult(content=head + "\n" + _plan_text(plan.slots))


class SavePlan(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="save_plan",
            description=(
                "Lưu kế hoạch tuần: phân bổ từng việc vào từng ngày với số giờ. "
                "1 việc có thể tách nhiều ngày (nhiều slot). Trả về cảnh báo nếu ngày quá tải "
                f"(>{DAILY_CAPACITY_HOURS:g}h) hoặc slot trễ hơn deadline."
            ),
            parameters=_obj_schema(
                {
                    "week_start": {"type": "string", "description": "YYYY-MM-DD, thứ Hai của tuần"},
                    "note": {"type": "string"},
                    "slots": {
                        "type": "array",
                        "items": _obj_schema(
                            {
                                "task_id": {"type": "integer"},
                                "day": {"type": "string", "description": "YYYY-MM-DD"},
                                "hours": {"type": "number"},
                                "start_minute": {"type": "integer", "description": "phút từ 0h, tùy chọn"},
                            },
                            required=["task_id", "day", "hours"],
                        ),
                    },
                },
                required=["week_start", "slots"],
            ),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        plan = await self._repo.save_plan(
            date.fromisoformat(arguments["week_start"]),
            list(arguments.get("slots", [])),
            note=arguments.get("note", ""),
        )
        warnings = _validate_plan(plan.slots, await self._repo.list_tasks())
        out = f"Đã lưu kế hoạch tuần {plan.week_start}\n" + _plan_text(plan.slots)
        if warnings:
            out += "\n\nCẢNH BÁO:\n" + "\n".join(f"- {w}" for w in warnings)
        return ToolResult(content=out)


class Reschedule(_RepoTool):
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="reschedule",
            description="Dời 1 slot sang ngày khác / đổi số giờ. Cần slot_id (xem từ get_plan).",
            parameters=_obj_schema(
                {
                    "slot_id": {"type": "integer"},
                    "new_day": {"type": "string", "description": "YYYY-MM-DD"},
                    "new_hours": {"type": "number"},
                },
                required=["slot_id"],
            ),
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        sl = await self._repo.update_slot(
            int(arguments["slot_id"]),
            day=arguments.get("new_day"),
            planned_hours=arguments.get("new_hours"),
        )
        if sl is None:
            return ToolResult(content=f"Không tìm thấy slot #{arguments['slot_id']}", is_error=True)
        return ToolResult(content=f"Đã dời: {sl.task_title} → {sl.day} ({sl.planned_hours:g}h)")


def _validate_plan(slots: list[PlanSlot], tasks: list[Task]) -> list[str]:
    """Ràng buộc cứng: trần giờ/ngày + slot không được trễ hơn deadline."""
    warnings: list[str] = []
    by_day: dict[date, float] = {}
    last_day: dict[int, date] = {}
    for sl in slots:
        by_day[sl.day] = by_day.get(sl.day, 0.0) + sl.planned_hours
        last_day[sl.task_id] = max(last_day.get(sl.task_id, sl.day), sl.day)
    for day, hrs in sorted(by_day.items()):
        if hrs > DAILY_CAPACITY_HOURS:
            warnings.append(f"{day}: {hrs:g}h vượt trần {DAILY_CAPACITY_HOURS:g}h")
    task_by_id = {t.id: t for t in tasks}
    for tid, d in last_day.items():
        t = task_by_id.get(tid)
        if t and t.deadline and d > t.deadline:
            warnings.append(f"#{tid} {t.title}: slot cuối {d} trễ hơn deadline {t.deadline}")
    return warnings


def register_task_tools(registry: ToolRegistry, repo: TaskRepo) -> None:
    for cls in (
        AddTask,
        ListTasks,
        UpdateTask,
        CompleteTask,
        SetChecklist,
        CheckItem,
        GetPlan,
        SavePlan,
        Reschedule,
    ):
        registry.register(cls(repo))
