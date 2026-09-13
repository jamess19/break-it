"""Đọc `mcp.json` — danh sách MCP server (stdio) để agent connect lúc app khởi động.

Format:
    {"time": {"command": "uvx", "args": ["mcp-server-time"]},
     "lark": {"command": "npx", "args": ["-y", "@larksuiteoapi/lark-mcp", "mcp"],
              "env": {"APP_ID": "...", "APP_SECRET": "..."}}}

Không có file → trả `{}`, agent chạy bình thường không có tool MCP (optional).
"""

from __future__ import annotations

import json
from pathlib import Path


def load_mcp_servers(path: str) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())
