# Personal Ops Agent

Agent dùng thật hằng ngày, kiến trúc theo hướng platform. Chi tiết đầy đủ:
[`agent-platform-backend-guide.md`](./agent-platform-backend-guide.md).

## Tài liệu (`docs/`)

| File | Nội dung |
| --- | --- |
| [`architecture.md`](./docs/architecture.md) | Vì sao chia thư mục thế này, flow 1 request, khác gì 3-layer/MVC/Clean |
| [`roadmap.md`](./docs/roadmap.md) | Kế hoạch đưa dự án lên mức portfolio: eval, MCP, observability, deploy |
| [`local-llm.md`](./docs/local-llm.md) | Local vs cloud LLM, chỉnh context/memory cho model nhỏ |
| [`llm-providers.md`](./docs/llm-providers.md) | Field request/response từng provider (OpenAI-compat, Anthropic, Gemini) |
| [`request-flow.md`](./docs/request-flow.md) | 1 request `POST /chat` đi xuyên các tầng |
| [`system-boundaries.md`](./docs/system-boundaries.md) | Client — Our System — LLM Provider: ai giữ gì |
| [`database.md`](./docs/database.md) | Redis + Postgres schema (facts phẳng, không vector) |
| [`erd.md`](./docs/erd.md) | ERD Postgres — định nghĩa từng cột, enum, quan hệ, CASCADE |
| [`tool-calling.md`](./docs/tool-calling.md) | Phần 2 |
| [`agent-loop.md`](./docs/agent-loop.md) | Phần 3 |
| [`short-term-memory.md`](./docs/short-term-memory.md) | Phần 4 |
| [`task-agent.md`](./docs/task-agent.md) | Task Agent — to-do + chatbot + cron xếp lịch tuần |

> ⚠️ Đây là **structure đích** (Phần 1 của guide), đã dựng sẵn khung + interface.
> Guide khuyên người mới tiến hoá dần từ 1 file — khung này hợp khi bạn *đã* hiểu
> các ranh giới và muốn điền vào chỗ trống. Mỗi file stub `raise NotImplementedError`
> kèm số **Phần** tương ứng trong guide để làm theo thứ tự.

## Quy tắc phụ thuộc (đọc một chiều)

```
domain/  ←  không phụ thuộc ai. Mọi tầng import từ đây.
engine/  →  chỉ phụ thuộc interface: providers/base, tools/registry, memory/base
api/, automations/  →  chỉ chạm engine.run(), không đụng nội tạng loop
```

Ba loại "model" không được trộn:

| Loại         | Sống ở             | Ví dụ                                    |
| ------------- | -------------------- | ------------------------------------------ |
| Domain entity | `domain/`          | `Message`, `ToolCall`, `AgentResult` |
| HTTP schema   | `api/schemas.py`   | `ChatRequest`, `ChatResponse`          |
| DB model      | `memory/tables.py` | `MessageRow` (SQLAlchemy)                |

## Thứ tự thi công (Phần 5 của guide)

| # | Phần              | File chính                            | ✅ Checkpoint                                   | Xong |
| - | ------------------ | -------------------------------------- | ----------------------------------------------- | ---- |
| 1 | Gọi model         | `providers/openai.py`, `ollama.py`  | gọi được model, in câu trả lời           | ✅ |
| 2 | Tool-calling       | `tools/registry.py`, `tools/base.py`  | model xin gọi tool → mình chạy → trả lại | ✅ (cơ chế) |
| 3 | Agent loop         | `engine/loop.py`, `run.py`          | agent tự làm task cần ≥2 tool-call          | ✅ |
| 4 | Memory ngắn hạn  | `memory/session.py` (Redis)          | nhớ context qua nhiều lượt                  | ✅ |
| 5 | Memory dài hạn   | `memory/store.py`, `tools/memory.py` | agent gọi `recall`/`remember` fact (bảng phẳng, lọc category) | ✅ (qua tool) |
| 6 | Tools ngoài & MCP | `tools/mcp/client.py`                | agent discover + gọi tool qua MCP              | — |
| 7 | Automations        | `automations/scheduler.py`           | cron `daily` chạy agent, ghi `automation_runs` | ✅ |

**Task Agent** (mở rộng — [`docs/task-agent.md`](./docs/task-agent.md)): to-do list cấp cao +
chatbot xếp lịch tuần + cron sáng roll-over việc chưa xong. 11 tool, REST CRUD ở `api/tasks.py`.

**UI preview**: `frontend/index.html` (vanilla JS, không build, gọi thẳng REST) — FastAPI serve ở
`http://localhost:8000/` (và `/app/`) khi chạy `uvicorn app.main:app --reload`. 3 tab: Việc /
Kế hoạch tuần / Chat. (`personal-ops-agent.html` ở root là mockup tĩnh cũ, giữ để tham khảo design.)

## Chạy

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # điền OPENAI_API_KEY (Groq)

docker compose up -d          # Postgres + Redis
docker compose ps             # đợi db "healthy"

pytest                        # test loop (fake provider)
bash tests/check_api_key.sh openai

uvicorn app.main:app --reload
curl -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"session_id":"s1","message":"Chào, tên tôi là Thông"}'
curl -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"session_id":"s1","message":"Tôi tên gì?"}'   # nhớ được = Redis OK
```

- Provider chat: `.env` → `PROVIDER` + `OPENAI_BASE_URL` (Groq/OpenAI/…) hoặc `PROVIDER=ollama`.
- Storage: `docker-compose.yml` + `db/init.sql`. Chi tiết `docs/database.md`.
- Debug: `docs/*` + `GET /debug/config`, `/debug/tools`, `tests/agent.http`, Postman collection.
