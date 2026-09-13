"""Interface memory: read / write / search. Memory làm chủ shape DB — engine không thấy bảng."""
from __future__ import annotations

from typing import Protocol

from app.domain.message import Message


class SessionMemory(Protocol):
    """Ngắn hạn — history trong 1 phiên (Phần 4)."""

    async def read(self, session_id: str) -> list[Message]: ...
    async def write(self, session_id: str, messages: list[Message]) -> None: ...


class FactStore(Protocol):
    """Dài hạn — fact user dạy agent, lấy lại bằng lọc category / load-all (Phần 5)."""

    async def write_fact(
        self, text: str, *, source: str = "", meta: dict | None = None
    ) -> None: ...
    async def search(
        self, query: str = "", *, categories: list[str] | None = None, k: int | None = None
    ) -> list[str]: ...
