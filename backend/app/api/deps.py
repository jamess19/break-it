"""wiring: chọn provider, dựng graph (orchestrator + worker), mở kết nối memory + MCP.

Chỗ DUY NHẤT biết implementation cụ thể nào đang chạy. Đổi provider / Redis / Postgres
ở đây — app/agents/, app/orchestration/ không sửa 1 dòng.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from app.agents.planning.tools import build_registry as build_planning_registry
from app.core.config import settings
from app.orchestration.graph import build_graph
from app.providers.base import LLMProvider
from app.services.base import SessionMemory
from app.services.session import RedisSession
from app.services.store import FactStore
from app.services.tasks import TaskRepo
from app.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

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


async def setup_mcp() -> list[MCPClient]:
    """Connect tất cả server khai báo trong `mcp.json`. Gọi 1 lần lúc app khởi động
    (xem lifespan trong main.py). Trả list client ĐÃ CONNECT để đăng ký tool + đóng lúc
    shutdown.

    KHÔNG tự đăng ký vào registry nào — `main.py::_lifespan` đăng ký vào
    `Runtime.external_registry` sau khi connect xong (xem `build_runtime`)."""
    from app.mcp_client.manager import connect_all
    from app.mcp_client.registry import load_mcp_servers

    return await connect_all(load_mcp_servers(settings.mcp_config_path))


@dataclass
class Runtime:
    provider: LLMProvider
    graph: CompiledStateGraph
    external_registry: ToolRegistry  # expose để main.py::_lifespan đăng ký MCP client vào
    session: SessionMemory
    store: FactStore
    tasks: TaskRepo


@lru_cache(maxsize=1)
def build_runtime() -> Runtime:
    """Dựng 1 lần, dùng lại mọi request (FastAPI Depends) — giữ connection pool.

    `external_registry` cố tình RỖNG lúc trả về: connect MCP cần `await`, không gọi được
    trong hàm sync này — `main.py::_lifespan` điền tool MCP vào SAU, đăng ký thẳng vào
    ĐÚNG object này (không tạo registry mới). An toàn dù graph đã compile trước đó:
    `ToolRegistry` mutable, và `app/agents/_runtime.py::run_loop()` đọc `registry.defs()`
    LIVE mỗi lượt gọi (không cache lúc compile) — tool thêm sau vẫn được LLM thấy ở lượt kế
    tiếp. Đã đọc lại source để xác nhận, không giả định (xem
    plans/260913-1646-langgraph-orchestrator-worker/phase-04-entrypoint-migration.md
    Risk Assessment)."""
    tasks = TaskRepo(settings.postgres_dsn)
    store = FactStore(settings.postgres_dsn, top_k=settings.fact_top_k)
    provider = build_provider()
    external_registry = ToolRegistry()
    graph = build_graph(provider, build_planning_registry(tasks, store), external_registry)
    return Runtime(
        provider=provider,
        graph=graph,
        external_registry=external_registry,
        session=RedisSession(
            settings.redis_url,
            window=settings.session_window,
            ttl_seconds=settings.session_ttl_hours * 3600,
        ),
        store=store,
        tasks=tasks,
    )
