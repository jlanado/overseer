"""
The Overseer pipeline as a LangGraph StateGraph.

    START -> review -> [needs_fix?] -> fix -> test -> [passed?] -> security
                |no                     ^         |fail, retries left
                v                       └─────────┘
             security                                |fail, out of retries -> END (failed)
                |
          [passed?] -> approval -> [approved?] -> deploy -> END
                |fail                     |no
                v                         v
               END (failed)              END (rejected)

Checkpointer: MemorySaver for this MVP (state lives in orchestrator process
memory for the run's lifetime). Swap for a Postgres-backed checkpointer if
you want runs to survive an orchestrator restart mid-flight.
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import PipelineState
from nodes.reviewer import review_node
from nodes.fixer import fixer_node
from nodes.tester import tester_node
from nodes.security import security_node
from nodes.approval import approval_node
from nodes.deploy import deploy_node


def route_after_review(state: PipelineState) -> str:
    return "fix" if state["needs_fix"] else "security"


def route_after_test(state: PipelineState) -> str:
    if state["tests_passed"]:
        return "security"
    if state["fix_attempts"] < state["max_fix_attempts"]:
        return "fix"
    return "end_failed"


def route_after_security(state: PipelineState) -> str:
    return "approval" if state["security_passed"] else "end_failed"


def route_after_approval(state: PipelineState) -> str:
    return "deploy" if state["approved"] else "end_rejected"


def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("review", review_node)
    graph.add_node("fix", fixer_node)
    graph.add_node("test", tester_node)
    graph.add_node("security", security_node)
    graph.add_node("approval", approval_node)
    graph.add_node("deploy", deploy_node)

    graph.add_edge(START, "review")
    graph.add_conditional_edges(
        "review", route_after_review, {"fix": "fix", "security": "security"}
    )
    graph.add_edge("fix", "test")
    graph.add_conditional_edges(
        "test", route_after_test,
        {"security": "security", "fix": "fix", "end_failed": END},
    )
    graph.add_conditional_edges(
        "security", route_after_security, {"approval": "approval", "end_failed": END}
    )
    graph.add_conditional_edges(
        "approval", route_after_approval, {"deploy": "deploy", "end_rejected": END}
    )
    graph.add_edge("deploy", END)

    return graph.compile(checkpointer=MemorySaver())


overseer_graph = build_graph()
