"""Khởi động app, ráp mọi thứ lại. `uvicorn app.main:app --reload`."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.debug import router as debug_router
from app.api.routes import router
from app.api.tasks import router as tasks_router

log = logging.getLogger("agent")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-7s %(name)s | %(message)s",
    )
    app = FastAPI(title="Personal Ops Agent")
    app.include_router(router)
    app.include_router(tasks_router)  # REST CRUD to-do list cho UI
    app.include_router(debug_router)  # /debug/* — gỡ lỗi, tắt khi lên production

    # UI preview — folder frontend/ (1 file HTML, gọi thẳng REST ở trên, cùng origin → khỏi CORS).
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    async def _ui() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.exception_handler(Exception)
    async def _show_errors(request: Request, exc: Exception) -> JSONResponse:
        """DEV: trả lỗi + traceback ra response cho dễ debug từ Postman.
        Production thì bỏ handler này (đừng lộ nội tạng)."""
        if isinstance(exc, HTTPException):
            raise exc
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        body: dict = {
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
