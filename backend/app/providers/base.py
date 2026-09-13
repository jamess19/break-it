"""LLMProvider interface: chat(messages, tools) -> Message.

engine/ CHỈ phụ thuộc interface này, không phụ thuộc anthropic.py / openai.py.
Thay OpenAI bằng Anthropic, hay ngược lại, engine không nhúc nhích.
"""
from __future__ import annotations

from typing import Protocol

from app.domain.message import Message
from app.domain.tool import ToolDef


class ProviderHTTPError(RuntimeError):
    """Lỗi HTTP từ provider sau khi hết retry — status (0 = lỗi mạng) + body để debug.

    Ở `base.py` (không phải `_http.py`) vì là error contract của provider: biên
    `api/` bắt nó để map ra 429/502 thay vì 500."""

    def __init__(self, status: int, url: str, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status} từ {url} — {body[:800]}")


class LLMProvider(Protocol):
    # define model trong LLM provider
    model: str
    async def chat(self, messages: list[Message], tools: list[ToolDef]) -> Message:
        """Gọi model 1 lượt. Trả về assistant Message (có thể chứa tool_calls).

        Implementation chịu trách nhiệm:
          - map domain.Message <-> format provider
          - normalize tool-call về domain.ToolCall
            (KHÔNG để shape của Anthropic/OpenAI leak lên engine)
        """
        ...
