"""
Approval gate: writes the run to 'awaiting_approval' and polls Postgres for
a human decision made via the Streamlit UI. This is a blocking poll loop —
simple to reason about, but it ties up the graph execution thread for the
duration of the wait and does not survive an orchestrator restart mid-wait.

For a production version, replace this with LangGraph's native
`interrupt()` + a Postgres-backed checkpointer, which persists the paused
state and resumes cleanly across restarts instead of blocking a thread.
"""
import time

from langfuse import observe

from state import PipelineState
from config import settings
from db import update_run, get_run


@observe(name="approval")
def approval_node(state: PipelineState) -> dict:
    update_run(state["run_id"], status="awaiting_approval")

    deadline = time.time() + settings.approval_timeout_seconds
    poll_interval = 5

    while time.time() < deadline:
        run = get_run(state["run_id"])
        if run["status"] == "approved":
            return {"approved": True}
        if run["status"] == "rejected":
            return {"approved": False}
        time.sleep(poll_interval)

    # Timed out waiting — treat as rejected rather than hanging forever.
    update_run(state["run_id"], status="rejected", error="Approval timed out")
    return {"approved": False, "error": "Approval timed out"}
