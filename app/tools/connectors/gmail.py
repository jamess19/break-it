"""Gmail connector — tool "nội bộ" tự viết. Đăng ký vào registry như mọi tool khác.

Phần 6 — Connector thật: OAuth / API key cơ bản.
"""
from __future__ import annotations

from typing import Any

from app.domain.tool import ToolDef, ToolResult


class GmailListUnread:
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="gmail.list_unread",
            description="Liệt kê email chưa đọc; có thể lọc chỉ email được gắn cờ.",
            parameters={
                "type": "object",
                "properties": {"flagged": {"type": "boolean"}},
            },
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError("Phần 6 — gọi Gmail API")
