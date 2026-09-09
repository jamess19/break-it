"""entrypoint run() — MỌI trigger (api, automation, webhook) đều vào đây.

KHÔNG có execution path riêng cho automation. Trigger chỉ là input source khác.
"""
from __future__ import annotations

from app.domain.agent import AgentResult, RunContext
from app.domain.message import Message, Role
from app.engine.loop import run_loop
from app.memory.base import SessionMemory
from app.providers.base import LLMProvider
from app.tools.registry import ToolRegistry

# Phần 3 — prompt engineering đủ để agent biết khi nào gọi tool, khi nào dừng.
SYSTEM_PROMPT = (
    "Bạn là trợ lý quản lý công việc cá nhân. Dùng tool để đọc/ghi task và kế hoạch "
    "thật, KHÔNG được đoán dữ liệu. "
    "Khi user liệt kê nhiều việc, tách từng việc và gọi add_task cho mỗi việc. "
    "Khi user nhờ xếp lịch tuần: gọi recall lấy thói quen, list_tasks lấy việc chưa "
    "xong, rồi save_plan với các slot theo ngày — tôn trọng trần ~6h làm việc/ngày "
    "và deadline. "
    "Khi đã đủ thông tin, trả lời thẳng bằng tiếng Việt, ngắn gọn, KHÔNG gọi thêm tool."
)


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
