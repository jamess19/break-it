"""Test engine loop bằng fake provider — chứng minh loop chạy không cần model thật.

Đây là checkpoint Phần 3 ở dạng test: agent gọi ≥2 tool-call liên tiếp rồi dừng.
"""
from __future__ import annotations

import asyncio

import pytest

from app.agents._runtime import run_loop
from app.domain.agent import RunContext
from app.domain.message import Message, Role, Usage
from app.domain.tool import ToolCall, ToolDef, ToolResult
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
    """Lượt 1-2 xin gọi tool, lượt 3 trả lời cuối. Mỗi lượt báo usage + cost cố định."""

    model = "scripted"
    STEP_USAGE = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    STEP_COST = 0.001

    def __init__(self) -> None:
        self._turn = 0

    async def chat(self, messages: list[Message], tools: list[ToolDef]) -> Message:
        self._turn += 1
        if self._turn <= 2:
            return Message(
                role=Role.assistant,
                tool_calls=[ToolCall(id=f"c{self._turn}", name="echo", arguments={"text": "hi"})],
                usage=self.STEP_USAGE,
                cost_usd=self.STEP_COST,
            )
        return Message(
            role=Role.assistant, content="xong", usage=self.STEP_USAGE, cost_usd=self.STEP_COST
        )


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
    # usage + cost cộng dồn qua 3 lượt provider.chat
    assert result.usage is not None
    assert result.usage.total_tokens == 45
    assert result.usage.prompt_tokens == 30
    assert result.usage.completion_tokens == 15
    assert result.cost_usd == pytest.approx(0.003)
