"""Tests that templates/workflows/bug-fix.md carries the agent-dispatch
execution-trace methodology.

The trace template (entry point → call chain → root cause → fix site →
verification) is the single highest-leverage borrow from the agent-
dispatch repo. These tests assert it's present + structurally correct.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / "templates" / "workflows" / "bug-fix.md"


def _body() -> str:
    return WORKFLOW.read_text()


def test_workflow_file_exists() -> None:
    assert WORKFLOW.exists()


def test_workflow_introduces_execution_trace() -> None:
    body = _body()
    assert "execution trace" in body.lower()
    # Pattern attribution to agent-dispatch.
    assert "agent-dispatch" in body or "agent_dispatch" in body


def test_trace_template_has_five_required_fields() -> None:
    body = _body()
    # The trace block in the workflow must list all five fields.
    for field in ["Entry point", "Function call chain", "Root cause", "Fix site", "Verification"]:
        assert f"## {field}" in body, f"trace template missing field: ## {field}"


def test_trace_distinguishes_symptom_from_cause() -> None:
    body = _body()
    # Critical methodological note: 'Returns null' (symptom) vs 'cache not initialised' (cause).
    assert "symptom" in body.lower() and "cause" in body.lower()
    # Must explicitly say to write the cause, not the symptom.
    assert "cause is what you fix" in body.lower() or "not a symptom" in body.lower()


def test_workflow_step_3_references_trace_verification_field() -> None:
    """The regression-test step should pull its test name from the trace."""
    body = _body()
    step_3 = body[body.index("### 3."):body.index("### 4.")]
    assert "trace" in step_3.lower()
    assert "Verification" in step_3 or "verification" in step_3


def test_pr_body_template_includes_trace_summary() -> None:
    body = _body()
    # The PR body should include a Trace section so reviewers see the
    # entry-point/chain/cause/site/verification at a glance.
    pr_section = body[body.index("### 7."):]
    assert "Trace" in pr_section or "trace" in pr_section
    assert "Root cause" in pr_section
    assert "Fix site" in pr_section


def test_workflow_lists_why_traces_matter_section() -> None:
    body = _body()
    # The 'Why traces matter' subsection makes the case for the practice;
    # without it engineers might skim past the template.
    assert "Why traces matter" in body or "why traces matter" in body.lower()


def test_workflow_keeps_existing_step_numbering() -> None:
    """Steps 1-7 must still be present; chunk 15 only enriched step 2."""
    body = _body()
    for step in ["### 1.", "### 2.", "### 3.", "### 4.", "### 5.", "### 6.", "### 7."]:
        assert step in body, f"missing step: {step}"


def test_workflow_keeps_abort_conditions() -> None:
    body = _body()
    assert "Abort conditions" in body or "abort conditions" in body.lower()
