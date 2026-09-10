"""Provider cho Anthropic Messages API.

Cùng interface LLMProvider — engine không phân biệt với Ollama/OpenAI.
Nhưng shape Anthropic khác OpenAI ở 6 điểm (chi tiết: docs/llm-providers.md §3):
  1. Auth: header `x-api-key` + `anthropic-version` (không phải Authorization: Bearer)
  2. `max_tokens` BẮT BUỘC
  3. `system` là field top-level, KHÔNG nằm trong messages
  4. `content` là mảng block, không phải string
  5. tool arguments là object (không phải JSON string)
  6. tool schema dùng `input_schema`, không có wrapper {"type":"function"}

Phần 1 — `chat()` còn stub (cần API key để test). Các hàm map đã implement làm reference.
"""
from __future__ import annotations

from typing import Any

from app.domain.message import Message, Role
from app.domain.tool import ToolCall, ToolDef
from app.util import clean_arguments

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 1024


class AnthropicProvider:
    def __init__(
        self,
        model: str,
        *,
        api_key: str = "",
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def chat(self, messages: list[Message], tools: list[ToolDef]) -> Message:
        system, convo = self._split_system(messages)  # điểm khác #3
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": DEFAULT_MAX_TOKENS,  # điểm khác #2
            "messages": [self._message_to_dict(m) for m in convo],
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [self._tool_to_dict(t) for t in tools]

        # headers = {
        #     "x-api-key": self._api_key,                 # điểm khác #1
        #     "anthropic-version": ANTHROPIC_VERSION,
        #     "content-type": "application/json",
        # }
        # POST {self._base_url}/messages  -> self._dict_to_message(resp.json())
        raise NotImplementedError("Phần 1 — gọi Anthropic Messages API")

    # ============ Message: mình <-> dict của provider ============

    @staticmethod
    def _split_system(messages: list[Message]) -> tuple[str, list[Message]]:
        """Gom mọi message role=system thành 1 string top-level; trả phần còn lại."""
        system = "\n\n".join(m.content for m in messages if m.role is Role.system)
        convo = [m for m in messages if m.role is not Role.system]
        return system, convo

    @staticmethod
    def _message_to_dict(m: Message) -> dict[str, Any]:
        """domain.Message -> dict Anthropic. (system xử lý riêng ở _split_system)"""
        if m.role is Role.tool and m.tool_result is not None:
            # kết quả tool = block trong message role=user (điểm khác #4)
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_result.call_id,
                        "content": m.tool_result.content,
                        "is_error": m.tool_result.is_error,
                    }
                ],
            }
        if m.role is Role.assistant and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for c in m.tool_calls:
                blocks.append(
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                )
            return {"role": "assistant", "content": blocks}
        return {"role": m.role.value, "content": m.content}

    @staticmethod
    def _dict_to_message(resp: dict[str, Any]) -> Message:
        """dict Anthropic TRẢ VỀ -> domain.Message.

        Khi implement chat():
          - `resp["usage"]` → domain.Usage: `input_tokens` → prompt_tokens,
            `output_tokens` → completion_tokens, total = input + output
            (Anthropic KHÔNG trả sẵn `total_tokens`).
          - `message.cost_usd`: có cache-tier (`cache_read_input_tokens` −90%,
            `cache_creation_input_tokens` +25%) → tính riêng ở `_cost()`, đừng
            dùng thẳng `util.cost` (bảng đó chỉ giá cơ bản in/out).
        """
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.get("content", []):
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=clean_arguments(block.get("input") or {}),  # dict (điểm khác #5)
                    )
                )
        return Message(
            role=Role.assistant,
            content="".join(text_parts),
            tool_calls=tool_calls,
        )

    # ============ Tool: khai báo cho provider (1 chiều) ============

    @staticmethod
    def _tool_to_dict(t: ToolDef) -> dict[str, Any]:
        """domain.ToolDef -> dict schema Anthropic (`input_schema`, không wrapper)."""
        return {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,  # điểm khác #6
        }
