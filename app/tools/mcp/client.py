"""MCP CHỈ là 1 nguồn tool: client discover tool ngoài → đăng ký vào registry.

Nếu engine phải biết "đây là MCP" thì đã sai. Nó chỉ là nguồn tool plug vào cùng registry.
Phần 6 — ✅ agent discover + gọi được 1 tool qua MCP server.
"""
from __future__ import annotations

from typing import Any

from app.domain.tool import ToolDef, ToolResult
from app.tools.registry import ToolRegistry


class MCPTool:
    """Wrap 1 tool khám phá từ MCP server thành Tool chuẩn của registry."""

    def __init__(self, server: "MCPClient", definition: ToolDef) -> None:
        self._server = server
        self._definition = definition

    @property
    def definition(self) -> ToolDef:
        return self._definition

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        return await self._server.call_tool(self._definition.name, arguments)


class MCPClient:
    def __init__(self, name: str, command: list[str]) -> None:
        self._name = name
        self._command = command

    async def connect(self) -> None:
        raise NotImplementedError("Phần 6 — spawn/kết nối MCP server có sẵn")

    async def list_tools(self) -> list[ToolDef]:
        raise NotImplementedError("Phần 6 — MCP list_tools()")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError("Phần 6 — MCP call_tool()")

    async def register_into(self, registry: ToolRegistry) -> None:
        """Điểm mấu chốt: đổ tool MCP vào cùng registry mà connector dùng."""
        for definition in await self.list_tools():
            registry.register(MCPTool(self, definition))
