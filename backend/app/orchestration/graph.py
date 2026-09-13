"""Build + compile StateGraph, và hàm `run()` (entrypoint cho api/automations).

`run()` gộp CHUNG file này (không tách file run.py riêng — rxguardian/ không có khái niệm
này, xem docs/langgraph-plan.md mục 1b). `route`/`build_graph` điền ở Phase 3, `run()` điền
ở Phase 4.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.external.agent import make_node as make_external_node
from app.agents.planning.agent import make_node as make_planning_node
from app.domain.agent import AgentResult
from app.domain.message import Message, Role
from app.orchestration.orchestrator import (
    MAX_ORCHESTRATOR_STEPS,
    make_orchestrator_node,
)
from app.orchestration.state import GraphState
from app.providers.base import LLMProvider
from app.services.base import SessionMemory
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
) -> CompiledStateGraph:
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


async def run(
    session_id: str,
    user_message: str,
    *,
    graph: CompiledStateGraph,
    session: SessionMemory,
    trigger: str = "api",
) -> AgentResult:
    history = await session.read(session_id)
    initial = GraphState(
        session_id=session_id,
        trigger=trigger,
        messages=[*history, Message(role=Role.user, content=user_message)],
    )

    raw = await graph.ainvoke(initial)
    # GraphState(**raw), KHÔNG index thẳng raw["final_reply"] — field Optional nào KHÔNG
    # node nào từng trả về (vd graph bị chặn ở MAX_ORCHESTRATOR_STEPS trước khi orchestrator
    # kịp finish) sẽ VẮNG MẶT hoàn toàn trong raw, index thẳng sẽ KeyError.
    # Verify thật: docs/langgraph.md mục 2.4b.
    final_state = GraphState(**raw)

    reply = final_state.final_reply or "(không có phản hồi — có thể đã chạm giới hạn bước)"
    new_messages = [*final_state.messages, Message(role=Role.assistant, content=reply)]
    await session.write(session_id, new_messages)

    return AgentResult(
        session_id=session_id,
        reply=reply,
        messages=new_messages,
        worker_trace=final_state.worker_trace,
        steps=final_state.steps,
        tool_calls=final_state.tool_calls,
        usage=final_state.usage,
        cost_usd=final_state.cost_usd,
    )
