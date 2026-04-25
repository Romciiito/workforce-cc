"""Tests for docs/running-a-session.md.

Quick structural checks — the doc's discoverability and accuracy matter
more than its prose. These tests assert the doc lists every command the
operator actually needs and that pointers to other docs aren't broken.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "running-a-session.md"


def _body() -> str:
    return DOC.read_text()


def test_doc_exists() -> None:
    assert DOC.exists()


def test_doc_covers_three_modes() -> None:
    body = _body()
    assert "Mode A" in body
    assert "Mode B" in body
    assert "Mode C" in body


def test_doc_references_orchestrator_agents() -> None:
    body = _body()
    for role in ["intent-validator", "conductor", "alignment-guard"]:
        assert role in body


def test_doc_documents_dispatch_wave() -> None:
    body = _body()
    assert "dispatch-wave" in body
    assert "--wave" in body


def test_doc_documents_status_subcommand() -> None:
    body = _body()
    assert "pipeline_runner.py status" in body
    assert "--expect" in body


def test_doc_documents_blocked_scan() -> None:
    body = _body()
    assert "blocked-scan" in body


def test_doc_explains_three_audit_layers() -> None:
    body = _body()
    for layer in ["telemetry.jsonl", "governance.jsonl", "observations.jsonl"]:
        assert layer in body


def test_doc_documents_env_var_contract() -> None:
    body = _body()
    for var in ["WORKFORCE_TELEMETRY", "WORKFORCE_MULTI_TERMINAL", "WORKFORCE_DISABLED_HOOKS"]:
        assert var in body


def test_doc_includes_troubleshooting_section() -> None:
    body = _body()
    assert "## Troubleshooting" in body
    # At least three real situations.
    troubleshoot = body[body.index("## Troubleshooting"):]
    next_section = troubleshoot.find("\n## ", 5)
    if next_section >= 0:
        troubleshoot = troubleshoot[:next_section]
    sub_count = troubleshoot.count("###")
    assert sub_count >= 3


def test_doc_links_to_canonical_pointers_at_end() -> None:
    body = _body()
    for path in [
        "BACKBONE.md",
        "artifact-contract.md",
        "bug-fix.md",
    ]:
        assert path in body


def test_doc_distinguishes_when_not_to_use() -> None:
    body = _body()
    assert "When NOT to use" in body or "when not to use" in body.lower()


def test_doc_documents_five_skills() -> None:
    """After Chunks 29 + 32, /perf and /harness must appear alongside the original three."""
    body = _body()
    for skill in ["/foundation", "/workforce", "/sync", "/perf", "/harness"]:
        assert skill in body, f"running-a-session.md missing skill: {skill}"


def test_doc_explains_multi_harness_selection() -> None:
    """Chunk 30 introduced --harnesses; the doc must explain it."""
    body = _body()
    assert "Multi-harness" in body or "multi-harness" in body.lower()
    assert "--harnesses" in body
    for harness in ["claude", "cursor", "codex", "opencode", "gemini"]:
        assert harness in body, f"missing harness in doc: {harness}"


def test_doc_explains_context_only_distinction() -> None:
    body = _body()
    assert "context-only" in body.lower() or "Context-only" in body


def test_doc_documents_adding_harness_mid_project() -> None:
    body = _body()
    assert "Adding a harness mid-project" in body or "mid-project" in body.lower()
    assert "/harness" in body


def test_doc_pointers_resolve_to_real_files() -> None:
    """Every relative-path link in the doc should point to a file that exists."""
    body = _body()
    # Match markdown links of the form [text](relative/path)
    link_re = re.compile(r"\]\(([^)]+)\)")
    relatives = [
        m.group(1) for m in link_re.finditer(body)
        if not m.group(1).startswith(("http://", "https://", "#"))
    ]
    missing = []
    for rel in relatives:
        # Strip any anchor fragment.
        path = rel.split("#", 1)[0]
        if not path:
            continue
        # Resolve relative to the doc's directory.
        target = (DOC.parent / path).resolve()
        if not target.exists():
            missing.append(rel)
    assert not missing, f"running-a-session.md has broken pointers: {missing}"
