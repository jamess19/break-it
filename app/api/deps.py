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


async def setup_mcp(registry: ToolRegistry) -> list[MCPClient]:
    """Connect từng server trong `mcp.json` + đăng ký tool vào registry. Gọi 1 lần
    lúc app khởi động (xem lifespan trong main.py). Trả list client để đóng lúc shutdown.

    1 server lỗi (server chưa cài, network chết…) KHÔNG được kéo sập cả app —
    agent vẫn chạy tốt chỉ với tool native, chỉ thiếu tool của server đó.
    """
    from app.mcp_client.manager import MCPClient
    from app.mcp_client.registry import load_mcp_servers

    clients: list[MCPClient] = []
    for name, cfg in load_mcp_servers(settings.mcp_config_path).items():
        client = MCPClient(name, cfg["command"], cfg.get("args"), cfg.get("env"))
        try:
            await client.connect()
            await client.register_into(registry)
            clients.append(client)
        except Exception:  # MCP tuỳ chọn — lỗi 1 server không được giết cả app
            log.exception("MCP '%s' kết nối lỗi — bỏ qua, agent chạy tiếp không có tool này", name)
    return clients


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
