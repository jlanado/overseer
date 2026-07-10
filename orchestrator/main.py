"""
FastAPI app: receives Gitea webhooks (push / pull_request), clones the repo
into a scoped per-run workspace, and kicks off the LangGraph pipeline as a
background task.
"""
import hashlib
import hmac
import shutil
import uuid
from pathlib import Path

import git
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from langfuse import propagate_attributes

from config import settings
from db import create_run, update_run
from graph import overseer_graph
from state import PipelineState

app = FastAPI(title="Overseer Orchestrator")


def _verify_signature(body: bytes, signature: str | None) -> bool:
    if not settings.webhook_secret:
        return True  # no secret configured — allow (dev convenience only)
    if not signature:
        return False
    expected = hmac.new(
        settings.webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _branch_from_ref(ref: str) -> str:
    """Strip the leading refs/heads/ or refs/tags/ segment, preserving any
    slashes in the branch/tag name itself (e.g. refs/heads/feature/foo ->
    feature/foo, not foo)."""
    for prefix in ("refs/heads/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def _clone_repo(repo_url: str, branch: str, run_id: str) -> str:
    dest = Path(settings.workspace_dir) / run_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    git.Repo.clone_from(repo_url, dest, branch=branch, depth=1)
    return str(dest)


def _run_pipeline(run_id: str, repo_url: str, branch: str, pr_number: int | None, commit_sha: str | None):
    try:
        repo_path = _clone_repo(repo_url, branch, run_id)
    except Exception as e:
        update_run(run_id, status="failed", error=f"Clone failed: {e}")
        return

    initial_state: PipelineState = {
        "run_id": run_id,
        "repo_url": repo_url,
        "repo_path": repo_path,
        "branch": branch,
        "pr_number": pr_number,
        "commit_sha": commit_sha,
        "diff": _get_diff(repo_path),
        "review_notes": "",
        "needs_fix": False,
        "fix_attempts": 0,
        "max_fix_attempts": settings.max_fix_attempts,
        "tests_passed": False,
        "test_output": "",
        "security_passed": False,
        "security_output": "",
        "approved": None,
        "deployed": False,
        "error": None,
    }

    config = {"configurable": {"thread_id": run_id}}
    try:
        # Groups every node's @observe() trace (see nodes/*.py) under one
        # Langfuse session per pipeline run, so a run's full review->deploy
        # path shows up together instead of as disconnected traces.
        with propagate_attributes(session_id=run_id, trace_name="overseer-pipeline"):
            final_state = overseer_graph.invoke(initial_state, config=config)
        status = "deployed" if final_state.get("deployed") else (
            "rejected" if final_state.get("approved") is False else "failed"
        )
        update_run(
            run_id,
            status=status,
            fix_attempts=final_state.get("fix_attempts", 0),
            review_notes=final_state.get("review_notes", ""),
            test_output=final_state.get("test_output", ""),
            security_output=final_state.get("security_output", ""),
            error=final_state.get("error"),
        )
    except Exception as e:
        update_run(run_id, status="failed", error=f"Pipeline crashed: {e}")


def _get_diff(repo_path: str) -> str:
    """Diff of the last commit against its parent. Falls back to full HEAD
    show for the initial commit on a branch."""
    repo = git.Repo(repo_path)
    try:
        return repo.git.diff("HEAD~1", "HEAD")
    except git.GitCommandError:
        return repo.git.show("HEAD")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitea_signature: str | None = Header(default=None),
):
    body = await request.body()
    if not _verify_signature(body, x_gitea_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    repo_url = payload.get("repository", {}).get("clone_url")
    branch = _branch_from_ref(payload.get("ref", "refs/heads/main"))
    pr_number = payload.get("number")  # present on pull_request events
    commit_sha = (payload.get("after") or payload.get("pull_request", {}).get("head", {}).get("sha"))

    if not repo_url:
        raise HTTPException(status_code=400, detail="No repository.clone_url in payload")

    run_id = str(uuid.uuid4())[:8]
    create_run(run_id, repo_url, branch, pr_number, commit_sha)
    background_tasks.add_task(_run_pipeline, run_id, repo_url, branch, pr_number, commit_sha)

    return {"run_id": run_id, "status": "started"}
