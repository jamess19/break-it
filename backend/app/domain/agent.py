"""AgentResult, RunContext — output & context của 1 lần run()."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.message import Message, Usage


class RunContext(BaseModel):
    """Context 1 lần run() — đi kèm suốt vòng lặp engine."""

    session_id: str
    trigger: str = "api"  # api | cron | webhook — chỉ là input source khác nhau
    max_steps: int = 10  # chặn loop vô hạn


class AgentResult(BaseModel):
    """Output 1 lần run(): câu trả lời cuối + metadata. Engine KHÔNG biết ChatResponse."""

    session_id: str
    reply: str
    messages: list[Message] = Field(default_factory=list)
    worker_trace: list[dict] = Field(default_factory=list)  # chi tiết tool-call của worker vừa
    # chạy (multi-agent) — messages ở trên giờ chỉ có cấp orchestrator (user + final assistant),
    # không còn đủ để debug từng bước tool-call như trước graph; xem docs/langgraph-plan.md mục 3
    steps: int = 0
    tool_calls: int = 0
    usage: Usage | None = None  # tổng token qua các step; None = provider không báo
    cost_usd: float | None = None  # tổng chi phí; None = provider không tính được step nào
