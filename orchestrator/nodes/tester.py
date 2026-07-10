"""
Tester node: runs the target repo's test suite. Defaults to pytest, but a
target repo can override the command via a `.overseer.yaml` file at its
root:

    test_command: npm test -- --ci

Falls back to the pytest default if the file is missing, unparseable, or
doesn't set `test_command` — a target repo with no opinion on this still
works exactly as before.
"""
import shlex
import subprocess
from pathlib import Path

import yaml
from langfuse import observe

from state import PipelineState

DEFAULT_TEST_COMMAND = ["pytest", "-x", "--tb=short"]


def _load_test_command(repo_path: str) -> list[str]:
    config_path = Path(repo_path) / ".overseer.yaml"
    if not config_path.exists():
        return DEFAULT_TEST_COMMAND

    try:
        config = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError:
        return DEFAULT_TEST_COMMAND

    command = config.get("test_command")
    if isinstance(command, str) and command.strip():
        return shlex.split(command)

    return DEFAULT_TEST_COMMAND


@observe(name="test")
def tester_node(state: PipelineState) -> dict:
    command = _load_test_command(state["repo_path"])

    try:
        result = subprocess.run(
            command,
            cwd=state["repo_path"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        passed = result.returncode == 0
        output = (result.stdout + result.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        passed = False
        output = f"Test run timed out after 300s (command: {' '.join(command)})"
    except FileNotFoundError:
        passed = False
        output = f"Test command not found in target repo image: {' '.join(command)}"

    return {"tests_passed": passed, "test_output": output}
