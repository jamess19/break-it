# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
docker compose up -d                          # Postgres (localhost:5433) + Redis (6379)
cp .env.example .env                          # fill OPENAI_API_KEY (Groq key works)

pytest                                        # all tests — pure logic + fakes, no DB/network needed
pytest tests/test_engine_loop.py -v
pytest tests/test_engine_loop.py::test_loop_runs_two_tool_calls_then_stops
ruff check .                                  # only linter configured; no pyproject.toml/ruff.toml (defaults)

uvicorn app.main:app --reload                 # API + frontend at localhost:8000 (and /docs)
python -m eval --model gpt-oss-120b --gap 12  # benchmark harness (see Eval section)
python -m scripts.try_call "prompt here"      # single provider.chat() smoke test, no tools/loop
bash tests/check_api_key.sh openai            # verify a provider key/endpoint works
```

No Alembic yet — schema lives in `db/init.sql` (runs once via docker-compose `initdb.d`) plus
`app/memory/tables.py` (SQLAlchemy models, must be kept in sync by hand). Schema changes to an
existing DB are applied as manual `ALTER TABLE` (see migration snippets in `docs/roadmap.md`).
Switching to Alembic is a known, deliberately-deferred TODO — don't assume it exists.

## Architecture

Ports-and-adapters / hexagonal, not layered MVC. Dependencies point **inward** toward `domain/`:

```
domain/   →  Pydantic entities only (Message, ToolCall, Task, AgentResult...). No imports from
             any other app/ package. Every other layer imports from here.
engine/   →  run_loop() / run() — the tool-calling loop. Depends ONLY on the Protocols in
             providers/base.py, tools/registry.py, memory/base.py — never on a concrete
             openai.py, session.py, etc. This is what makes it testable with fakes (see
             tests/test_engine_loop.py) and provider-swappable.
providers/, tools/, memory/  →  adapters implementing those Protocols (LLM APIs, tool
             execution, Redis/Postgres). Interchangeable behind the interface.
api/, automations/  →  entrypoints (HTTP, cron, webhook). All three call the *same*
             app/engine/run.py::run() — there is no separate code path per trigger. If you're
             adding a new trigger, it should be a thin wrapper that ends in a call to run().
app/api/deps.py  →  the ONLY place that knows which concrete provider/DB/session impl is
             wired up (build_provider, build_registry, build_runtime). Swapping Groq→Anthropic
             or Redis→something else is a change confined to this file.
```

Three "model" kinds that must never merge into one class, even when their fields overlap:
domain entity (`domain/`) vs HTTP request/response schema (`api/schemas.py`, `api/*.py`) vs
DB row (`memory/tables.py`, SQLAlchemy). Each changes for a different reason.

Tools (native + MCP) are indistinguishable to `engine/` and to the LLM: both are just entries
`registry.defs()` sends as `tools=[...]` in the chat request, and both come back as
`tool_calls` the loop executes via `registry.run()`. Adding a capability to *this* agent = a
new class in `app/tools/` implementing the `Tool` protocol (`app/tools/base.py`) + one
`registry.register(...)` call — do not reach for MCP for that; MCP is for reusing a tool
someone else already wrote as an MCP server (see `docs/mcp.md`).

### MCP (`app/tools/mcp/`)

- `MCPClient.connect()` uses `AsyncExitStack`, not `async with`, because the connection is
  opened once at app startup (`app/main.py` lifespan) and used across many later, unrelated
  HTTP requests — no single lexical block spans both. `close()` unwinds the stack at shutdown.
- MCP servers (e.g. Lark's `im.v1.message.create`) can have dotted tool names; OpenAI/Groq
  function names must match `^[a-zA-Z0-9_-]+$`. `client.py::_safe_name()` sanitizes on the way
  out and `MCPClient._real_name` maps back to the real name when calling the server — both
  directions are needed, they solve different problems (LLM wire vs MCP wire).
- One server failing to connect (missing binary, bad credentials) must not crash the app —
  `app/api/deps.py::setup_mcp()` catches per-server and logs; MCP is always optional. Servers
  are declared in `mcp.json` (gitignored; `mcp.json.example` is the committed template).

### Usage/cost tracking

Each provider computes its own `Message.cost_usd` (in `_dict_to_message`/`chat()`), reading
rates from `app/util.py::PRICES`/`cost()`. This is deliberate, not just "didn't refactor yet":
each provider's `usage` response shape differs (Anthropic will need cache-tier pricing later),
so the provider — which already translates its wire format into domain types — is the right
place to also translate usage into cost. `engine/loop.py` only accumulates what providers hand
it; it does not know about pricing. `cost_usd`/`usage` being `None` means "not measured /
model not in PRICES" — never treat `None` as `0`.

### Resilience (`app/providers/_http.py`)

`post_json()` retries both HTTP 429/5xx *and* network-transport errors
(`httpx.TransportError` — connect/read timeouts, connection resets), with a shorter connect
timeout than read timeout. `ProviderHTTPError` (defined in `providers/base.py`, not `_http.py`
— it's part of the provider port's contract) carries the response body so callers can inspect
*why* a call failed (e.g. Lark/Groq tool-schema validation errors show up here).

### Long-term memory (`facts` table)

Deliberately flat, no embeddings/pgvector — `recall`/`remember` filter by `meta.category` or
load-all. This was an explicit decision (not an oversight): personal-scale facts need
completeness, not similarity search, so RAG was rejected. Don't reintroduce vector search here
without revisiting that reasoning (see `docs/database.md`, `docs/mcp.md`).

### Eval harness (`eval/`)

`python -m eval` seeds fake tasks into **whatever `TEST_POSTGRES_DSN` (fallback
`POSTGRES_DSN`) points at**, runs the real `engine.run()`, then `TRUNCATE`s between cases —
this is destructive to real data if pointed at a non-test database. Assertions in
`eval/cases/*.yaml` are split `hard` (must pass) vs `soft: true` (reported, doesn't fail the
case) — e.g. daily-hour-cap violations are soft because task estimates are human-entered and
can legitimately exceed capacity. `eval/models.yaml` pins the Groq model IDs that are actually
available/working (verified against `GET /v1/models`); don't assume a model name from Groq's
marketing docs works without checking that file or the live model list first.

## Docs

`docs/` is gitignored (local reference notes, not shipped) but actively maintained — read
`docs/roadmap.md` first for current project state/priorities and past decisions with their
reasoning (many "why" answers live there, not just in code comments). `docs/architecture.md`,
`docs/database.md`, `docs/mcp.md` go deeper on the sections above.
