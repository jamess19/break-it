"""wiring: chọn provider, dựng registry, mở kết nối memory.

Chỗ DUY NHẤT biết implementation cụ thể nào đang chạy. Đổi provider / Redis / Postgres
ở đây — engine/loop.py không sửa 1 dòng.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.config import settings
from app.memory.base import SessionMemory
from app.memory.session import RedisSession
from app.memory.store import FactStore
from app.memory.tasks import TaskRepo
from app.providers.base import LLMProvider
from app.tools.registry import ToolRegistry


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
    # connector thật (Gmail, Calendar, Slack) + MCP → đăng ký ở Phần 6
    return registry


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
