"""GraphState — schema duy nhất luân chuyển qua mọi node của graph (orchestrator + worker).

Dùng Pydantic BaseModel (nhất quán với domain/), KHÔNG dùng reducer kiểu
`Annotated[list, add_messages]` của LangGraph — nó thiết kế cho `langchain_core.messages`,
mình dùng `domain.Message`. Mỗi node trả `messages` là list đầy đủ đã cập nhật (thay thế,
không append ngầm) — xem docs/langgraph-plan.md mục 3.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.message import Message, Usage


class GraphState(BaseModel):
    session_id: str
    trigger: str = "api"
    messages: list[Message]  # hội thoại gốc — KHÔNG đổi bởi worker/orchestrator nội bộ

    next_worker: str | None = None  # "planning" | "external" | None — orchestrator set mỗi lượt
    next_task: str | None = None  # câu lệnh orchestrator giao cho worker
    worker_reply: str | None = None  # worker vừa trả gì — orchestrator đọc để quyết bước kế
    worker_trace: list[dict] = []  # chi tiết loop nội bộ worker vừa chạy (tool_calls, steps) —
    # tương đương "full_history" của langgraph-supervisor, để _trace()/api không mất debug detail
    final_reply: str | None = None  # có giá trị = graph xong, route sang END

    steps: int = 0  # đếm lượt orchestrator — chặn vòng lặp vô hạn (giống ctx.max_steps)
    tool_calls: int = 0  # cộng dồn từ MỌI worker
    usage: Usage | None = None  # cộng dồn từ MỌI worker (Phase 3a — không được bỏ khi multi-agent)
    cost_usd: float | None = None
