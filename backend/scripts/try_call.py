"""Phần 1 checkpoint: gọi model local, in ra câu trả lời.

    python -m scripts.try_call
    python -m scripts.try_call "Viết cho tôi 1 câu haiku về mùa thu"

✅ khi thấy câu trả lời in ra từ model đang chạy trong Ollama.
"""
from __future__ import annotations

import asyncio
import sys

from app.api.deps import build_provider
from app.core.config import settings
from app.domain.message import Message, Role


async def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Chào! Trả lời ngắn gọn: bạn là model gì?"
    provider = build_provider()

    print(f"provider={settings.provider}  model={settings.model}\n> {prompt}\n")
    reply = await provider.chat([Message(role=Role.user, content=prompt)], tools=[])
    print(reply.content or "(model không trả về text)")


if __name__ == "__main__":
    asyncio.run(main())
