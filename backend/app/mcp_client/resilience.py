"""Resilience cho MCP qua stdio/subprocess — KHÔNG phải HTTP retry/circuit-breaker.

rxGuardian dùng transport HTTP (`streamable-http`), có timeout/retry/circuit-breaker đúng
nghĩa mạng. Server ở đây chạy qua subprocess (`stdio_client`) — rủi ro thật là subprocess
crash/hang, không phải lỗi mạng. Phạm vi cố tình nhỏ: phát hiện lỗi khi gọi tool, reconnect
ĐÚNG 1 LẦN rồi thử lại — không retry vô hạn (personal-scale, ưu tiên fail-fast + log hơn retry
storm). Không làm circuit breaker nhiều state/threshold — 1-2 MCP server hiện tại không cần.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domain.tool import ToolResult

if TYPE_CHECKING:
    from app.mcp_client.manager import MCPClient

log = logging.getLogger("mcp.resilience")


async def call_with_reconnect(client: MCPClient, name: str, arguments: dict[str, Any]) -> ToolResult:
    """Gọi `client.call_tool()`; nếu lỗi (subprocess chết/hang), reconnect 1 lần rồi thử lại.

    Lỗi lần 2 (sau reconnect) được để văng ra ngoài nguyên vẹn — không nuốt lỗi,
    `ToolRegistry.run()` (tầng gọi hàm này) đã có chỗ biến exception thành `ToolResult(is_error=True)`.
    """
    try:
        return await client.call_tool(name, arguments)
    except Exception:
        log.exception("MCP '%s' lỗi khi gọi '%s' — thử reconnect 1 lần", client.name, name)
        await client.close()
        await client.connect()
        return await client.call_tool(name, arguments)
