"""wiring: chọn provider, dựng registry, mở kết nối memory + MCP.

Chỗ DUY NHẤT biết implementation cụ thể nào đang chạy. Đổi provider / Redis / Postgres
ở đây — engine/loop.py không sửa 1 dòng.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings
from app.providers.base import LLMProvider
from app.services.base import SessionMemory
from app.services.session import RedisSession
from app.services.store import FactStore
from app.services.tasks import TaskRepo
from app.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from app.mcp_client.manager import MCPClient

log = logging.getLogger("deps")


def build_provider() -> LLMProvider:
    if settings.provider == "ollama":
        from app.providers.ollama import OllamaProvider

        return OllamaProvider(settings.model, base_url=settings.ollama_base_url)
    if settings.provider == "anthropic":
        from app.providers.anthropic import AnthropicProvider

        return AnthropicProvider(settings.model, api_key=settings.anthropic_api_key)
    if settings.provider == "openai":
        from app.providers.openai import OpenAIProvider

        return OpenAIProvider(
            settings.model,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
    raise ValueError(f"Unknown provider: {settings.provider!r}")


def build_registry(tasks: TaskRepo, store: FactStore) -> ToolRegistry:
    registry = ToolRegistry()
    from app.tools.memory import register_memory_tools
    from app.tools.tasks import register_task_tools

    register_task_tools(registry, tasks)  # 9 tool quản lý việc + kế hoạch
    register_memory_tools(registry, store)  # recall / remember (Phần 5)
    # connector thật (Gmail, Calendar, Slack) → đăng ký ở đây khi có. MCP nạp riêng,
    # xem setup_mcp() — cần await nên không gọi được trong hàm sync này.
    return registry


async def setup_mcp() -> list[MCPClient]:
    """Connect tất cả server khai báo trong `mcp.json`. Gọi 1 lần lúc app khởi động
    (xem lifespan trong main.py). Trả list client ĐÃ CONNECT để đăng ký tool + đóng lúc
    shutdown.

    KHÔNG tự đăng ký vào registry nào — đó là việc của `agents/comms/tools.py::build_registry`
    (xem Phase 2 của plans/260913-1646-langgraph-orchestrator-worker/). Tạm thời (tới khi
    Phase 4 nối graph xong), `main.py::_lifespan` tự đăng ký các client này vào
    `Runtime.registry` cũ để app không bị vỡ giữa chừng khi các phase multi-agent chưa hoàn tất.
    """
    from app.mcp_client.manager import connect_all
    from app.mcp_client.registry import load_mcp_servers

    return await connect_all(load_mcp_servers(settings.mcp_config_path))


@dataclass
class Runtime:
    provider: LLMProvider
    registry: ToolRegistry
    session: SessionMemory
    store: FactStore
    tasks: TaskRepo


@lru_cache(maxsize=1)
def build_runtime() -> Runtime:
    """Dựng 1 lần, dùng lại mọi request (FastAPI Depends) — giữ connection pool."""
    tasks = TaskRepo(settings.postgres_dsn)
    store = FactStore(settings.postgres_dsn, top_k=settings.fact_top_k)
    return Runtime(
        provider=build_provider(),
        registry=build_registry(tasks, store),
        session=RedisSession(
            settings.redis_url,
            window=settings.session_window,
            ttl_seconds=settings.session_ttl_hours * 3600,
        ),
        store=store,
        tasks=tasks,
    )
