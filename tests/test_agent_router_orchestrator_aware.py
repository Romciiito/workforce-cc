"""Tests that agent-router knows about the new orchestrator roles + catalog.

Chunk 23 updates agents/_shared/agent-router.md to:
1. List the three orchestrator roles (intent-validator, conductor,
   alignment-guard) in the agent catalog.
2. Mark the legacy orchestrators as DEPRECATED in the same table.
3. Mention the catalog allowlist as an extension to the built-in pool.
4. Add Rule 0 (vague request → route to intent-validator first).
5. Add Rule 3.5 (multi-engineer dispatch → route to conductor).
6. Add Rule 3.6 (drift/consistency check → route to alignment-guard).
7. Update the routing table with three new triggers (alignment-guard
   modes + intent-validator).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTER = REPO_ROOT / "agents" / "_shared" / "agent-router.md"


def _body() -> str:
    return ROUTER.read_text()


def test_router_lists_three_orchestrator_roles() -> None:
    body = _body()
    for role in ["intent-validator", "conductor", "alignment-guard"]:
        assert role in body, f"agent-router must reference orchestrator role: {role}"


def test_router_marks_legacy_orchestrators_deprecated() -> None:
    body = _body()
    # Find the meta table block.
    meta_idx = body.index("### Meta")
    next_section = body.find("###", meta_idx + 1)
    meta_block = body[meta_idx:next_section]
    assert "DEPRECATED" in meta_block
    assert "foundation-orchestrator" in meta_block
    assert "workforce-orchestrator" in meta_block


def test_router_describes_three_orchestrator_modes() -> None:
    body = _body()
    # conductor should reference its three sub-modes
    assert "dispatch" in body and "monitor" in body and "integrate" in body
    # alignment-guard should reference its two modes
    assert "vision" in body
    assert "cross-check" in body
    # intent-validator should reference its three modes
    assert "Mode A" in body or "greenfield interrogation" in body.lower()


def test_router_mentions_catalog_allowlist() -> None:
    body = _body()
    assert "catalog_query.py" in body or "catalog allowlist" in body.lower()
    assert "enabled" in body.lower()


def test_router_has_rule_0_for_vague_requests() -> None:
    body = _body()
    assert "Rule 0" in body
    rule_block = body[body.index("### Rule 0"):body.index("### Rule 1")]
    assert "intent-validator" in rule_block
    assert "vague" in rule_block.lower() or "too vague" in rule_block.lower()


def test_router_has_rule_for_multi_engineer_dispatch() -> None:
    body = _body()
    # Either Rule 3.5 or some equivalent — the matcher must point at conductor
    # for multi-engineer dispatch.
    assert "Rule 3.5" in body or "Multi-engineer" in body or "multi-engineer" in body.lower()
    # Look for the conductor + dispatch pairing in the rule.
    rule35_start = body.find("Rule 3.5")
    if rule35_start >= 0:
        section = body[rule35_start:body.find("Rule", rule35_start + 1)]
        assert "conductor" in section
        assert "dispatch" in section


def test_router_has_rule_for_alignment_guard() -> None:
    body = _body()
    assert "Rule 3.6" in body or "alignment-guard" in body
    # Both modes referenced.
    assert "vision" in body and "cross-check" in body


def test_routing_table_has_alignment_guard_entries() -> None:
    body = _body()
    # The Task-type-detection table should list at least two alignment-guard triggers.
    table_idx = body.index("Task type detection")
    next_section = body.find("###", table_idx + 1)
    table = body[table_idx:next_section]
    assert "alignment-guard" in table
    # And an intent-validator entry.
    assert "intent-validator" in table or "intent" in table.lower()


def test_router_does_not_remove_existing_rules() -> None:
    """Chunk 23 is additive — no existing rule should disappear."""
    body = _body()
    for rule in ["Rule 1", "Rule 2", "Rule 3", "Rule 4", "Rule 5", "Rule 6"]:
        assert rule in body, f"agent-router missing legacy {rule}"
