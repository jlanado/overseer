"""
Reviewer node: a CrewAI agent reads the PR diff and produces structured
review notes. Pure reasoning over text — no file access needed, so this
goes through the Anthropic API directly rather than Claude Code.
"""
import json

from crewai import Agent, Task, Crew, LLM

from state import PipelineState
from config import settings

llm = LLM(model="anthropic/claude-sonnet-4-6", api_key=settings.anthropic_api_key)

reviewer_agent = Agent(
    role="Senior Code Reviewer",
    goal="Identify real bugs, security issues, and code smells in a diff — skip nitpicks.",
    backstory=(
        "You are a pragmatic staff engineer doing a pre-merge review. You care about "
        "correctness, security, and maintainability. You do not comment on formatting "
        "or style choices a linter would catch."
    ),
    llm=llm,
    verbose=False,
)


def review_node(state: PipelineState) -> dict:
    task = Task(
        description=(
            f"Review this diff:\n\n{state['diff']}\n\n"
            "Respond ONLY with JSON: "
            '{"issues_found": bool, "notes": "<concise list of concrete issues, '
            'or empty string if none>"}'
        ),
        expected_output="A JSON object with issues_found and notes.",
        agent=reviewer_agent,
    )
    crew = Crew(agents=[reviewer_agent], tasks=[task], verbose=False)
    result = crew.kickoff()

    try:
        parsed = json.loads(str(result))
        needs_fix = bool(parsed.get("issues_found", False))
        notes = parsed.get("notes", "")
    except (json.JSONDecodeError, AttributeError):
        # Model didn't return clean JSON — fail safe by routing to Fixer
        # with the raw text, rather than silently skipping review.
        needs_fix = True
        notes = str(result)

    return {"review_notes": notes, "needs_fix": needs_fix}
