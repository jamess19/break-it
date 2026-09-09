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


class Message(BaseModel):
    role: Role
    content: str = ""

    # assistant có thể xin gọi tool trong 1 lượt
    tool_calls: list[ToolCall] = Field(default_factory=list)

    # message role=tool mang kết quả 1 tool trả lại cho model
    tool_result: ToolResult | None = None
