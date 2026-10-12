-- The single local brain. One file at ~/.assistant/state.db (APP_DB_PATH).
-- Mirrors ../../../_shared/memory-schema.md. Plain tables, readable by any
-- SQLite viewer. Safe to run repeatedly (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT,
    started_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id  INTEGER NOT NULL,
    role             TEXT NOT NULL,          -- user | assistant
    content          TEXT NOT NULL,
    trace            TEXT,                   -- JSON: phases + tool calls (evals/debug)
    created_at       TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
);

CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'fact',    -- preference | fact | profile ...
    source      TEXT NOT NULL DEFAULT 'auto',    -- auto (consolidation) | explicit
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id     INTEGER,
    tool        TEXT NOT NULL,
    args        TEXT,                   -- JSON
    result      TEXT,                   -- text/JSON (truncated)
    ok          INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (     -- local calendar
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    start       TEXT NOT NULL,          -- ISO-8601
    "end"       TEXT,
    notes       TEXT,
    google_id   TEXT,                   -- set when synced to Google Calendar
    outlook_id  TEXT,                   -- set when synced to Microsoft Outlook
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_conv ON turns (conversation_id);
CREATE INDEX IF NOT EXISTS idx_facts_created ON facts (created_at);
CREATE INDEX IF NOT EXISTS idx_events_start ON events (start);
CREATE INDEX IF NOT EXISTS idx_events_google ON events (google_id);
