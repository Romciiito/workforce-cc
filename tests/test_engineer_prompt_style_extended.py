"""Tests for Chunk 14: extend the engineer-with-judgment prompt-style pass to
the remaining engineer agents.

Same shape as test_engineer_prompt_style.py (architect, security-analyst,
requirements-engineer) — just applied to nine more agents:

  Foundation engineers: idea-refiner, market-researcher, stack-selector,
                        workplan-builder.
  Shared engineers:    performance-analyst, test-strategist, agent-generator.
  Workforce engineers: scanner, gap-analyst, doc-writer.

Skipped: model-selector, agent-router (utility roles; no substantive
artifact; the additional prompt sections would be overkill).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

ENGINEERS = {
    "agents/foundation/idea-refiner.md": "spec.md",
    "agents/foundation/market-researcher.md": "market-analysis.md",
    "agents/foundation/stack-selector.md": "stack-decision.md",
    "agents/foundation/workplan-builder.md": "workplan.md",
    "agents/_shared/performance-analyst.md": "performance-model.md",
    "agents/_shared/test-strategist.md": "test-plan.md",
    "agents/_shared/agent-generator.md": ".claude/agents/",
    "agents/workforce/scanner.md": "project-snapshot.md",
    "agents/workforce/gap-analyst.md": "gap-report.md",
    "agents/workforce/doc-writer.md": "doc-writer",  # owned territory is "approved gap-report files"
}


@pytest.mark.parametrize("rel_path,owned", ENGINEERS.items())
def test_engineer_has_adversarial_self_critique(rel_path: str, owned: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    assert "## Adversarial self-critique" in body, (
        f"{rel_path} missing '## Adversarial self-critique' section"
    )


@pytest.mark.parametrize("rel_path,_", ENGINEERS.items())
def test_engineer_self_critique_lists_canonical_traps(rel_path: str, _: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    section_start = body.index("## Adversarial self-critique")
    section = body[section_start:]
    next_heading = section.find("\n## ", 1)
    if next_heading >= 0:
        section = section[:next_heading]
    for trap in ["Verification avoidance", "first 80%"]:
        assert trap in section, f"{rel_path} self-critique missing trap: {trap}"


@pytest.mark.parametrize("rel_path,_", ENGINEERS.items())
def test_engineer_uses_three_reviewer_test(rel_path: str, _: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    has_three_test = any(
        phrase in body.lower()
        for phrase in [
            "three different",
            "three reviewers",
            "three engineers",
            "three architects",
            "three teammates",
            "three test engineers",
            "three performance engineers",
            "three market analysts",
            "three-reviewer",
            "three-engineer",
        ]
    )
    assert has_three_test, f"{rel_path} self-critique should include a three-reviewer-style test"


@pytest.mark.parametrize("rel_path,_", ENGINEERS.items())
def test_engineer_has_read_only_constraint(rel_path: str, _: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    assert "## Read-only constraints" in body, (
        f"{rel_path} missing '## Read-only constraints' section"
    )


@pytest.mark.parametrize("rel_path,owned", [
    (p, o) for p, o in ENGINEERS.items()
    # doc-writer's territory is "files approved in gap-report" — variable, so we
    # check for the broader 'gap-report' reference instead of a specific filename.
    if "doc-writer" not in p
])
def test_engineer_read_only_lists_owned_artifact(rel_path: str, owned: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    section_start = body.index("## Read-only constraints")
    section = body[section_start:]
    assert owned in section, (
        f"{rel_path} read-only section must reference its owned output: {owned}"
    )


def test_doc_writer_read_only_references_gap_report() -> None:
    """doc-writer's territory is dynamic ('approved files in gap-report'),
    so we check the section references the upstream input rather than a
    specific filename."""
    body = (REPO_ROOT / "agents" / "workforce" / "doc-writer.md").read_text()
    section = body[body.index("## Read-only constraints"):]
    assert "gap-report" in section
    # Must explicitly forbid editing existing doc bodies.
    assert "must not" in section.lower()
    # The append-only behavior for stale docs is a hard rule.
    assert "Update Needed" in section or "append" in section.lower()


@pytest.mark.parametrize("rel_path,_", ENGINEERS.items())
def test_engineer_read_only_explains_open_issues_escalation_or_equivalent(rel_path: str, _: str) -> None:
    """Each engineer must explain how to surface a finding that needs an
    upstream fix — typically via an 'Open issues' section in the engineer's
    own output."""
    body = (REPO_ROOT / rel_path).read_text()
    section = body[body.index("## Read-only constraints"):]
    has_escalation = (
        "Open issues" in section
        or "Findings" in section
        or "## Code-side findings" in section
        or "Recommended architectural changes" in section
        or "Update Needed" in section  # doc-writer's specific append pattern
        or "decisions.md" in section.lower()  # agent-generator escalates via decisions.md
    )
    assert has_escalation, (
        f"{rel_path} read-only section must explain how to escalate findings "
        f"that need upstream fixes (typically '## Open issues' in the engineer's own output)"
    )
