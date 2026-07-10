-- Overseer core schema: one row per pipeline run, status drives the
-- LangGraph approval_gate node (poll-based, see nodes/approval.py).

CREATE TABLE IF NOT EXISTS runs (
    run_id           TEXT PRIMARY KEY,
    repo_url         TEXT NOT NULL,
    branch           TEXT NOT NULL,
    pr_number        INTEGER,
    commit_sha       TEXT,
    status           TEXT NOT NULL DEFAULT 'running',
        -- running | awaiting_approval | approved | rejected | deployed | failed
    fix_attempts     INTEGER NOT NULL DEFAULT 0,
    review_notes     TEXT,
    test_output      TEXT,
    security_output  TEXT,
    error            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status);
