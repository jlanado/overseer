import psycopg2
import psycopg2.extras
from contextlib import contextmanager

from config import settings


@contextmanager
def get_conn():
    conn = psycopg2.connect(settings.postgres_dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_run(run_id: str, repo_url: str, branch: str, pr_number: int | None, commit_sha: str | None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (run_id, repo_url, branch, pr_number, commit_sha, status)
                VALUES (%s, %s, %s, %s, %s, 'running')
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, repo_url, branch, pr_number, commit_sha),
            )


def update_run(run_id: str, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [run_id]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE runs SET {set_clause}, updated_at = now() WHERE run_id = %s",
                values,
            )


def get_run(run_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,))
            return cur.fetchone()


def list_runs_by_status(status: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM runs WHERE status = %s ORDER BY created_at DESC", (status,)
            )
            return cur.fetchall()
