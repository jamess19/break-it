"""Message, Role — shape hội thoại engine truyền qua lại.

Đây là "tiền tệ" ở giữa: engine sống hoàn toàn trong thế giới domain/ này —
không biết gì về HTTP (api/schemas.py) lẫn bảng SQL (memory/tables.py).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.domain.tool import ToolCall, ToolResult


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Usage(BaseModel):
    """Token 1 (hoặc nhiều, khi cộng dồn) lần gọi LLM. Provider điền, loop cộng lại."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: Usage | None) -> Usage:
        if other is None:
            return self
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class Message(BaseModel):
    role: Role
    content: str = ""

    # assistant có thể xin gọi tool trong 1 lượt
    tool_calls: list[ToolCall] = Field(default_factory=list)

    # message role=tool mang kết quả 1 tool trả lại cho model
    tool_result: ToolResult | None = None

    # assistant message: token + chi phí lượt gọi này (provider điền; None nếu
    # provider không báo usage / model chưa có trong util.py)
    usage: Usage | None = None
    cost_usd: float | None = None
