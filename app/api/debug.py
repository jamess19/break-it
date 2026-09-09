"""Endpoint gỡ lỗi — gọi TỪNG tầng riêng lẻ để soi từng step.

Chỉ dùng khi dev. Không có auth, phơi bày nội tạng — đừng bật ở production.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import Runtime, build_runtime
from app.config import settings
from app.domain.message import Message, Role
from app.domain.tool import ToolCall
from app.engine.run import SYSTEM_PROMPT

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/config")
async def show_config():
    """Xem app THỰC SỰ nạp gì từ .env (key bị che)."""
    def mask(s: str) -> str:
        return f"{s[:6]}…{s[-4:]}" if len(s) > 12 else ("(set)" if s else "(trống)")

    return {
        "provider": settings.provider,
        "model": settings.model,
        "ollama_base_url": settings.ollama_base_url,
        "openai_base_url": settings.openai_base_url,
        "openai_api_key": mask(settings.openai_api_key),
        "anthropic_api_key": mask(settings.anthropic_api_key),
        "session_window": settings.session_window,
    }


@router.get("/tools")
async def list_tools(rt: Runtime = Depends(build_runtime)):  # noqa: B008
    """Xem tool nào đang đăng ký + schema gửi cho model."""
    return [d.model_dump() for d in rt.registry.defs()]


class ToolRunBody(BaseModel):
    name: str
    arguments: dict = {}


@router.post("/tool")
async def run_tool(body: ToolRunBody, rt: Runtime = Depends(build_runtime)):  # noqa: B008
    """Chạy 1 tool trực tiếp (bỏ qua LLM) — kiểm tra tool hoạt động đúng."""
    result = await rt.registry.run(
        ToolCall(id="dbg", name=body.name, arguments=body.arguments)
    )
    return result.model_dump()


class LLMBody(BaseModel):
    message: str
    use_tools: bool = True
    use_system: bool = True


@router.post("/llm")
async def call_llm(body: LLMBody, rt: Runtime = Depends(build_runtime)):  # noqa: B008
    """1 lần provider.chat() — xem model trả text hay tool_calls (không chạy loop)."""
    msgs = [Message(role=Role.user, content=body.message)]
    if body.use_system:
        msgs.insert(0, Message(role=Role.system, content=SYSTEM_PROMPT))
    tools = rt.registry.defs() if body.use_tools else []
    reply = await rt.provider.chat(msgs, tools)
    return reply.model_dump()


@router.get("/session/{session_id}")
async def dump_session(session_id: str, rt: Runtime = Depends(build_runtime)):  # noqa: B008
    """Xem history đang lưu của 1 session (Phần 4)."""
    msgs = await rt.session.read(session_id)
    return [m.model_dump() for m in msgs]
