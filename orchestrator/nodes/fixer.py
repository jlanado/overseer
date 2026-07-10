"""
Fixer node: hands the Reviewer's notes (or the Tester's failure output, on
retry) to Claude Code headlessly, so it can make real edits in the cloned
repo working tree.
"""
from langfuse import observe

from state import PipelineState
from claude_code_runner import run_claude_code, ClaudeCodeError


@observe(name="fix")
def fixer_node(state: PipelineState) -> dict:
    context = state.get("review_notes", "")
    if state.get("test_output"):
        context += f"\n\nMost recent test failure output:\n{state['test_output']}"

    prompt = (
        "Fix the following issues in this repository. Make the smallest "
        "correct change that resolves them — do not refactor unrelated code.\n\n"
        f"{context}"
    )

    try:
        run_claude_code(
            prompt=prompt,
            repo_path=state["repo_path"],
            allowed_tools="Read,Edit,Bash,Grep,Glob",
        )
        return {"fix_attempts": state["fix_attempts"] + 1, "error": None}
    except ClaudeCodeError as e:
        return {
            "fix_attempts": state["fix_attempts"] + 1,
            "error": f"Fixer failed: {e}",
        }
