"""Test engine loop bằng fake provider — chứng minh loop chạy không cần model thật.

Đây là checkpoint Phần 3 ở dạng test: agent gọi ≥2 tool-call liên tiếp rồi dừng.
"""
from __future__ import annotations

import asyncio

from app.domain.agent import RunContext
from app.domain.message import Message, Role
from app.domain.tool import ToolCall, ToolDef, ToolResult
from app.engine.loop import run_loop
from app.tools.registry import ToolRegistry


class EchoTool:
    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="echo",
            description="Trả lại đúng chuỗi nhận vào.",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        )

    async def run(self, arguments: dict) -> ToolResult:
        return ToolResult(call_id="", content=arguments.get("text", ""))


class ScriptedProvider:
    """Lượt 1-2 xin gọi tool, lượt 3 trả lời cuối."""

    def __init__(self) -> None:
        self._turn = 0

    async def chat(self, messages: list[Message], tools: list[ToolDef]) -> Message:
        self._turn += 1
        if self._turn <= 2:
            return Message(
                role=Role.assistant,
                tool_calls=[ToolCall(id=f"c{self._turn}", name="echo", arguments={"text": "hi"})],
            )
        return Message(role=Role.assistant, content="xong")


def test_loop_runs_two_tool_calls_then_stops() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())

    result = asyncio.run(
        run_loop(
            RunContext(session_id="t"),
            [Message(role=Role.user, content="làm gì đó")],
            ScriptedProvider(),
            registry,
        )
    )

    assert result.reply == "xong"
    assert result.tool_calls == 2
    assert result.steps == 3
