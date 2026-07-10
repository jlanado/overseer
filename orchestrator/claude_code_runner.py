"""
Thin wrapper around the Claude Code CLI's headless (`-p`) mode.

Used by the Fixer node — the one step in the pipeline that needs real,
repo-aware file edits rather than just reasoning over text. Everything else
(Reviewer, Security) reasons over a diff/output as plain text via CrewAI +
either the Anthropic API or the same LiteLLM proxy, since they don't need
to touch files.

Auth — two modes, controlled by whether LITELLM_BASE_URL is set:

  Mode A (direct Anthropic): ANTHROPIC_API_KEY is used as-is. In headless
  (-p) mode, Claude Code prefers an API key over any subscription credential
  when both are present — the deterministic behavior wanted here since
  Overseer wraps Claude Code inside a larger orchestrated pipeline.

  Mode B (LiteLLM proxy, e.g. local Ollama models): Claude Code is pointed
  at the proxy via ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN instead.
  ANTHROPIC_MODEL / ANTHROPIC_SMALL_FAST_MODEL remap Claude Code's hardcoded
  sonnet/opus/haiku aliases to whatever model names are registered in the
  proxy. ANTHROPIC_API_KEY is intentionally NOT forwarded in this mode —
  Claude Code docs are explicit that the auth token, not the API key, is
  the credential to use against a third-party base URL.
"""
import json
import os
import subprocess

from config import settings


class ClaudeCodeError(Exception):
    pass


def _build_env() -> dict:
    env = os.environ.copy()

    if settings.using_litellm:
        env["ANTHROPIC_BASE_URL"] = settings.litellm_base_url
        env["ANTHROPIC_AUTH_TOKEN"] = settings.litellm_api_key
        if settings.anthropic_model:
            env["ANTHROPIC_MODEL"] = settings.anthropic_model
        if settings.anthropic_small_fast_model:
            env["ANTHROPIC_SMALL_FAST_MODEL"] = settings.anthropic_small_fast_model
        env.pop("ANTHROPIC_API_KEY", None)
    else:
        env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    return env


def run_claude_code(
    prompt: str,
    repo_path: str,
    allowed_tools: str = "Read,Edit,Bash,Grep,Glob",
    max_turns: int = 8,
    timeout: int = 900,
) -> dict:
    """
    Runs Claude Code headlessly against `repo_path` and returns the parsed
    JSON result. Raises ClaudeCodeError on non-zero exit or bad JSON.

    --dangerously-skip-permissions is used because this runs inside the
    orchestrator container, which mounts only the scoped per-run workspace
    (see WORKSPACE_DIR in config.py) — not the host filesystem. Do not lift
    this pattern into a context where Claude Code can reach anything wider
    than that scoped directory.
    """
    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
        "--allowedTools", allowed_tools,
        "--max-turns", str(max_turns),
        "--dangerously-skip-permissions",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
        )
    except subprocess.TimeoutExpired as e:
        raise ClaudeCodeError(f"Claude Code timed out after {timeout}s") from e

    if result.returncode != 0:
        raise ClaudeCodeError(
            f"Claude Code exited {result.returncode}: {result.stderr[:2000]}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeCodeError(
            f"Could not parse Claude Code output as JSON: {result.stdout[:2000]}"
        ) from e

    # Known failure mode: exit code 0 with an empty/irrelevant result.
    # Surface it rather than silently treating this as success.
    if not payload.get("result"):
        raise ClaudeCodeError(f"Claude Code returned an empty result: {payload}")

    return payload
