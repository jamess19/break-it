"""Orchestrator node — quyết định worker nào chạy tiếp hoặc kết thúc.

Dùng chính cơ chế tool-calling có sẵn (2 "tool" giả: `delegate`, `finish`) — không tự làm
task, không gọi tool thật. Xem docs/langgraph-plan.md mục 4.
"""

from __future__ import annotations

from pathlib import Path

from app.agents._runtime import add_cost, add_usage
from app.domain.message import Message, Role
from app.domain.tool import ToolDef
from app.orchestration.state import GraphState
from app.providers.base import LLMProvider

PROMPT = (Path(__file__).parent / "prompts" / "orchestrator.md").read_text(encoding="utf-8").strip()

MAX_ORCHESTRATOR_STEPS = 10

DELEGATE = ToolDef(
    name="delegate",
    description="Giao việc cho 1 worker",
    parameters={
        "type": "object",
        "properties": {
            "worker": {"type": "string", "enum": ["planning", "external"]},
            "task": {"type": "string", "description": "Việc cụ thể cần worker làm"},
        },
        "required": ["worker", "task"],
    },
)

FINISH = ToolDef(
    name="finish",
    description="Kết thúc, trả lời user",
    parameters={
        "type": "object",
        "properties": {"reply": {"type": "string"}},
        "required": ["reply"],
    },
)


def _build_messages(state: GraphState) -> list[Message]:
    """Hội thoại gốc (state.messages, KHÔNG đổi bởi orchestrator) + ghi chú worker vừa
    trả lời (nếu đây không phải lượt đầu) để model có đủ ngữ cảnh quyết bước kế."""
    messages = list(state.messages)
    if state.worker_reply is not None:
        messages.append(
            Message(
                role=Role.user,
                content=f"[worker '{state.next_worker}' đã trả lời]: {state.worker_reply}",
            )
        )
    return messages


def make_orchestrator_node(provider: LLMProvider):
    async def orchestrator_node(state: GraphState) -> dict:
        assistant = await provider.chat(
            [Message(role=Role.system, content=PROMPT)] + _build_messages(state),
            [DELEGATE, FINISH],
        )
        base: dict = {
            "steps": state.steps + 1,
            "usage": add_usage(state.usage, assistant.usage),
            "cost_usd": add_cost(state.cost_usd, assistant.cost_usd),
        }

        if not assistant.tool_calls:
            # model trả text thẳng, không gọi tool nào — coi như finish (xem Risk Assessment
            # ở phase-03-orchestrator-graph.md: không tin LLM luôn tuân thủ đúng 1 trong 2 tool)
            return {**base, "final_reply": assistant.content or "(không có nội dung)"}

        call = assistant.tool_calls[0]  # bắt buộc đúng 1 — bỏ qua tool_call thừa nếu có
        if call.name == "finish":
            return {**base, "final_reply": call.arguments.get("reply") or assistant.content or ""}

        # delegate
        return {
            **base,
            "next_worker": call.arguments.get("worker"),
            "next_task": call.arguments.get("task", ""),
        }

    return orchestrator_node
