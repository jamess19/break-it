"""`/chat` — nhận request → map sang domain → run() → map kết quả ra response.

api/ chỉ chạm engine.run() — không đụng nội tạng loop.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agents._runtime import trace
from app.api.deps import Runtime, build_runtime
from app.api.schemas import ChatRequest, ChatResponse
from app.engine.run import run

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
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
        usage=result.usage.model_dump() if result.usage else None,
        cost_usd=result.cost_usd,
        trace=trace(result.messages),
    )


@router.get("/history")
async def chat_history(
    session_id: str,
    rt: Runtime = Depends(build_runtime),  # noqa: B008
) -> dict:
    """History đã lưu của 1 session (Redis — tối đa SESSION_WINDOW message, TTL 7 ngày).

    Frontend gọi lúc load để hiện lại hội thoại. Muốn xem session cũ hơn window /
    hết TTL → cần archive vào bảng `messages` (Postgres, hiện chưa ghi).
    """
    msgs = await rt.session.read(session_id)
    return {"session_id": session_id, "trace": trace(msgs)}
