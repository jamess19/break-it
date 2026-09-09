"""Provider cho OpenAI Chat Completions API — và mọi endpoint tương thích nó.

Format y hệt Ollama (xem ollama.py). Class này khác ollama.py ở đúng 2 điểm:
  - `base_url` mặc định trỏ OpenAI
  - luôn gửi header `Authorization: Bearer <api_key>`

Dùng cho: OpenAI, Groq, Gemini (endpoint compat), DeepSeek, Together, xAI, OpenRouter,
Hugging Face router — chỉ đổi `base_url` + `api_key` + `model`.

> ollama.py và file này gần như trùng nhau. Khi muốn gọn, gộp 3 hàm map vào
> `providers/_openai_format.py` dùng chung. Giữ tách để mỗi file tự đọc trọn vẹn.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.domain.message import Message, Role
from app.domain.tool import ToolCall, ToolDef


class OpenAIProvider:
    def __init__(
        self,
        model: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def chat(self, messages: list[Message], tools: list[ToolDef]) -> Message:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [self._message_to_dict(m) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = [self._tool_to_dict(t) for t in tools]

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        return self._dict_to_message(data["choices"][0]["message"])

    # ============ Message: mình <-> dict của provider ============

    @staticmethod
    def _message_to_dict(m: Message) -> dict[str, Any]:
        """domain.Message -> dict để GỬI cho provider."""
        if m.role is Role.tool and m.tool_result is not None:
            return {
                "role": "tool",
                "tool_call_id": m.tool_result.call_id,
                "content": m.tool_result.content,
            }
        if m.role is Role.assistant and m.tool_calls:
            return {
                "role": "assistant",
                "content": m.content or "",
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in m.tool_calls
                ],
            }
        return {"role": m.role.value, "content": m.content}

    @staticmethod
    def _dict_to_message(msg: dict[str, Any]) -> Message:
        """dict provider TRẢ VỀ -> domain.Message (normalize tool-call)."""
        tool_calls: list[ToolCall] = []
        for rc in msg.get("tool_calls") or []:
            fn = rc.get("function", {})
            raw = fn.get("arguments")
            if isinstance(raw, str):
                try:
                    args = json.loads(raw or "{}")
                except json.JSONDecodeError:
                    args = {}
            else:
                args = raw or {}
            tool_calls.append(
                ToolCall(
                    id=rc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    name=fn.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )

        return Message(
            role=Role.assistant,
            content=msg.get("content") or "",
            tool_calls=tool_calls,
        )

    # ============ Tool: khai báo cho provider (1 chiều) ============

    @staticmethod
    def _tool_to_dict(t: ToolDef) -> dict[str, Any]:
        """domain.ToolDef -> dict schema tool mà provider hiểu."""
        return {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
