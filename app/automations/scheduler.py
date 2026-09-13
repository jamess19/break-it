"""Đăng ký cron (arq) → gọi engine.run(). KHÔNG build execution path song song.

Phần 7 — ✅ 1 cron chạy agent không cần người, output được lưu (automation_runs).
Cron `daily`: roll-over việc chưa xong sang hôm nay → agent ra "focus hôm nay" + cảnh báo deadline.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import ClassVar

from app.api.deps import build_runtime
from app.engine.run import run
from app.services.runs import log_run

DAILY_PROMPT = (
    "Dựa vào get_plan của tuần này, tóm tắt việc cần làm HÔM NAY, tối đa 5 gạch đầu dòng. "
    "Gọi list_tasks để soát task có deadline trong 2 ngày tới mà kế hoạch chưa đủ giờ — "
    "nếu có thì cảnh báo. Trả lời tiếng Việt, ngắn gọn."
)


async def daily(_ctx: dict) -> None:
    rt = build_runtime()
    today = date.today()  # noqa: DTZ011 — giờ địa phương
    moved = await rt.tasks.roll_over(today - timedelta(days=1), today)
    result = await run(
        session_id="cron:daily",
        user_message=DAILY_PROMPT,
        provider=rt.provider,
        registry=rt.registry,
        session=rt.session,
        trigger="cron",
    )
    await log_run("daily", "cron", result=result, note=f"roll_over {moved} slot")


class WorkerSettings:
    """arq worker: `arq app.automations.scheduler.WorkerSettings`.

    Bật cron thật bằng cách bỏ comment cron_jobs (cần Redis chạy):
        from arq import cron
        cron_jobs = [cron(daily, hour=7, minute=0)]
    """

    functions: ClassVar = [daily]
    # from arq import cron
    # cron_jobs = [cron(daily, hour=7, minute=0)]
