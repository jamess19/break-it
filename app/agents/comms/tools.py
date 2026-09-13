"""Bind tool MCP cho worker `comms` — KHÔNG tự implement tool.

Điền ở Phase 2 — xem plans/260913-1646-langgraph-orchestrator-worker/phase-02-worker-agents.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from app.mcp_client.manager import MCPClient


def build_registry(mcp_clients: list[MCPClient]) -> ToolRegistry:
    raise NotImplementedError("Điền ở Phase 2")
