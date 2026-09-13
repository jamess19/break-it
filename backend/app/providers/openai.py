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

from app.domain.message import Message, Role, Usage
from app.domain.tool import ToolCall, ToolDef
from app.providers._http import post_json
from app.util import clean_arguments, cost


def _allow_null_optionals(schema: dict[str, Any]) -> dict[str, Any]:
    """Đệ quy: prop optional (không nằm trong `required`) → type nhận thêm "null".

    Groq (và vài endpoint OpenAI-compat) validate tool-call server-side → 400
    `tool_use_failed` nếu model emit `"param": null` mà schema chỉ cho "string".
    `clean_arguments()` strip null sau khi nhận. Quirk endpoint → sống ở provider.
    """
    if not isinstance(schema, dict):
        return schema
    out = dict(schema)
    if isinstance(out.get("items"), dict):  # array of objects (vd save_plan.slots)
        out["items"] = _allow_null_optionals(out["items"])
    props = out.get("properties")
    if isinstance(props, dict):
        required = set(out.get("required") or [])
        patched = {}
        for name, spec in props.items():
            spec = _allow_null_optionals(spec)
            t = spec.get("type") if isinstance(spec, dict) else None
            if name not in required and isinstance(t, str) and t != "null":
                spec = {**spec, "type": [t, "null"]}
            patched[name] = spec
        out["properties"] = patched
    return out


class OpenAIProvider:
    def __init__(
        self,
        model: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def chat(self, messages: list[Message], tools: list[ToolDef]) -> Message:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._message_to_dict(m) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = [self._tool_to_dict(t) for t in tools]

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        data = await post_json(
            f"{self._base_url}/chat/completions",
            json=payload, headers=headers, timeout=self._timeout,
        )

        message = self._dict_to_message(data["choices"][0]["message"])
        message.usage = self._parse_usage(data.get("usage"))
        message.cost_usd = cost(message.usage, self.model)
        return message

    # ============ Message: mình <-> dict của provider ============

    @staticmethod
    def _parse_usage(u: dict[str, Any] | None) -> Usage | None:
        """`usage` của response (có mặt vì stream=False). None nếu provider bỏ trống."""
        if not u:
            return None
        prompt = u.get("prompt_tokens", 0)
        completion = u.get("completion_tokens", 0)
        return Usage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=u.get("total_tokens") or prompt + completion,
        )

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
                    arguments=clean_arguments(args) if isinstance(args, dict) else {},
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
                "parameters": _allow_null_optionals(t.parameters),
            },
        }
