"""Chạy 1 case: cô lập DB → seed → orchestration.graph.run() → đọc plan → chấm.

DB: TEST_POSTGRES_DSN (default = POSTGRES_DSN). TRUNCATE các bảng liên quan giữa
mỗi case → mỗi case bắt đầu từ rỗng. CẢNH BÁO: dùng chung DB `ops_agent` thì eval
xoá sạch tasks/plans/facts hiện có.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.domain.message import Usage
from app.orchestration.graph import build_graph, run
from app.providers.openai import OpenAIProvider
from app.services.store import FactStore
from app.services.tasks import TaskRepo
from app.tools.memory import register_memory_tools
from app.tools.registry import ToolRegistry
from app.tools.tasks import register_task_tools
from eval.loader import Case, resolve_day, week_monday
from eval.scorers import Check, score

DSN = os.environ.get("TEST_POSTGRES_DSN") or settings.postgres_dsn
_TRUNCATE = "TRUNCATE plan_slots, plans, checklist_items, tasks, facts RESTART IDENTITY CASCADE"

_SEED_FACTS = [
    "Deep work tốt nhất buổi sáng 9h–12h; buổi chiều để việc nhẹ và họp.",
    "Trần khoảng 6 giờ deep work mỗi ngày — đừng xếp quá tay.",
    "Ưu tiên việc có deadline gần và priority cao (P1) trước.",
    "Task lớn hơn 3h nên tách ra nhiều ngày, không dồn 1 buổi.",
]


class _MemSession:
    """SessionMemory tạm cho eval — không đụng Redis. Mới mỗi case."""

    def __init__(self) -> None:
        self._d: dict = {}

    async def read(self, sid: str):
        return list(self._d.get(sid, []))

    async def write(self, sid: str, msgs) -> None:
        self._d[sid] = list(msgs)


def build_provider(entry: dict) -> OpenAIProvider:
    if entry["provider"] != "openai":
        raise SystemExit(
            f"eval v1 chỉ hỗ trợ provider 'openai' (OpenAI-compat). Model "
            f"{entry['name']!r} khai provider={entry['provider']!r}."
        )
    key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
    if not key:
        raise SystemExit("thiếu OPENAI_API_KEY (env hoặc .env)")
    return OpenAIProvider(entry["model"], base_url=entry["base_url"], api_key=key)


@dataclass
class CaseResult:
    case_id: str
    checks: list[Check]
    steps: int
    tool_calls: int
    usage: Usage | None
    cost_usd: float | None
    latency_ms: float
    error: str | None = None

    @property
    def passed(self) -> bool:
        """PASS = không lỗi + mọi HARD check ok. Soft check fail chỉ để báo."""
        return (
            self.error is None
            and bool(self.checks)
            and all(c.ok for c in self.checks if not c.soft)
        )

    @property
    def soft_fails(self) -> list[Check]:
        return [c for c in self.checks if c.soft and not c.ok]


async def _reset(engine) -> None:
    async with engine.begin() as c:
        await c.execute(text(_TRUNCATE))


async def run_case(case: Case, provider: OpenAIProvider, engine) -> CaseResult:
    await _reset(engine)
    repo = TaskRepo(DSN)
    store = FactStore(DSN)
    for fact in _SEED_FACTS:
        await store.write_fact(fact, source="eval", meta={"category": "planning"})

    base = week_monday()
    for st in case.seed_tasks:
        await repo.add_task(
            st.title,
            estimate_hours=st.estimate_hours,
            deadline=resolve_day(st.deadline, base),
            priority=st.priority,
            source="eval",
        )

    planning_registry = ToolRegistry()
    register_task_tools(planning_registry, repo)
    register_memory_tools(planning_registry, store)
    external_registry = ToolRegistry()  # rỗng — eval không cần MCP thật (xem Phase 4)
    graph = build_graph(provider, planning_registry, external_registry)

    msg = case.message or (
        f"Xếp lịch làm việc cho tuần bắt đầu {base}. Các việc đã có sẵn trong hệ thống — "
        f"gọi list_tasks để xem rồi save_plan các slot theo ngày."
    )

    t0 = time.perf_counter()
    try:
        res = await run(
            session_id=f"eval:{case.id}",
            user_message=msg,
            graph=graph,
            session=_MemSession(),
            trigger="api",
        )
    except Exception as e:  # noqa: BLE001 — muốn bắt mọi lỗi để case fail sạch, không vỡ suite
        return CaseResult(case.id, [], 0, 0, None, None, (time.perf_counter() - t0) * 1000, error=repr(e))
    latency_ms = (time.perf_counter() - t0) * 1000

    plan = await repo.get_plan(base)
    tasks = await repo.list_tasks()
    checks = [score(a, plan, tasks) for a in case.asserts]
    return CaseResult(
        case.id, checks, res.steps, res.tool_calls, res.usage, res.cost_usd, latency_ms
    )


async def run_suite(
    cases: list[Case], model_entry: dict, *, gap_seconds: float = 3.0
) -> list[CaseResult]:
    engine = create_async_engine(DSN)
    provider = build_provider(model_entry)
    out: list[CaseResult] = []
    try:
        for i, c in enumerate(cases):
            if i:
                await asyncio.sleep(gap_seconds)  # né rate-limit provider giữa các case
            out.append(await run_case(c, provider, engine))
    finally:
        await engine.dispose()
    return out
