"""
Tester node: runs the target repo's test suite. This MVP assumes pytest;
swap the `cmd` list for your project's actual test runner (npm test, go
test, mvn test, etc.) or make it configurable per-repo via a
`.overseer.yaml` file in the target repo (see README "Next Steps").
"""
import subprocess

from state import PipelineState


def tester_node(state: PipelineState) -> dict:
    try:
        result = subprocess.run(
            ["pytest", "-x", "--tb=short"],
            cwd=state["repo_path"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        passed = result.returncode == 0
        output = (result.stdout + result.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        passed = False
        output = "Test run timed out after 300s"
    except FileNotFoundError:
        passed = False
        output = "pytest not found in target repo image — check the repo's test setup"

    return {"tests_passed": passed, "test_output": output}
