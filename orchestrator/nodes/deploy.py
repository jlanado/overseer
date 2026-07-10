"""
Deploy node: builds the target repo's image, pushes it to the local
registry, and brings it up via docker compose on the host. Assumes the
target repo has its own docker-compose.yml (or Dockerfile) at its root —
see example-target-app/ for the minimal shape expected.
"""
import subprocess

from langfuse import observe

from state import PipelineState
from config import settings


@observe(name="deploy")
def deploy_node(state: PipelineState) -> dict:
    image_tag = f"{settings.registry_url}/{state['run_id']}:latest"

    try:
        subprocess.run(
            ["docker", "build", "-t", image_tag, "."],
            cwd=state["repo_path"],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        subprocess.run(
            ["docker", "push", image_tag],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            cwd=state["repo_path"],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {"deployed": True, "error": None}
    except subprocess.CalledProcessError as e:
        return {
            "deployed": False,
            "error": f"Deploy failed: {e.stderr[:2000] if e.stderr else str(e)}",
        }
    except subprocess.TimeoutExpired as e:
        return {"deployed": False, "error": f"Deploy step timed out: {e}"}
