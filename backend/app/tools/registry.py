"""Nơi DUY NHẤT engine thấy tool — connector & MCP cùng đăng ký vào đây."""
from __future__ import annotations

from app.domain.tool import ToolCall, ToolDef, ToolResult
from app.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.definition.name] = tool

    def defs(self) -> list[ToolDef]:
        """Danh sách ToolDef để đính vào mỗi lần provider.chat()."""
        return [t.definition for t in self._tools.values()]

    async def run(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(
                call_id=call.id,
                content=f"Unknown tool: {call.name}",
                is_error=True,
            )
        try:
            result = await tool.run(call.arguments)
        except Exception as exc:  # noqa: BLE001 — lỗi tool không được giết cả loop
            return ToolResult(call_id=call.id, content=repr(exc), is_error=True)
        result.call_id = call.id  # tool không cần biết id — registry gắn để khớp tool_call
        return result
