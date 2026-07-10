"""
Tests for the routing functions in graph.py — the bounded-loop governance
logic that is the architectural centerpiece of this project (see CLAUDE.md
"Bounded-loop governance"). Each route_after_* function is a pure function
over a plain PipelineState dict, so these need no mocking of nodes, no
LangGraph invocation, and no network access.
"""
from graph import (
    route_after_approval,
    route_after_review,
    route_after_security,
    route_after_test,
)


def test_review_with_no_issues_skips_fix():
    assert route_after_review({"needs_fix": False}) == "security"


def test_review_with_issues_routes_to_fix():
    assert route_after_review({"needs_fix": True}) == "fix"


def test_passing_tests_route_to_security():
    state = {"tests_passed": True, "fix_attempts": 0, "max_fix_attempts": 3}
    assert route_after_test(state) == "security"


def test_failing_tests_retry_while_under_cap():
    state = {"tests_passed": False, "fix_attempts": 1, "max_fix_attempts": 3}
    assert route_after_test(state) == "fix"


def test_failing_tests_stop_at_cap_instead_of_looping_forever():
    state = {"tests_passed": False, "fix_attempts": 3, "max_fix_attempts": 3}
    assert route_after_test(state) == "end_failed"


def test_failing_tests_stop_if_somehow_over_cap():
    state = {"tests_passed": False, "fix_attempts": 4, "max_fix_attempts": 3}
    assert route_after_test(state) == "end_failed"


def test_security_pass_routes_to_approval():
    assert route_after_security({"security_passed": True}) == "approval"


def test_security_fail_routes_to_end_not_approval():
    assert route_after_security({"security_passed": False}) == "end_failed"


def test_approved_routes_to_deploy():
    assert route_after_approval({"approved": True}) == "deploy"


def test_rejected_routes_to_end_not_deploy():
    assert route_after_approval({"approved": False}) == "end_rejected"
