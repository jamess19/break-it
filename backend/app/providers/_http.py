"""POST JSON + retry 429/5xx + lỗi mạng — dùng chung cho openai.py và ollama.py.

Roadmap 3c-3 (resilience) kéo lên sớm: Groq free tier hay 429 + timeout, eval
chạy nhiều call liên tục sẽ vỡ nếu không retry.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.providers.base import ProviderHTTPError

log = logging.getLogger("provider.http")

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_BACKOFF = 30.0
# connect ngắn (server sống hay chết biết ngay); read dài (LLM sinh chậm)
_CONNECT_TIMEOUT = 10.0

__all__ = ["ProviderHTTPError", "post_json"]


async def post_json(
    url: str,
    *,
    json: dict,
    headers: dict,
    timeout: float,
    retries: int = 4,
) -> dict:
    """POST → `.json()`. Retry 429/5xx (tôn trọng `Retry-After`) và lỗi mạng
    (`ConnectTimeout`/`ReadTimeout`/`ConnectError`…) với exponential backoff
    (2/4/8… giây, trần 30s). Hết lượt / lỗi khác → `ProviderHTTPError`."""
    to = httpx.Timeout(timeout, connect=_CONNECT_TIMEOUT)
    last_net: Exception | None = None

    for attempt in range(1, retries + 2):
        try:
            async with httpx.AsyncClient(timeout=to) as client:
                resp = await client.post(url, json=json, headers=headers)
        except httpx.TransportError as e:  # ConnectTimeout, ReadTimeout, ConnectError…
            last_net = e
            if attempt > retries:
                raise ProviderHTTPError(0, url, f"{type(e).__name__}: {e}") from e
            wait = min(2.0**attempt, _MAX_BACKOFF)
            log.warning(
                "mạng %s từ %s — thử lại sau %.1fs (lần %d/%d)",
                type(e).__name__, url, wait, attempt, retries,
            )
            await asyncio.sleep(wait)
            continue

        if resp.status_code not in _RETRY_STATUS or attempt > retries:
            if resp.is_error:
                raise ProviderHTTPError(resp.status_code, url, resp.text)
            return resp.json()

        wait = _retry_after(resp) or min(2.0**attempt, _MAX_BACKOFF)
        log.warning(
            "HTTP %d từ %s — thử lại sau %.1fs (lần %d/%d)",
            resp.status_code, url, wait, attempt, retries,
        )
        await asyncio.sleep(wait)

    raise ProviderHTTPError(0, url, f"hết retry sau lỗi mạng: {last_net}")


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("retry-after")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None
