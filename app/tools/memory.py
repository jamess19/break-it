"""Tool nối agent vào bộ nhớ dài hạn (Phần 5) — recall / remember.

Thay vì nhồi fact vào mọi prompt, để model TỰ gọi recall khi cần (vd trước khi xếp lịch).
Rẻ token hơn và model chủ động hơn. `remember` cho user dạy thói quen qua chat.

Không vector: recall lọc theo `category` hoặc trả toàn bộ fact gần đây (xem store.py).
"""

from __future__ import annotations

from typing import Any

from app.domain.tool import ToolDef, ToolResult
from app.memory.store import FactStore

_CATEGORY_DESC = (
    "Nhóm fact, nếu biết: 'planning' (thói quen xếp lịch), 'preference', hoặc tên tự đặt. "
    "Bỏ trống để lấy tất cả."
)


class Recall:
    def __init__(self, store: FactStore) -> None:
        self._store = store

    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="recall",
            description=(
                "Nhớ lại thói quen / sở thích / ràng buộc làm việc đã lưu của user. "
                "Gọi TRƯỚC khi xếp lịch tuần, hoặc khi cần biết user muốn làm việc thế nào."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "chủ đề cần nhớ lại (mô tả tự do)"},
                    "category": {"type": "string", "description": _CATEGORY_DESC},
                },
            },
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        cat = (arguments.get("category") or "").strip()
        hits = await self._store.search(
            arguments.get("query", ""),
            categories=[cat] if cat else None,
        )
        if not hits:
            return ToolResult(content="(không có ghi chú liên quan)")
        return ToolResult(content="\n".join(f"- {h}" for h in hits))


class Remember:
    def __init__(self, store: FactStore) -> None:
        self._store = store

    @property
    def definition(self) -> ToolDef:
        return ToolDef(
            name="remember",
            description=(
                "Lưu 1 thói quen / sở thích / ràng buộc lâu dài của user để dùng sau này "
                "(vd 'thứ 6 nghỉ chiều', 'không họp trước 9h'). Không dùng cho task cụ thể."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "fact": {"type": "string"},
                    "category": {"type": "string", "description": _CATEGORY_DESC},
                },
                "required": ["fact"],
            },
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        fact = (arguments.get("fact") or "").strip()
        if not fact:
            return ToolResult(content="fact trống", is_error=True)
        cat = (arguments.get("category") or "").strip()
        await self._store.write_fact(
            fact, source="chat:remember", meta={"category": cat} if cat else None
        )
        return ToolResult(content=f"Đã ghi nhớ: {fact}")


def register_memory_tools(registry, store: FactStore) -> None:
    registry.register(Recall(store))
    registry.register(Remember(store))
