import os
import time

import psycopg2
import psycopg2.extras
import streamlit as st

# This file duplicates the query logic in orchestrator/db.py rather than
# importing it (separate containers/images — see CLAUDE.md). If you change
# the `runs` table schema (scripts/init_db.sql), update both this file and
# orchestrator/db.py in lockstep.

POSTGRES_DSN = (
    f"host={os.environ.get('POSTGRES_HOST', 'postgres')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', 'overseer')} "
    f"user={os.environ.get('POSTGRES_USER', 'overseer')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', '')}"
)


def get_runs(status: str):
    conn = psycopg2.connect(POSTGRES_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM runs WHERE status = %s ORDER BY created_at DESC", (status,)
            )
            return cur.fetchall()
    finally:
        conn.close()


def set_status(run_id: str, status: str):
    conn = psycopg2.connect(POSTGRES_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE runs SET status = %s, updated_at = now() WHERE run_id = %s",
                (status, run_id),
            )
        conn.commit()
    finally:
        conn.close()


st.set_page_config(page_title="Overseer — Approvals", layout="wide")
st.title("🛡️ Overseer — Pending Deployments")

pending = get_runs("awaiting_approval")

if not pending:
    st.info("No runs currently awaiting approval.")
else:
    for run in pending:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(f"Run `{run['run_id']}` — {run['repo_url']}")
                st.caption(f"Branch: {run['branch']} · PR #{run['pr_number'] or '—'} · Commit: {run['commit_sha'] or '—'}")

                with st.expander("Review notes"):
                    st.text(run["review_notes"] or "—")
                with st.expander("Test output"):
                    st.text(run["test_output"] or "—")
                with st.expander("Security scan"):
                    st.text(run["security_output"] or "—")
                st.caption(f"Fix attempts used: {run['fix_attempts']}")

            with col2:
                if st.button("✅ Approve", key=f"approve_{run['run_id']}", use_container_width=True):
                    set_status(run["run_id"], "approved")
                    st.rerun()
                if st.button("❌ Reject", key=f"reject_{run['run_id']}", use_container_width=True):
                    set_status(run["run_id"], "rejected")
                    st.rerun()

st.divider()
st.subheader("Recent history")
for status in ["deployed", "rejected", "failed"]:
    runs = get_runs(status)
    if runs:
        st.caption(status.upper())
        st.dataframe(
            [{"run_id": r["run_id"], "repo": r["repo_url"], "branch": r["branch"], "updated": r["updated_at"]} for r in runs],
            use_container_width=True,
            hide_index=True,
        )

time.sleep(5)
st.rerun()
