"""
Fixer node: hands the Reviewer's notes (or the Tester's failure output, on
retry) to Claude Code headlessly, so it can make real edits in the cloned
repo working tree.

If DIFF_ONLY_MODE is on (see config.py), the prompt names the files touched
by the triggering diff and Edit is scoped to just those paths via
allowedTools — the actual token-spend lever is telling Claude Code what's
relevant up front, since that's what cuts down on it Glob/Grep-ing the whole
repo to figure out what to look at. The Edit scoping is defense in depth on
top of that, not a hard boundary: Bash stays unscoped (Fixer needs it for
things like `git status`), and Bash can write files too.
"""
import re

from langfuse import observe

from state import PipelineState
from config import settings
from claude_code_runner import run_claude_code, ClaudeCodeError

_DIFF_GIT_LINE = re.compile(r"^diff --git a/.+? b/(.+)$", re.MULTILINE)


def _extract_changed_files(diff: str) -> list[str]:
    return _DIFF_GIT_LINE.findall(diff)


@observe(name="fix")
def fixer_node(state: PipelineState) -> dict:
    context = state.get("review_notes", "")
    if state.get("test_output"):
        context += f"\n\nMost recent test failure output:\n{state['test_output']}"

    changed_files = _extract_changed_files(state["diff"]) if settings.diff_only_mode else []

    if changed_files:
        file_list = "\n".join(f"- {f}" for f in changed_files)
        prompt = (
            "Fix the following issues in this repository. Make the smallest "
            "correct change that resolves them — do not refactor unrelated code.\n\n"
            f"Files changed by the triggering diff (stay within these unless you "
            f"need to read other files for context):\n{file_list}\n\n"
            f"{context}"
        )
        allowed_tools = "Read,Bash,Grep,Glob," + ",".join(f"Edit({f})" for f in changed_files)
    else:
        prompt = (
            "Fix the following issues in this repository. Make the smallest "
            "correct change that resolves them — do not refactor unrelated code.\n\n"
            f"{context}"
        )
        allowed_tools = "Read,Edit,Bash,Grep,Glob"

    try:
        run_claude_code(
            prompt=prompt,
            repo_path=state["repo_path"],
            allowed_tools=allowed_tools,
        )
        return {"fix_attempts": state["fix_attempts"] + 1, "error": None}
    except ClaudeCodeError as e:
        return {
            "fix_attempts": state["fix_attempts"] + 1,
            "error": f"Fixer failed: {e}",
        }
