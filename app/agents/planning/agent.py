"""Node cho worker `planning` — bọc run_loop(), export make_node(provider, registry).

Điền ở Phase 2 — xem plans/260913-1646-langgraph-orchestrator-worker/phase-02-worker-agents.md
"""

from __future__ import annotations

from app.orchestration.state import GraphState


def make_node(provider, registry):
    async def node(state: GraphState) -> dict:
        raise NotImplementedError("Điền ở Phase 2")

    return node
