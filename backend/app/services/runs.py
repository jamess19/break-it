"""Ghi log mỗi lần automation (cron/webhook) chạy agent — bảng automation_runs.

Checkpoint Phần 7: cron chạy không cần người, output ĐƯỢC LƯU (để xem lại sau).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.domain.agent import AgentResult
from app.services.tables import AutomationRunRow

_engine = create_async_engine(settings.postgres_dsn)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


async def log_run(
    name: str,
    trigger: str,
    *,
    result: AgentResult | None = None,
    error: str | None = None,
    note: str = "",
) -> None:
    output = result.reply if result else ""
    if note:
        output = f"{output}\n[note] {note}".strip()
    usage = result.usage if result else None
    async with _Session() as s, s.begin():
        s.add(
            AutomationRunRow(
                name=name,
                trigger=trigger,
                finished_at=datetime.now(timezone.utc),
                status="error" if error else "ok",
                steps=result.steps if result else 0,
                tool_calls=result.tool_calls if result else 0,
                tokens=usage.total_tokens if usage else 0,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                cost_usd=result.cost_usd if result else None,
                output=output,
                error=error,
            )
        )
