"""Helper thuần dùng chung — chỉ phụ thuộc `domain/`."""

from __future__ import annotations

from typing import Any

from app.domain.message import Usage


def clean_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Bỏ key có value null. Model (gpt-oss…) hay emit `"param": null` cho optional
    param — `null` ≡ bỏ trống. Provider gọi khi parse tool-call từ response."""
    return {k: v for k, v in args.items() if v is not None}


# ---------- giá token ----------
# model -> (USD / 1M input, USD / 1M output). Cập nhật TAY — không có API giá chuẩn.
# Model không có trong bảng → cost() trả None (khác 0: nghĩa là "chưa set giá").
# Anthropic: đây là giá cơ bản, cache-tier (cache_read −90% / cache_write +25%)
# tính riêng ở anthropic._cost() khi implement.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.15, 0.75),      # Groq
    "openai/gpt-oss-20b": (0.10, 0.50),
    "qwen/qwen3.8-27b": (0.29, 0.59),         # ước lượng theo Qwen3-32B — verify
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "gpt-4o": (2.50, 10.00),                  # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "claude-sonnet-4-5": (3.00, 15.00),       # Anthropic
    "claude-haiku-4-5": (1.00, 5.00),
    "llama3.2": (0.0, 0.0),                   # Ollama local
    "qwen2.5": (0.0, 0.0),
}  # cập nhật: 2026-09-10


def cost(usage: Usage | None, model: str) -> float | None:
    """USD cho `usage` với `model`. None nếu chưa đo được token hoặc model chưa có giá."""
    if usage is None:
        return None
    rate = PRICES.get(model)
    if rate is None:
        return None
    in_rate, out_rate = rate
    return round(
        usage.prompt_tokens / 1_000_000 * in_rate
        + usage.completion_tokens / 1_000_000 * out_rate,
        6,
    )
