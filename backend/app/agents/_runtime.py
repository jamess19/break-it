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


def trace(messages: list[Message]) -> list[dict]:
    """domain.Message[] → list[dict] gọn để đọc trong Postman/debug.

    Dùng chung bởi mọi agent (đọc kết quả `run_loop()` để trả `worker_trace` trong
    GraphState — xem docs/langgraph-plan.md mục 3) VÀ `api/chat.py` (đọc history session).
    Trước đây là `_trace()` riêng trong `api/chat.py` — chuyển vào đây vì cả 2 nơi đều cần,
    và `api/` không phải nơi các agent nên import ngược lại.
    """
    out: list[dict] = []
    for m in messages:
        row: dict = {"role": m.role.value, "content": m.content}
        if m.tool_calls:
            row["tool_calls"] = [
                {"name": c.name, "arguments": c.arguments} for c in m.tool_calls
            ]
        if m.tool_result is not None:
            row["tool_error"] = m.tool_result.is_error
        out.append(row)
    return out


def add_cost(a: float | None, b: float | None) -> float | None:
    """Cộng 2 `cost_usd` an toàn với `None` ("chưa đo được", KHÔNG phải 0 — xem CLAUDE.md
    mục Usage/cost tracking). `None` + số = số đó, `None` + `None` = `None`."""
    if a is None:
        return b
    if b is None:
        return a
    return a + b


def add_usage(a: Usage | None, b: Usage | None) -> Usage | None:
    """Cộng 2 `Usage` an toàn với `None` ở CẢ 2 bên. `Usage.__add__` (domain/message.py) chỉ
    xử lý `self + None` (`other is None`) — không xử lý `None + Usage` (khi cộng dồn bắt đầu
    từ `state.usage=None`, trường hợp rất hay gặp ở lượt đầu tiên của orchestrator/worker)."""
    if a is None:
        return b
    if b is None:
        return a
    return a + b
