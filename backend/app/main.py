"""Khởi động app, ráp mọi thứ lại. `uvicorn app.main:app --reload`.

Backend THUẦN API — không serve frontend nữa (xem `frontend/`, dự án Vite+React riêng,
`npm run dev` cổng 5173, proxy sang backend lúc dev — xem `frontend/vite.config.ts`)."""

from __future__ import annotations

import logging
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import api_router
from app.api.deps import build_runtime, setup_mcp
from app.core.config import settings

log = logging.getLogger("agent")


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Connect MCP server 1 lần lúc startup (cần `await`, không gọi được trong
    `build_runtime()` sync) — tool MCP đăng ký vào `rt.external_registry` (registry rỗng
    `build_runtime()` đã tạo sẵn và đóng vào graph lúc compile). Đăng ký SAU compile vẫn thấy
    được vì registry mutable, `run_loop()` đọc `registry.defs()` live mỗi lượt gọi — xem
    `deps.py::build_runtime`. Đóng lại lúc shutdown."""
    rt = build_runtime()
    mcp_clients = await setup_mcp()
    for client in mcp_clients:
        await client.register_into(rt.external_registry)
    log.info(
        "startup: %d tool external đăng ký (%d server MCP)",
        len(rt.external_registry.defs()),
        len(mcp_clients),
    )
    yield
    for client in mcp_clients:
        await client.close()


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-7s %(name)s | %(message)s",
    )
    app = FastAPI(title="Personal Ops Agent", lifespan=_lifespan)
    app.include_router(api_router)

    @app.get("/health", tags=["meta"])
    async def _health() -> dict:
        """Liveness — process còn sống + config đang nạp. (Chưa ping DB/Redis.)"""
        return {"ok": True, "provider": settings.provider, "model": settings.model}

    @app.exception_handler(Exception)
    async def _on_error(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            raise exc
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        if not settings.debug:
            return JSONResponse(status_code=500, content={"error": "internal_error"})
        body: dict = {  # dev: traceback ra response cho dễ debug
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc().splitlines()[-14:],
        }
        req = getattr(exc, "request", None)  # httpx errors mang theo request
        if req is not None:
            body["failed_url"] = str(req.url)
        return JSONResponse(status_code=500, content=body)

    return app


app = create_app()
