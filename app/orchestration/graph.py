"""Build + compile StateGraph, và hàm `run()` (entrypoint cho api/automations).

`run()` gộp CHUNG file này (không tách file run.py riêng — rxguardian/ không có khái niệm
này, xem docs/langgraph-plan.md mục 1b). Điền ở Phase 3 (build_graph/route) + Phase 4 (run()).
"""

from __future__ import annotations

from app.orchestration.state import GraphState


def route(state: GraphState) -> str:
    raise NotImplementedError("Điền ở Phase 3")


def build_graph(provider, planning_registry, comms_registry):
    raise NotImplementedError("Điền ở Phase 3")


async def run(session_id, user_message, *, graph, session, trigger="api"):
    raise NotImplementedError("Điền ở Phase 4")
