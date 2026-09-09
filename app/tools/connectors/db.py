"""DB connector — cho agent query dữ liệu nội bộ (read-only).

Ví dụ connector "không phải SaaS": chứng minh registry không quan tâm tool gọi ra ngoài
hay xuống DB, miễn là implement Tool interface.
"""
from __future__ import annotations

from typing import Any

from app.domain.tool import ToolDef, ToolResult


class DbQuery:
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="db.query",
            description="Chạy 1 truy vấn SELECT read-only trên DB nội bộ.",
            parameters={
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError("Phần 6 — mở kết nối, chặn không phải SELECT")
