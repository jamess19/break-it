"""LLMProvider interface: chat(messages, tools) -> Message.

engine/ CHỈ phụ thuộc interface này, không phụ thuộc anthropic.py / openai.py.
Thay OpenAI bằng Anthropic, hay ngược lại, engine không nhúc nhích.
"""
from __future__ import annotations

from typing import Protocol

from app.domain.message import Message
from app.domain.tool import ToolDef


class LLMProvider(Protocol):
    async def chat(self, messages: list[Message], tools: list[ToolDef]) -> Message:
        """Gọi model 1 lượt. Trả về assistant Message (có thể chứa tool_calls).

        Implementation chịu trách nhiệm:
          - map domain.Message <-> format provider
          - normalize tool-call về domain.ToolCall
            (KHÔNG để shape của Anthropic/OpenAI leak lên engine)
        """
        ...
