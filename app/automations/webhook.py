"""Nhận event ngoài → run(). Trigger chỉ là input source khác, không có path riêng."""
from __future__ import annotations

from app.api.deps import build_runtime
from app.engine.run import run


async def handle_event(payload: dict) -> None:
    rt = build_runtime()
    session_id = f"webhook:{payload.get('source', 'unknown')}"
    message = payload.get("summary", "")
    await run(
        session_id=session_id,
        user_message=message,
        provider=rt.provider,
        registry=rt.registry,
        session=rt.session,
        trigger="webhook",
    )
