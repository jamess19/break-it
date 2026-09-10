"""Shape bảng Postgres — CHỈ memory/ import file này.

`MessageRow` (SQLAlchemy) ≠ `domain.Message` (Pydantic). memory/ map giữa 2 bên.
Schema thật khởi tạo bằng `db/init.sql` (docker-compose chạy 1 lần). File này để ORM query.
Khi schema tiến hoá nhiều → chuyển sang Alembic autogenerate từ `Base.metadata`.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FactRow(Base):
    """Bộ nhớ dài hạn — fact user dạy agent (thói quen / ràng buộc / sở thích).

    Lấy lại bằng lọc `meta.category` hoặc load-all, KHÔNG vector — xem store.py.
    """

    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="")  # chat:remember | seed:planning
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class MessageRow(Base):
    """Archive toàn bộ hội thoại (Redis chỉ giữ N gần nhất)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, index=True)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutomationRunRow(Base):
    """Log mỗi lần cron/webhook chạy agent (Phần 7 — output được lưu)."""

    __tablename__ = "automation_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(Text)  # cron | webhook
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, default="running")  # running | ok | error
    steps: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)  # tổng (= prompt + completion)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)  # None = model chưa có giá
    output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConnectorStateRow(Base):
    """Token OAuth + con trỏ sync mỗi connector (Phần 6)."""

    __tablename__ = "connector_state"

    name: Mapped[str] = mapped_column(Text, primary_key=True)  # gmail | slack | linear
    kind: Mapped[str] = mapped_column(Text)  # connector | mcp
    status: Mapped[str] = mapped_column(Text, default="disconnected")
    credentials: Mapped[dict] = mapped_column(JSONB, default=dict)  # mã hoá ở tầng trên
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)


# ===================== Task Agent (docs/task-agent.md) =====================


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="todo", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=2)
    estimate_hours: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    project: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    source: Mapped[str] = mapped_column(Text, default="chat")  # chat | api | cron
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChecklistItemRow(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanRow(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)  # thứ Hai
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(Text, default="chat")  # chat | cron | api
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanSlotRow(Base):
    __tablename__ = "plan_slots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_hours: Mapped[float] = mapped_column(Numeric(4, 1))
    position: Mapped[int] = mapped_column(Integer, default=0)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
