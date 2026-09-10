"""ChatRequest, ChatResponse — shape của HTTP, KHÔNG phải domain.

HTTP schema không trôi xuống service. Biên HTTP dịch ChatRequest → domain.Message
ngay tại route (xem routes.py); nếu không, framework web rò rỉ tận engine.
"""
from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str

# trả usage và cost để người dùng biết model đang dùng tốn bao nhiêu token, bao nhiêu tiền.
# sẽ đổi sang cờ alert + setup ngưỡng ở phase sau
class ChatResponse(BaseModel):
    session_id: str
    reply: str
    steps: int
    tool_calls: int
    usage: dict | None = None
    cost_usd: float | None = None  # None = model chưa có trong app/util.py
    # trace: từng message của loop (user/assistant/tool) — để soi từng step trong Postman.
    # Là list[dict] chứ không phải domain.Message → không leak domain lên biên HTTP.
    trace: list[dict] = []
