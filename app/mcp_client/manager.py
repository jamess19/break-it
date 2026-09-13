"""MCP CHỈ là 1 nguồn tool: client discover tool ngoài → đăng ký vào registry.

Nếu engine phải biết "đây là MCP" thì đã sai. Nó chỉ là nguồn tool plug vào cùng registry.
Phần 6 — agent discover + gọi được tool qua MCP server (stdio transport).

Tên tool đăng ký vào registry có prefix `<server_name>_` — tránh đụng tool native
hoặc tool của server MCP khác cùng tên (vd 2 server đều có `send_message`).
"""
from __future__ import annotations

import logging
import re
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.domain.tool import ToolDef, ToolResult
from app.mcp_client.resilience import call_with_reconnect
from app.tools.registry import ToolRegistry

log = logging.getLogger("mcp.client")

# OpenAI/Groq chỉ chấp nhận tên function [a-zA-Z0-9_-] — nhiều MCP server (vd Lark:
# "im.v1.message.create") dùng dấu chấm trong tên tool → phải thay trước khi đăng ký.
_INVALID_NAME_CHARS = re.compile(r"[^a-zA-Z0-9_-]")


def _safe_name(raw: str) -> str:
    return _INVALID_NAME_CHARS.sub("_", raw)


class MCPTool:
    """Wrap 1 tool khám phá từ MCP server thành Tool chuẩn của registry."""

    def __init__(self, server: MCPClient, definition: ToolDef) -> None:
        self._server = server
        self._definition = definition

    @property
    def definition(self) -> ToolDef:
        return self._definition

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        return await call_with_reconnect(self._server, self._definition.name, arguments)


class MCPClient:
    """1 kết nối stdio tới 1 MCP server. Sống suốt vòng đời app (xem api/deps.py
    lifespan) — connect() 1 lần lúc startup, close() lúc shutdown."""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self._command = command
        self._args = args or []
        self._env = env
        self._session: ClientSession | None = None
        self._stack = AsyncExitStack()
        self._real_name: dict[str, str] = {}  # tên đã sanitize (đăng ký registry) -> tên thật server

    async def connect(self) -> None:
        """Spawn subprocess + handshake MCP. `AsyncExitStack` giữ cả 2 context
        (stdio pipe + session) mở qua nhiều request — không dùng `async with` trực
        tiếp vì FastAPI không gọi mình trong 1 khối `with` duy nhất."""
        params = StdioServerParameters(command=self._command, args=self._args, env=self._env)
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        log.info("MCP '%s' connected (%s %s)", self.name, self._command, " ".join(self._args))

    async def close(self) -> None:
        await self._stack.aclose()
        self._session = None

    async def list_tools(self) -> list[ToolDef]:
        session = self._require_session()
        result = await session.list_tools()
        defs: list[ToolDef] = []
        for t in result.tools:
            safe = f"{self.name}_{_safe_name(t.name)}"
            self._real_name[safe] = t.name  # nhớ để call_tool() gọi đúng tên gốc
            defs.append(ToolDef(name=safe, description=t.description or "", parameters=t.input_schema))
        return defs

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        session = self._require_session()
        real_name = self._real_name.get(name, name.removeprefix(f"{self.name}_"))
        result = await session.call_tool(real_name, arguments)
        text = "\n".join(getattr(c, "text", None) or repr(c) for c in result.content)
        return ToolResult(content=text or "(rỗng)", is_error=bool(result.is_error))

    async def register_into(self, registry: ToolRegistry) -> None:
        """Điểm mấu chốt: đổ tool MCP vào cùng registry mà connector/tool native dùng."""
        defs = await self.list_tools()
        for definition in defs:
            registry.register(MCPTool(self, definition))
        log.info("MCP '%s' đăng ký %d tool: %s", self.name, len(defs), [d.name for d in defs])

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError(f"MCPClient '{self.name}' chưa connect()")
        return self._session


async def connect_all(servers: dict[str, dict[str, Any]]) -> list[MCPClient]:
    """Connect từng server trong `mcp.json` (xem registry.py::load_mcp_servers).

    1 server lỗi (chưa cài, network chết…) KHÔNG được kéo sập cả app — agent vẫn chạy
    tốt chỉ với tool native, chỉ thiếu tool của server đó. Trả list client ĐÃ CONNECT để
    gọi tiếp `register_into()` — hàm này KHÔNG tự đăng ký vào registry nào (đó là việc
    của agents/external/tools.py::build_registry, không phải của mcp_client/).
    """
    clients: list[MCPClient] = []
    for name, cfg in servers.items():
        client = MCPClient(name, cfg["command"], cfg.get("args"), cfg.get("env"))
        try:
            await client.connect()
            clients.append(client)
        except Exception:
            log.exception("MCP '%s' kết nối lỗi — bỏ qua, agent chạy tiếp không có tool này", name)
    return clients
