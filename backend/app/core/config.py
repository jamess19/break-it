"""Đọc .env — provider, model, DB url. KHÔNG hardcode key vào code."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    debug: bool = False  # True → lộ traceback ra response (chỉ dev)

    # provider: ollama (local) | anthropic | openai (dùng cho cả Groq/Gemini-compat)
    provider: str = "openai"
    model: str = "openai/gpt-oss-120b"

    ollama_base_url: str = "http://localhost:11434/v1"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    # đổi sang Groq/Gemini/DeepSeek/HF: chỉ cần đổi base_url + key + model
    openai_base_url: str = "https://api.groq.com/openai/v1"

    # memory
    session_window: int = 20  # Phần 4 — giữ N message gần nhất / phiên
    session_ttl_hours: int = 168  # 7 ngày
    fact_top_k: int = 20  # Phần 5 — số fact recall nạp ra (không vector, lấy gần đây nhất)
    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql+asyncpg://ops:ops@localhost:5433/ops_agent"

    mcp_config_path: str = "mcp.json"  # Phần 6 — danh sách MCP server (stdio); không có file = bỏ qua


settings = Settings()
