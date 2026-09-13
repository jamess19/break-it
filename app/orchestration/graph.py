"""Build + compile StateGraph, và hàm `run()` (entrypoint cho api/automations).

`run()` gộp CHUNG file này (không tách file run.py riêng — rxguardian/ không có khái niệm
này, xem docs/langgraph-plan.md mục 1b). `route`/`build_graph` điền ở Phase 3, `run()` điền
ở Phase 4.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.external.agent import make_node as make_external_node
from app.agents.planning.agent import make_node as make_planning_node
from app.orchestration.orchestrator import (
    MAX_ORCHESTRATOR_STEPS,
    make_orchestrator_node,
)
from app.orchestration.state import GraphState
from app.providers.base import LLMProvider
from app.tools.registry import ToolRegistry


def route(state: GraphState) -> str:
    if state.final_reply is not None:
        return "end"
    if state.steps >= MAX_ORCHESTRATOR_STEPS:  # chặn vòng lặp vô hạn, độc lập quyết định của LLM
        return "end"
    return state.next_worker or "end"


def build_graph(
    provider: LLMProvider,
    planning_registry: ToolRegistry,
    external_registry: ToolRegistry,
):
    g = StateGraph(GraphState)
    g.add_node("orchestrator", make_orchestrator_node(provider))
    g.add_node("planning", make_planning_node(provider, planning_registry))
    g.add_node("external", make_external_node(provider, external_registry))

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges(
        "orchestrator",
        route,
        {"planning": "planning", "external": "external", "end": END},
    )
    g.add_edge("planning", "orchestrator")  # worker luôn báo cáo lại, orchestrator quyết bước kế
    g.add_edge("external", "orchestrator")

    return g.compile()


async def run(session_id, user_message, *, graph, session, trigger="api"):
    raise NotImplementedError("Điền ở Phase 4")
