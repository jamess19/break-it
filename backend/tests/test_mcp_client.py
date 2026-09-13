"""MCPClient: map mcp.types → domain, prefix tên tool. Session giả — không spawn
server thật (đó là việc của `connect()`, test riêng bằng tay với `mcp-server-time`)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.domain.tool import ToolCall
from app.mcp_client.manager import MCPClient
from app.tools.registry import ToolRegistry


def _tool(name: str, description: str = "", schema: dict | None = None):
    return SimpleNamespace(
        name=name, description=description, input_schema=schema or {"type": "object", "properties": {}}
    )


def _text(s: str):
    return SimpleNamespace(text=s)


class _FakeSession:
    """Đứng thay `mcp.ClientSession` — chỉ implement 2 method MCPClient gọi."""

    def __init__(self, tools: list, call_result) -> None:
        self._tools = tools
        self._call_result = call_result
        self.called_with: tuple | None = None

    async def list_tools(self):
        return SimpleNamespace(tools=self._tools)

    async def call_tool(self, name: str, arguments: dict):
        self.called_with = (name, arguments)
        return self._call_result


def _client(tools: list, call_result=None) -> tuple[MCPClient, _FakeSession]:
    client = MCPClient("time", command="uvx", args=["mcp-server-time"])
    fake = _FakeSession(tools, call_result)
    client._session = fake  # type: ignore[assignment]  — bypass connect() thật
    return client, fake


def test_list_tools_prefixes_name_and_maps_schema():
    tools = [_tool("get_current_time", "Giờ hiện tại", {"type": "object", "properties": {"tz": {"type": "string"}}})]
    client, _ = _client(tools)

    defs = asyncio.run(client.list_tools())

    assert [d.name for d in defs] == ["time_get_current_time"]
    assert defs[0].parameters["properties"]["tz"]["type"] == "string"


def test_call_tool_strips_prefix_before_calling_server():
    result = SimpleNamespace(content=[_text("14:05"), _text("Asia/Ho_Chi_Minh")], is_error=False)
    client, fake = _client([], call_result=result)

    out = asyncio.run(client.call_tool("time_get_current_time", {"tz": "Asia/Ho_Chi_Minh"}))

    assert fake.called_with == ("get_current_time", {"tz": "Asia/Ho_Chi_Minh"})
    assert out.content == "14:05\nAsia/Ho_Chi_Minh"
    assert out.is_error is False


def test_call_tool_propagates_is_error():
    result = SimpleNamespace(content=[_text("timezone không hợp lệ")], is_error=True)
    client, _ = _client([], call_result=result)

    out = asyncio.run(client.call_tool("time_get_current_time", {}))

    assert out.is_error is True


def test_list_tools_sanitizes_dotted_names_for_openai_function_naming():
    # Lark-mcp style: tool id gốc có dấu chấm ("im.v1.message.create") — OpenAI/Groq
    # không cho dấu chấm trong tên function, phải thay bằng "_" khi đăng ký.
    tools = [_tool("im.v1.message.create", "Gửi tin nhắn")]
    client, _ = _client(tools)

    defs = asyncio.run(client.list_tools())

    assert defs[0].name == "time_im_v1_message_create"


def test_call_tool_maps_sanitized_name_back_to_real_server_name():
    tools = [_tool("im.v1.message.create")]
    result = SimpleNamespace(content=[_text("ok")], is_error=False)
    client, fake = _client(tools, call_result=result)
    asyncio.run(client.list_tools())  # điền _real_name

    asyncio.run(client.call_tool("time_im_v1_message_create", {"chat_id": "oc_x"}))

    assert fake.called_with == ("im.v1.message.create", {"chat_id": "oc_x"})


def test_register_into_wires_tool_through_registry_and_back_to_server():
    tools = [_tool("ping")]
    result = SimpleNamespace(content=[_text("pong")], is_error=False)
    client, fake = _client(tools, result)
    registry = ToolRegistry()

    asyncio.run(client.register_into(registry))
    out = asyncio.run(registry.run(ToolCall(id="c1", name="time_ping", arguments={})))

    assert fake.called_with == ("ping", {})
    assert out.content == "pong"
