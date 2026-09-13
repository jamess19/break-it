"""ToolDef (định nghĩa), ToolCall (model xin gọi), ToolResult (kết quả).

domain/ ở trung tâm — KHÔNG import từ tầng nào; mọi tầng import từ đây.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolDef(BaseModel):
    """Định nghĩa 1 tool để gửi cho provider (tên, mô tả, schema tham số)."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


class ToolCall(BaseModel):
    """Model *xin* gọi 1 tool. `id` để map kết quả trả lại đúng chỗ."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Kết quả sau khi registry chạy tool — nhét lại vào history cho model."""

    call_id: str = ""  # tool không biết id; registry gắn sau khi chạy
    content: str
    is_error: bool = False
