"""Orchestrator node — quyết định worker nào chạy tiếp hoặc kết thúc.

Điền ở Phase 3 — xem plans/260913-1646-langgraph-orchestrator-worker/phase-03-orchestrator-graph.md
"""

from __future__ import annotations

from app.orchestration.state import GraphState

MAX_ORCHESTRATOR_STEPS = 10


async def orchestrator_node(state: GraphState) -> dict:
    raise NotImplementedError("Điền ở Phase 3")
