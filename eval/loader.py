"""Nạp case YAML → dataclass, resolve ngày tương đối.

`deadline` trong case: "mon".."sun" (neo vào thứ Hai tuần chạy eval — deterministic
bất kể hôm nay thứ mấy), "+Nd" (từ hôm nay), hoặc YYYY-MM-DD.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.memory.tasks import monday_of

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def week_monday() -> dt.date:
    return monday_of(dt.date.today())  # noqa: DTZ011 — giờ địa phương, như app/memory/tasks.py


def resolve_day(spec: str | int | None, base: dt.date) -> dt.date | None:
    if spec is None:
        return None
    if isinstance(spec, int):
        return base + dt.timedelta(days=spec)
    s = str(spec).strip().lower()
    if s in _WEEKDAYS:
        return base + dt.timedelta(days=_WEEKDAYS[s])
    if s.startswith("+") and s.endswith("d"):
        return dt.date.today() + dt.timedelta(days=int(s[1:-1]))  # noqa: DTZ011
    return dt.date.fromisoformat(s)


@dataclass
class SeedTask:
    title: str
    estimate_hours: float | None = None
    deadline: str | int | None = None
    priority: int = 2


@dataclass
class Assert:
    type: str
    params: dict = field(default_factory=dict)
    soft: bool = False  # soft = chỉ báo, không làm case FAIL (vd cap 6h/ngày — estimate do người)


@dataclass
class Case:
    id: str
    seed_tasks: list[SeedTask]
    asserts: list[Assert]
    message: str | None = None


def load_cases(path: Path) -> list[Case]:
    cases: list[Case] = []
    for c in yaml.safe_load(path.read_text()):
        asserts = []
        for a in c["asserts"]:
            a = dict(a)
            asserts.append(
                Assert(type=a.pop("type"), soft=bool(a.pop("soft", False)), params=a)
            )
        cases.append(
            Case(
                id=c["id"],
                seed_tasks=[SeedTask(**s) for s in c.get("seed_tasks", [])],
                asserts=asserts,
                message=c.get("message"),
            )
        )
    return cases
