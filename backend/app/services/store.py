"""Memory dài hạn — fact user dạy agent (thói quen, ràng buộc, sở thích).

Fact cá nhân ít và cần ĐẦY ĐỦ (đừng để agent sót) → KHÔNG dùng vector/RAG.
`search` lấy fact theo:
- `categories` (agent truyền, vd "planning") → lọc chính xác qua `meta.category`
- không truyền → toàn bộ fact gần đây (đủ nhỏ để nhét thẳng vào prompt)

RAG (embedding + pgvector) chỉ đáng khi fact vượt vài nghìn / ingest nội dung
connector. Xem docs/roadmap.md Phase 0 + docs/database.md.

Map domain (str) ↔ FactRow xảy ra Ở ĐÂY. Engine chỉ thấy list[str].
"""

from __future__ import annotations

from sqlalchemy import func, nullslast, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.tables import FactRow


class FactStore:
    def __init__(self, dsn: str, top_k: int = 20) -> None:
        self._engine = create_async_engine(dsn)
        self._Session = async_sessionmaker(self._engine, expire_on_commit=False)
        self._k = top_k

    async def write_fact(
        self, text: str, *, source: str = "", meta: dict | None = None
    ) -> None:
        async with self._Session() as s, s.begin():
            s.add(FactRow(text=text, source=source, meta=meta or {}))

    async def search(
        self,
        query: str = "",
        *,
        categories: list[str] | None = None,
        k: int | None = None,
    ) -> list[str]:
        """`query` giữ cho tương thích interface — lọc thật bằng `categories`.
        Không có `categories` → trả toàn bộ fact, dùng gần đây / mới nhất trước.
        """
        k = k or self._k
        async with self._Session() as s:
            stmt = select(FactRow.id, FactRow.text)
            if categories:
                stmt = stmt.where(FactRow.meta["category"].astext.in_(categories))
            stmt = stmt.order_by(
                nullslast(FactRow.last_used_at.desc()),
                FactRow.created_at.desc(),
            ).limit(k)
            rows = (await s.execute(stmt)).all()
            if rows:
                await s.execute(
                    update(FactRow)
                    .where(FactRow.id.in_([r.id for r in rows]))
                    .values(use_count=FactRow.use_count + 1, last_used_at=func.now())
                )
                await s.commit()
            return [r.text for r in rows]
