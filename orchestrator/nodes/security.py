"""
Security node: runs bandit (Python SAST) against the repo and blocks on
high-severity findings. Swap/add scanners (Trivy for images, Semgrep for
multi-language) as your target repos diversify beyond Python.
"""
import json
import subprocess

from langfuse import observe

from state import PipelineState


@observe(name="security")
def security_node(state: PipelineState) -> dict:
    try:
        result = subprocess.run(
            ["bandit", "-r", ".", "-f", "json", "-ll"],  # -ll = only medium+ severity
            cwd=state["repo_path"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        report = json.loads(result.stdout or "{}")
        high_severity = [
            r for r in report.get("results", [])
            if r.get("issue_severity") in ("HIGH", "MEDIUM")
        ]
        passed = len(high_severity) == 0
        summary = (
            "No medium/high severity findings."
            if passed
            else "\n".join(
                f"[{r['issue_severity']}] {r['filename']}:{r['line_number']} — {r['issue_text']}"
                for r in high_severity
            )
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        # Fail closed: if the scanner itself breaks, don't silently pass security.
        passed = False
        summary = "Security scan failed to run or produced unparseable output — blocking deploy."

    return {"security_passed": passed, "security_output": summary}
