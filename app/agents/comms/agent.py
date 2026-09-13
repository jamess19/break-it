"""Node cho worker `comms` — bọc run_loop(), export make_node(provider, registry)."""

from __future__ import annotations

from pathlib import Path

from app.agents._runtime import add_cost, run_loop, trace
from app.domain.agent import RunContext
from app.domain.message import Message, Role
from app.orchestration.state import GraphState
from app.providers.base import LLMProvider
from app.tools.registry import ToolRegistry

PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8").strip()


def make_node(provider: LLMProvider, registry: ToolRegistry):
    async def node(state: GraphState) -> dict:
        ctx = RunContext(session_id=state.session_id, trigger=state.trigger)
        result = await run_loop(
            ctx,
            [Message(role=Role.user, content=state.next_task or "")],
            provider,
            registry,
            system=PROMPT,
        )
        return {
            "worker_reply": result.reply,
            "worker_trace": trace(result.messages),
            "tool_calls": state.tool_calls + result.tool_calls,
            "usage": (state.usage + result.usage) if result.usage else state.usage,
            "cost_usd": add_cost(state.cost_usd, result.cost_usd),
        }

    return node
