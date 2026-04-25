"""Tests that skills/foundation/SKILL.md Phase 2 surfaces MCP suggestions.

After Chunk 22, Foundation's Phase 2 (skill suggestions) is followed by
a Phase 2.5 that queries catalogs/mcp/index.json for stack-specific
servers and offers them to the user. These tests assert the new content
is present without locking in exact wording.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "foundation" / "SKILL.md"


def _body() -> str:
    return SKILL_PATH.read_text()


def test_phase_2_5_mcp_section_present() -> None:
    body = _body()
    assert "Phase 2.5" in body or "MCP server suggestions" in body
    assert "mcp_query.py" in body


def test_phase_2_5_uses_list_stack_filter() -> None:
    body = _body()
    # The script is invoked via shell quoting, so allow `mcp_query.py" list` too.
    assert re.search(r"mcp_query\.py\"?\s+list", body)
    # Must filter by stack so the user sees stack-relevant servers.
    assert "--stack" in body


def test_phase_2_5_documents_emit_apply() -> None:
    body = _body()
    assert re.search(r"mcp_query\.py\"?\s+emit", body)
    assert "--apply" in body


def test_phase_2_5_documents_placeholders() -> None:
    body = _body()
    assert "--placeholders" in body
    # Must reference a real placeholder pattern like ${VAR_NAME} OR a concrete example like GITHUB_TOKEN.
    assert "${" in body or "GITHUB_TOKEN" in body


def test_phase_2_5_explicitly_optional() -> None:
    body = _body()
    # The MCP catalog must be opt-in; missing this language risks pushing every project into MCP land.
    assert "optional" in body.lower() or "skip" in body.lower()


def test_phase_2_5_appears_between_phase_2_and_phase_3() -> None:
    body = _body()
    p2 = body.find("## PHASE 2")
    p25 = body.find("Phase 2.5")
    p3 = body.find("## PHASE 3")
    assert p2 >= 0 and p25 >= 0 and p3 >= 0
    assert p2 < p25 < p3, "Phase 2.5 must sit between Phase 2 and Phase 3"
