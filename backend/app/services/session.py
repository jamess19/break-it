"""Memory ngắn hạn — history 1 phiên, lưu trong Redis.

Phần 4 — ✅ agent nhớ context qua nhiều lượt trong 1 session.
Bẫy: history phình vô hạn → vượt context limit → cắt theo window.

Map domain.Message ↔ JSON xảy ra Ở ĐÂY (model_dump_json). Engine không thấy Redis.
"""

from __future__ import annotations

import redis.asyncio as redis

from app.domain.message import Message, Role


class RedisSession:
    def __init__(self, url: str, window: int = 20, ttl_seconds: int = 7 * 24 * 3600) -> None:
        self._r = redis.from_url(url, decode_responses=True)
        self._window = window
        self._ttl = ttl_seconds

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}:messages"

    async def read(self, session_id: str) -> list[Message]:
        raw = await self._r.lrange(self._key(session_id), 0, -1)
        return [Message.model_validate_json(x) for x in raw]

    async def write(self, session_id: str, messages: list[Message]) -> None:
        key = self._key(session_id)
        trimmed = self._trim(messages)
        pipe = self._r.pipeline()
        pipe.delete(key)
        if trimmed:
            pipe.rpush(key, *[m.model_dump_json() for m in trimmed])
        pipe.expire(key, self._ttl)
        await pipe.execute()

    def _trim(self, messages: list[Message]) -> list[Message]:
        """Giữ ~window message gần nhất, bắt đầu từ 'user' đầu tiên trong window
        để không bỏ lại 'tool' / 'assistant' mồ côi (mất tool_call đi kèm)."""
        window = messages[-self._window :]
        for i, m in enumerate(window):
            if m.role is Role.user:
                return window[i:]
        return window
