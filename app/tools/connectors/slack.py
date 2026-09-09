"""Slack connector — tool "nội bộ" tự viết."""
from __future__ import annotations

from typing import Any

from app.domain.tool import ToolDef, ToolResult


class SlackReadUnread:
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="slack.read_unread",
            description="Đọc tin nhắn chưa đọc trong các kênh đã đăng ký.",
            parameters={
                "type": "object",
                "properties": {"channel": {"type": "string"}},
            },
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError("Phần 6 — gọi Slack API")
