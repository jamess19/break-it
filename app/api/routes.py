"""nhận request → map sang domain → run() → map kết quả ra response.

api/ chỉ chạm engine.run() — không đụng nội tạng loop.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import Runtime, build_runtime
from app.api.schemas import ChatRequest, ChatResponse
from app.domain.message import Message
from app.engine.run import run

router = APIRouter()


def _trace(messages: list[Message]) -> list[dict]:
    """domain.Message[] → list[dict] gọn để đọc trong Postman."""
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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> ChatResponse:
    # BIÊN VÀO: rời thế giới HTTP — ChatRequest → tham số domain
    result = await run(
        session_id=req.session_id,
        user_message=req.message,
        provider=rt.provider,
        registry=rt.registry,
        session=rt.session,
        trigger="api",
    )
    return ChatResponse(
        session_id=result.session_id,
        reply=result.reply,
        steps=result.steps,
        tool_calls=result.tool_calls,
        trace=_trace(result.messages),
    )
