"""ChatRequest, ChatResponse — shape của HTTP, KHÔNG phải domain.

HTTP schema không trôi xuống service. Biên HTTP dịch ChatRequest → domain.Message
ngay tại route (xem routes.py); nếu không, framework web rò rỉ tận engine.
"""
from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    steps: int
    tool_calls: int
    # trace: từng message của loop (user/assistant/tool) — để soi từng step trong Postman.
    # Là list[dict] chứ không phải domain.Message → không leak domain lên biên HTTP.
    trace: list[dict] = []
