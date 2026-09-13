"""Khởi động app, ráp mọi thứ lại. `uvicorn app.main:app --reload`."""

from __future__ import annotations

import logging
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.api.deps import build_runtime, setup_mcp
from app.core.config import settings

log = logging.getLogger("agent")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Connect MCP server 1 lần lúc startup (cần `await`, không gọi được trong
    `build_runtime()` sync) — tool MCP đăng ký vào registry đã cache sẵn, mọi
    request sau (Depends(build_runtime)) thấy đủ tool. Đóng lại lúc shutdown.

    `setup_mcp()` giờ chỉ CONNECT (xem docs/langgraph-plan.md — Phase 2 của plan LangGraph),
    không tự đăng ký vào registry nào — đăng ký vào `rt.registry` (đường single-agent cũ) tạm
    làm Ở ĐÂY cho tới khi Phase 4 thay bằng `agents/comms/tools.py::build_registry()`."""
    rt = build_runtime()
    mcp_clients = await setup_mcp()
    for client in mcp_clients:
        await client.register_into(rt.registry)
    log.info("startup: %d tool đăng ký (%d server MCP)", len(rt.registry.defs()), len(mcp_clients))
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

    # UI preview — folder frontend/ (1 file HTML, gọi thẳng REST ở trên, cùng origin → khỏi CORS).
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    async def _ui() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

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
