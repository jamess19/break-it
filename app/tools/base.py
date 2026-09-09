"""Tool interface: name, schema, run(args) -> ToolResult.

Connector tự viết và tool khám phá qua MCP đều implement interface này —
engine chỉ nhìn thấy registry, không phân biệt nguồn gốc.
"""
from __future__ import annotations

from typing import Any, Protocol

from app.domain.tool import ToolDef, ToolResult


class Tool(Protocol):
    @property
    def definition(self) -> ToolDef: ...

    async def run(self, arguments: dict[str, Any]) -> ToolResult: ...
