-- Chạy 1 lần khi container Postgres khởi tạo (docker-compose mount vào initdb.d).
-- Khớp với app/memory/tables.py. Khi schema tiến hoá nhiều → chuyển sang Alembic.

-- Bộ nhớ dài hạn (Phần 5) — fact phẳng, KHÔNG vector ------------------------
-- Fact cá nhân ít + cần đầy đủ → lọc theo meta.category / load-all, không RAG.
CREATE TABLE IF NOT EXISTS facts (
    id            bigserial PRIMARY KEY,
    text          text        NOT NULL,
    source        text        NOT NULL DEFAULT '',
    meta          jsonb       NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_used_at  timestamptz,
    use_count     integer     NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS facts_category
    ON facts ((meta->>'category'));

-- Archive hội thoại (Redis chỉ giữ N gần nhất) ----------------------------
CREATE TABLE IF NOT EXISTS messages (
    id          bigserial PRIMARY KEY,
    session_id  text        NOT NULL,
    role        text        NOT NULL,
    content     text        NOT NULL DEFAULT '',
    tool_calls  jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_session ON messages (session_id, created_at);

-- Log cron/webhook (Phần 7) ---------------------------------------------
CREATE TABLE IF NOT EXISTS automation_runs (
    id           bigserial PRIMARY KEY,
    name         text        NOT NULL,
    trigger      text        NOT NULL,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    status       text        NOT NULL DEFAULT 'running',
    steps        integer     NOT NULL DEFAULT 0,
    tool_calls   integer     NOT NULL DEFAULT 0,
    tokens       integer     NOT NULL DEFAULT 0,   -- tổng = prompt + completion
    prompt_tokens     integer NOT NULL DEFAULT 0,
    completion_tokens integer NOT NULL DEFAULT 0,
    cost_usd     numeric(12,6),                    -- NULL = model chưa có trong app/pricing.py
    output       text        NOT NULL DEFAULT '',
    error        text
);

-- Token + cursor mỗi connector (Phần 6) --------------------------------
CREATE TABLE IF NOT EXISTS connector_state (
    name          text PRIMARY KEY,
    kind          text        NOT NULL,
    status        text        NOT NULL DEFAULT 'disconnected',
    credentials   jsonb       NOT NULL DEFAULT '{}',
    last_sync_at  timestamptz,
    cursor        text
);

-- ===================== Task Agent (docs/task-agent.md) =====================

CREATE TABLE IF NOT EXISTS tasks (
    id              bigserial PRIMARY KEY,
    title           text        NOT NULL,
    notes           text        NOT NULL DEFAULT '',
    status          text        NOT NULL DEFAULT 'todo',
    priority        integer     NOT NULL DEFAULT 2,
    estimate_hours  numeric(4,1),
    deadline        date,
    project         text,
    source          text        NOT NULL DEFAULT 'chat',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    done_at         timestamptz
);
CREATE INDEX IF NOT EXISTS tasks_status   ON tasks (status);
CREATE INDEX IF NOT EXISTS tasks_deadline ON tasks (deadline);
CREATE INDEX IF NOT EXISTS tasks_project  ON tasks (project);

CREATE TABLE IF NOT EXISTS checklist_items (
    id          bigserial PRIMARY KEY,
    task_id     bigint      NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    text        text        NOT NULL,
    done        boolean     NOT NULL DEFAULT false,
    position    integer     NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS checklist_task ON checklist_items (task_id, position);

CREATE TABLE IF NOT EXISTS plans (
    id          bigserial PRIMARY KEY,
    week_start  date        NOT NULL,
    is_active   boolean     NOT NULL DEFAULT true,
    created_by  text        NOT NULL DEFAULT 'chat',
    note        text        NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS plans_week ON plans (week_start, is_active);

CREATE TABLE IF NOT EXISTS plan_slots (
    id             bigserial PRIMARY KEY,
    plan_id        bigint       NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    task_id        bigint       NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    day            date         NOT NULL,
    start_minute   integer,
    planned_hours  numeric(4,1) NOT NULL,
    position       integer      NOT NULL DEFAULT 0,
    done           boolean      NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS plan_slots_plan ON plan_slots (plan_id);
CREATE INDEX IF NOT EXISTS plan_slots_day  ON plan_slots (day);
CREATE INDEX IF NOT EXISTS plan_slots_task ON plan_slots (task_id);
