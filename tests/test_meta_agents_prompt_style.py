"""Tests for the engineer-with-judgment shape applied to the two meta-agents
(model-selector + agent-router) in Chunk 34.

These were skipped in Chunks 12 + 14 because they're utility roles (don't
write substantive artifacts). Chunk 34 brings them into the same shape
for consistency: every agent ends with adversarial self-critique +
read-only constraints.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

META_AGENTS = {
    "agents/foundation/model-selector.md": "model-selector",
    "agents/_shared/agent-router.md": "agent-router",
}


@pytest.mark.parametrize("rel_path,name", META_AGENTS.items())
def test_meta_agent_has_adversarial_self_critique(rel_path: str, name: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    assert "## Adversarial self-critique" in body, (
        f"{name}: missing '## Adversarial self-critique' section"
    )


@pytest.mark.parametrize("rel_path,name", META_AGENTS.items())
def test_meta_agent_has_canonical_traps(rel_path: str, name: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    section = body[body.index("## Adversarial self-critique"):]
    next_h = section.find("\n## ", 1)
    if next_h >= 0:
        section = section[:next_h]
    assert "Verification avoidance" in section
    assert "first 80%" in section


@pytest.mark.parametrize("rel_path,name", META_AGENTS.items())
def test_meta_agent_has_three_X_test(rel_path: str, name: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    assert any(
        phrase in body.lower()
        for phrase in ["three different", "three-router", "three routers", "three model-selectors"]
    ), f"{name}: missing three-X test in self-critique"


@pytest.mark.parametrize("rel_path,name", META_AGENTS.items())
def test_meta_agent_has_read_only_constraints(rel_path: str, name: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    assert "## Read-only constraints" in body
    section = body[body.index("## Read-only constraints"):]
    # Both meta-agents must say they don't modify files.
    assert "do not modify" in section.lower() or "do not write" in section.lower()


def test_model_selector_warns_against_balanced_default() -> None:
    """Anti-pattern check: model-selector defaulting to Balanced for everything
    is a known degradation mode. The self-critique must call it out."""
    body = (REPO_ROOT / "agents" / "foundation" / "model-selector.md").read_text()
    section = body[body.index("## Adversarial self-critique"):]
    # Must mention the safe-middle anti-pattern.
    assert "Balanced" in section or "Sonnet" in section
    # Must explicitly say it's not always right.
    assert "not *every*" in section or "not every time" in section.lower() or "right *most*" in section


def test_agent_router_recommends_catalog_check() -> None:
    """When deciding fallbacks, agent-router should consult the catalog
    allowlist for tighter alternatives to built-in agents."""
    body = (REPO_ROOT / "agents" / "_shared" / "agent-router.md").read_text()
    section = body[body.index("## Adversarial self-critique"):]
    # The catalog_query reference is the load-bearing instruction here.
    assert "catalog_query.py" in section or "catalog allowlist" in section.lower()


def test_agent_router_warns_against_single_when_spans_tracks() -> None:
    """Anti-pattern: routing a multi-track request to a single agent."""
    body = (REPO_ROOT / "agents" / "_shared" / "agent-router.md").read_text()
    section = body[body.index("## Adversarial self-critique"):]
    assert "wave plan" in section.lower() or "spans tracks" in section.lower()
