"""Vòng lặp agent: gửi provider → có ToolCall thì chạy qua registry → nhét lại → lặp → dừng.

Điều phối, KHÔNG tự làm I/O. Phần 3 — ✅ agent tự làm xong task cần ≥2 tool-call liên tiếp.
"""

from __future__ import annotations

import logging

from app.domain.agent import AgentResult, RunContext
from app.domain.message import Message, Role, Usage
from app.providers.base import LLMProvider
from app.tools.registry import ToolRegistry

log = logging.getLogger("agent.loop")


async def run_loop(
    ctx: RunContext,
    messages: list[Message],
    provider: LLMProvider,
    registry: ToolRegistry,
    *,
    system: str = "",
) -> AgentResult:
    tool_defs = registry.defs()
    # system prompt là CONFIG, không phải history — không lưu vào session,
    # chỉ ghép vào mỗi lần gọi provider.
    prefix = [Message(role=Role.system, content=system)] if system else []
    steps = 0
    tool_calls = 0
    usage: Usage | None = None # cộng dồn token qua các step; None nếu provider không báo
    cost_usd: float | None = None  # tổng chi phí; None nếu không step nào tính được

    while steps < ctx.max_steps:
        steps += 1
        log.info("step=%d → provider.chat (msgs=%d, tools=%d)", steps, len(prefix) + len(messages), len(tool_defs))

        assistant = await provider.chat(prefix + messages, tool_defs)
        messages.append(assistant)
        if assistant.usage is not None:
            usage = assistant.usage if usage is None else usage + assistant.usage
        if assistant.cost_usd is not None:
            cost_usd = assistant.cost_usd if cost_usd is None else cost_usd + assistant.cost_usd            

        # điều kiện dừng: model không xin thêm tool nào nữa
        if not assistant.tool_calls:
            log.info("step=%d ← reply (dừng). steps=%d tool_calls=%d", steps, steps, tool_calls)
            return AgentResult(
                session_id=ctx.session_id,
                reply=assistant.content,
                messages=messages,
                steps=steps,
                tool_calls=tool_calls,
                usage=usage,
                cost_usd=cost_usd,
            )

        # chạy từng tool, nhét kết quả lại vào history rồi lặp
        for call in assistant.tool_calls:
            tool_calls += 1
            log.info("step=%d   ↳ tool_call %s args=%s", steps, call.name, call.arguments)
            result = await registry.run(call)
            log.info("step=%d   ← %s%.150s", steps,
                     "[ERROR] " if result.is_error else "", result.content)
            messages.append(
                Message(role=Role.tool, content=result.content, tool_result=result)
            )

    # chạm max_steps → dừng cưỡng bức (tránh loop vô hạn)
    log.warning("chạm max_steps=%d — dừng cưỡng bức", ctx.max_steps)
    return AgentResult(
        session_id=ctx.session_id,
        reply=messages[-1].content or "(đạt giới hạn số bước)",
        messages=messages,
        steps=steps,
        tool_calls=tool_calls,
        usage=usage,
        cost_usd=cost_usd,
    )
