"""Tests for Chunk 24: LICENSE at repo root + template refreshes for new artifacts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_JINJA = importlib.util.find_spec("jinja2") is not None


# ── LICENSE ──────────────────────────────────────────────────────────────────


def test_license_file_exists() -> None:
    assert (REPO_ROOT / "LICENSE").exists(), "Repo root must have a LICENSE file"


def test_license_is_mit() -> None:
    body = (REPO_ROOT / "LICENSE").read_text()
    assert "MIT License" in body
    assert "Permission is hereby granted" in body


def test_license_documents_catalog_attribution() -> None:
    body = (REPO_ROOT / "LICENSE").read_text()
    # The LICENSE must explain that catalogs/<source>/ entries carry their
    # upstream license, not just the repo root MIT.
    assert "catalogs/" in body
    assert "upstream" in body.lower()


# ── CLAUDE.md.jinja ──────────────────────────────────────────────────────────


def test_claude_md_template_references_workforce_artifacts() -> None:
    body = (REPO_ROOT / "templates" / "CLAUDE.md.jinja").read_text()
    # The pointer table should include orchestration artifacts.
    for artifact in [".workforce/intent.md", ".workforce/dispatch.md", ".workforce/alignment-report.md"]:
        assert artifact in body, f"CLAUDE.md.jinja missing pointer to {artifact}"


def test_claude_md_template_uses_env_prefix_var() -> None:
    """The env prefix interpolation should use the {{ env_prefix }} var
    that scaffold.py provides, not a derived expression."""
    body = (REPO_ROOT / "templates" / "CLAUDE.md.jinja").read_text()
    assert "{{ env_prefix }}" in body
    # The legacy `{{ project_name | upper | replace... }}` shouldn't be
    # the source of the env prefix any more — too fragile.
    assert "{{ project_name | upper" not in body


def test_claude_md_template_mentions_approach_md_discipline() -> None:
    body = (REPO_ROOT / "templates" / "CLAUDE.md.jinja").read_text()
    assert "approach.md" in body
    # Allow markdown emphasis (`*before*`, `**before**`) between the keyword
    # and the next word.
    import re
    assert re.search(r"before\W*\*?producing", body, re.IGNORECASE) or "before your declared" in body.lower()


def test_claude_md_template_mentions_alignment_report_block() -> None:
    body = (REPO_ROOT / "templates" / "CLAUDE.md.jinja").read_text()
    assert "alignment-report.md" in body
    assert "BLOCK" in body


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_claude_md_template_renders_with_strict_undefined() -> None:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    rendered = env.get_template("CLAUDE.md.jinja").render(
        project_name="Acme",
        description="An acme thing",
        stack="python-fastapi",
        env_prefix="ACME",
        critical_rules="",
    )
    assert "ACME_" in rendered
    assert "{{" not in rendered


# ── WORKFORCE.md.jinja ───────────────────────────────────────────────────────


def test_workforce_md_template_has_orchestration_section() -> None:
    body = (REPO_ROOT / "templates" / "WORKFORCE.md.jinja").read_text()
    assert "Orchestration artifacts" in body
    for artifact in ["intent.md", "dispatch.md", "alignment-report.md", "integration.md"]:
        assert artifact in body


def test_workforce_md_template_handles_no_orchestration_gracefully() -> None:
    """If a /workforce run was just a /sync-style audit (no .workforce/ output),
    the template must still render cleanly."""
    body = (REPO_ROOT / "templates" / "WORKFORCE.md.jinja").read_text()
    # An {% else %} branch covers the no-orchestration case.
    assert "{% else %}" in body or "no .workforce/" in body


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_workforce_md_template_renders_with_orchestration() -> None:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    rendered = env.get_template("WORKFORCE.md.jinja").render(
        project_name="Acme",
        run_date="2026-04-25",
        trigger="manual",
        scores={
            "vision": 8, "vision_status": "ok",
            "docs": 7, "docs_status": "5/7 present",
            "security": 6, "security_status": "Phase 0 partial",
            "agents": 9, "agents_status": "all 6 present",
            "workplan": 8, "workplan_status": "current",
            "total": 38,
        },
        agents_spawned=[{"name": "scanner", "outcome": "DONE"}],
        docs_created=["docs/claude/architecture.md"],
        docs_flagged=[],
        open_items=[],
        next_run_recommendation="Run /workforce in 30 days",
        next_run_trigger="20",
        key_finding="docs are mostly current",
        orchestration={
            "intent_status": "captured 2026-04-25",
            "dispatch_summary": "wave 1: 4 engineers",
            "alignment_status": "PASS-WITH-NOTES",
            "alignment_findings": 2,
            "integration_summary": "all artifacts produced; 0 cross-cuts",
        },
    )
    assert "PASS-WITH-NOTES" in rendered
    assert "2 findings" in rendered


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_workforce_md_template_renders_without_orchestration() -> None:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    rendered = env.get_template("WORKFORCE.md.jinja").render(
        project_name="Acme",
        run_date="2026-04-25",
        trigger="manual",
        scores={
            "vision": 8, "vision_status": "ok",
            "docs": 7, "docs_status": "ok",
            "security": 6, "security_status": "ok",
            "agents": 9, "agents_status": "ok",
            "workplan": 8, "workplan_status": "ok",
            "total": 38,
        },
        agents_spawned=[],
        docs_created=[],
        docs_flagged=[],
        open_items=[],
        next_run_recommendation="proceed",
        next_run_trigger="20",
        key_finding="",
        orchestration=None,
    )
    assert "no .workforce/ orchestration" in rendered or "/sync-style" in rendered
