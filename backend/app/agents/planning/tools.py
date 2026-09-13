"""Bind tool cho worker `planning` — KHÔNG tự implement tool (logic thật ở app/tools/).

`planning` sở hữu: 9 tool task (add_task...reschedule) + recall/remember — xem
docs/langgraph-plan.md mục 5 để đổi ranh giới nếu cần.
"""

from __future__ import annotations

from app.services.store import FactStore
from app.services.tasks import TaskRepo
from app.tools.memory import register_memory_tools
from app.tools.registry import ToolRegistry
from app.tools.tasks import register_task_tools


def build_registry(tasks: TaskRepo, store: FactStore) -> ToolRegistry:
    registry = ToolRegistry()
    register_task_tools(registry, tasks)  # code tool ở app/tools/, KHÔNG fork
    register_memory_tools(registry, store)
    return registry
