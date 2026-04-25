"""Tests for docs/rebuild-narrative.md.

Structural checks: the narrative must reference every load-bearing
chunk, link to the canonical docs, and have its internal pointers
resolve.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "rebuild-narrative.md"


def _body() -> str:
    return DOC.read_text()


def test_doc_exists() -> None:
    assert DOC.exists()


def test_doc_references_all_six_skills() -> None:
    body = _body()
    for skill in ["/foundation", "/workforce", "/sync", "/perf", "/security", "/harness"]:
        assert skill in body, f"narrative missing skill: {skill}"


def test_doc_references_all_five_harnesses() -> None:
    body = _body()
    for harness in ["claude", "cursor", "codex", "opencode", "gemini"]:
        assert harness in body, f"narrative missing harness: {harness}"


def test_doc_references_three_orchestrator_roles() -> None:
    body = _body()
    for role in ["intent-validator", "conductor", "alignment-guard"]:
        assert role in body


def test_doc_credits_all_five_borrow_sources() -> None:
    body = _body()
    for source in [
        "claude-code-system-prompts",
        "agent-dispatch",
        "everything-claude-code",
        "build-your-own-x",
        "leaked Claude Code source",
    ]:
        assert source in body, f"narrative missing borrow source: {source}"


def test_doc_has_borrow_mapping_table() -> None:
    """The narrative's payoff is the table mapping each borrow to where it landed."""
    body = _body()
    # Locate the borrows table.
    assert "How the borrows landed" in body or "borrows landed" in body.lower()
    # Spot-check a few specific cells.
    assert "envelope template" in body.lower()
    assert "permission_mode" in body
    assert "execution trace" in body.lower()


def test_doc_documents_what_we_didnt_do() -> None:
    body = _body()
    # The 'deliberately didn't' section is part of the discipline we want
    # future maintainers to inherit.
    assert "didn't do" in body.lower() or "didn't" in body.lower() or "deliberately" in body.lower()


def test_doc_pointers_resolve() -> None:
    """Every relative-path link in the narrative must point to an existing file."""
    body = _body()
    link_re = re.compile(r"\]\(([^)]+)\)")
    relatives = [
        m.group(1) for m in link_re.finditer(body)
        if not m.group(1).startswith(("http://", "https://", "#"))
    ]
    missing = []
    for rel in relatives:
        path = rel.split("#", 1)[0]
        if not path:
            continue
        target = (DOC.parent / path).resolve()
        if not target.exists():
            missing.append(rel)
    assert not missing, f"rebuild-narrative.md has broken pointers: {missing}"


def test_doc_describes_chunks_in_order() -> None:
    """The chunk-by-chunk sections must appear in chunk-number order so a reader
    can trace the arc linearly."""
    body = _body()
    # Find every reference of the form 'Chunk N' or 'Chunks N-M'.
    chunk_refs = re.findall(r"Chunks?\s+(\d+)", body)
    chunk_numbers = [int(n) for n in chunk_refs]
    # The reference sequence should be roughly monotonic — minor backreferences
    # are fine, but we expect to see the major progression. Spot-check that
    # the first occurrences of the boundary chunks are in order.
    first_indices = {}
    for i, ref in enumerate(chunk_numbers):
        if ref not in first_indices:
            first_indices[ref] = i
    # Check first occurrences of 1, 12, 25, 36 are in increasing order.
    boundaries = [1, 12, 25, 36]
    indices = [first_indices.get(b) for b in boundaries if b in first_indices]
    assert indices == sorted(indices), (
        f"chunk-number references out of order: boundaries {boundaries} → indices {indices}"
    )


def test_doc_references_test_count() -> None:
    """The 'Test surface' section must report a real-looking test count."""
    body = _body()
    assert "Test surface" in body
    # Pick out any number that looks like a test count.
    counts = re.findall(r"(\d{3,4})\s+pytest", body)
    assert counts, "rebuild-narrative.md should report pytest test count in Test surface section"
