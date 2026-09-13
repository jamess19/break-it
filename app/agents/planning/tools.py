"""Bind tool cho worker `planning` — KHÔNG tự implement tool (logic thật ở app/tools/).

Điền ở Phase 2 — xem plans/260913-1646-langgraph-orchestrator-worker/phase-02-worker-agents.md
"""

from __future__ import annotations

from app.services.store import FactStore
from app.services.tasks import TaskRepo
from app.tools.registry import ToolRegistry


def build_registry(tasks: TaskRepo, store: FactStore) -> ToolRegistry:
    raise NotImplementedError("Điền ở Phase 2")
