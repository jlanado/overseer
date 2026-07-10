from typing import TypedDict, Optional


class PipelineState(TypedDict):
    run_id: str
    repo_url: str
    repo_path: str          # local clone path inside the orchestrator container
    branch: str
    pr_number: Optional[int]
    commit_sha: Optional[str]

    diff: str
    review_notes: str
    needs_fix: bool

    fix_attempts: int
    max_fix_attempts: int

    tests_passed: bool
    test_output: str

    security_passed: bool
    security_output: str

    approved: Optional[bool]  # None = pending, True/False once resolved

    deployed: bool
    error: Optional[str]
