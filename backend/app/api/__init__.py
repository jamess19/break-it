"""Gom mọi router của app thành 1 `api_router` để `main.py` include 1 lần."""

from fastapi import APIRouter

from app.api import chat, plans, tasks

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(tasks.router)
api_router.include_router(plans.router)
