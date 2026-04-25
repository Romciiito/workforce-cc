"""Tests for skills/sync/SKILL.md after Chunk 19's refresh.

The /sync skill now reads .workforce/ orchestration state in addition to
the legacy 5-dimension health score. Tests assert structural invariants
in the SKILL.md (presence of new section, proper integration of
orchestration state, BLOCK-takes-precedence rule).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "sync" / "SKILL.md"


def _body() -> str:
    return SKILL_PATH.read_text()


def test_sync_skill_exists() -> None:
    assert SKILL_PATH.exists()


def test_sync_describes_orchestration_state_peek() -> None:
    body = _body()
    assert ".workforce/" in body
    # Must reference the three primary orchestration artifacts.
    assert "intent.md" in body
    assert "dispatch.md" in body or "dispatch" in body.lower()
    assert "alignment-report.md" in body


def test_sync_render_includes_orchestration_block() -> None:
    body = _body()
    # The summary template must surface orchestration state.
    assert "Orchestration state" in body or "Orchestration" in body
    # Must show alignment status range.
    assert "PASS" in body
    assert "BLOCK" in body


def test_sync_handles_missing_workforce_dir() -> None:
    body = _body()
    # The skill must explicitly say what to do when .workforce/ doesn't exist.
    assert "no .workforce" in body.lower() or "never run" in body.lower() or "doesn't exist" in body.lower()


def test_sync_block_precedence_rule_documented() -> None:
    body = _body()
    # The Rules section must explain that a BLOCK trumps a low health score.
    assert "BLOCK" in body and "precedence" in body.lower(), (
        "/sync rules must say a fresh BLOCK in alignment-report.md takes precedence "
        "over the lowest health-score dimension"
    )


def test_sync_step_numbering_is_sequential() -> None:
    """Steps 1, 2, 3, 4 in order — Chunk 19 inserted a new Step 2 (peek at .workforce/)
    and renumbered the original Do-nothing-else step to Step 4."""
    body = _body()
    for step in ["### Step 1", "### Step 2", "### Step 3", "### Step 4"]:
        assert step in body, f"missing {step}"
    # And no Step 5 (we only have four).
    assert "### Step 5" not in body


def test_sync_keeps_read_only_promise() -> None:
    """The /sync skill must keep its read-only promise even with the new state-peek."""
    body = _body()
    rules = body[body.index("## Rules"):]
    assert "Never write files" in rules
    assert "Never spawn agents" in rules


def test_sync_edge_case_for_partial_workforce_dir() -> None:
    body = _body()
    assert "incomplete" in body.lower() or "partial" in body.lower() or "half-finished" in body.lower()


def test_sync_table_compares_with_workforce() -> None:
    """The intro table comparing /sync to /workforce should still be there
    and now mention reading orchestration state."""
    body = _body()
    assert "/sync" in body and "/workforce" in body
    # The Validator → Conductor → Guard mention in the comparison table.
    assert "Validator" in body or "Conductor" in body or "Guard" in body
