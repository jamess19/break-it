"""entrypoint run() — MỌI trigger (api, automation, webhook) đều vào đây.

KHÔNG có execution path riêng cho automation. Trigger chỉ là input source khác.
"""
from __future__ import annotations

from pathlib import Path

from app.agents._runtime import run_loop
from app.domain.agent import AgentResult, RunContext
from app.domain.message import Message, Role
from app.providers.base import LLMProvider
from app.services.base import SessionMemory
from app.tools.registry import ToolRegistry

# Phần 3 — prompt engineering đủ để agent biết khi nào gọi tool, khi nào dừng.
# Prompt sống trong prompts/system.md, không phải string Python — version như config,
# sửa prompt không phải đụng code, đọc lại được không cần biết Python.
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8").strip()


async def run(
    session_id: str,
    user_message: str,
    *,
    provider: LLMProvider,
    registry: ToolRegistry,
    session: SessionMemory,
    trigger: str = "api",
) -> AgentResult:
    ctx = RunContext(session_id=session_id, trigger=trigger)

    history = await session.read(session_id)  # Phần 4 — history cũ của phiên
    history.append(Message(role=Role.user, content=user_message))

    result = await run_loop(ctx, history, provider, registry, system=SYSTEM_PROMPT)

    await session.write(session_id, result.messages)  # Phần 4 — lưu lại (không có system)
    return result
