"""AgentResult, RunContext — output & context của 1 lần run()."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.message import Message


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
    steps: int = 0
    tool_calls: int = 0
