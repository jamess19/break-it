"""Bind tool MCP cho worker `external` — KHÔNG tự implement tool.

`external` sở hữu tool MCP (time_*, lark_* sau này) — xem docs/langgraph-plan.md mục 5.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from app.mcp_client.manager import MCPClient


async def build_registry(mcp_clients: list[MCPClient]) -> ToolRegistry:
    registry = ToolRegistry()
    for client in mcp_clients:
        await client.register_into(registry)
    return registry
