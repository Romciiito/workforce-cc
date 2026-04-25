"""Tests that the three orchestrator agents reference the governance hook.

Chunk 10 added a `## Governance` section to each orchestrator role
prompting it to fire `hooks/dispatcher.sh fire governance ...` after major
decisions. These tests assert the references exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATORS_DIR = REPO_ROOT / "agents" / "orchestrators"


@pytest.mark.parametrize("agent", ["intent-validator", "conductor", "alignment-guard"])
def test_orchestrator_has_governance_section(agent: str) -> None:
    body = (ORCHESTRATORS_DIR / f"{agent}.md").read_text()
    assert "## Governance" in body, f"{agent}.md missing '## Governance' section"
    assert "hooks/dispatcher.sh" in body, f"{agent}.md must reference hooks/dispatcher.sh"
    assert "fire governance" in body, f"{agent}.md must invoke 'fire governance'"


@pytest.mark.parametrize("agent", ["intent-validator", "conductor", "alignment-guard"])
def test_orchestrator_says_dispatcher_is_safe_to_call_unconditionally(agent: str) -> None:
    body = (ORCHESTRATORS_DIR / f"{agent}.md").read_text()
    # The dispatcher silently no-ops when the profile excludes governance,
    # so the agent prompts must say it's safe to call without gating.
    assert "no-op" in body.lower() or "safe to call" in body.lower() or "profile-gated" in body.lower(), (
        f"{agent}.md should explain that the governance hook is safe to call unconditionally"
    )


def test_alignment_guard_governance_uses_status_argument() -> None:
    body = (ORCHESTRATORS_DIR / "alignment-guard.md").read_text()
    # alignment-guard's hook fire must include the PASS/PASS-WITH-NOTES/BLOCK status.
    assert "pass" in body.lower() and "block" in body.lower()


def test_conductor_governance_covers_three_actions() -> None:
    """Conductor should fire governance for dispatch, integrate, and retry decisions."""
    body = (ORCHESTRATORS_DIR / "conductor.md").read_text()
    governance_section = body[body.index("## Governance"):]
    for action in ["dispatch", "integrate", "retry"]:
        assert action in governance_section, (
            f"conductor.md governance section missing action: {action}"
        )


def test_conductor_references_catalog_query_for_engineer_pool() -> None:
    body = (ORCHESTRATORS_DIR / "conductor.md").read_text()
    assert "catalog_query.py" in body or "catalog allowlist" in body.lower()
    assert "additive" in body.lower(), (
        "conductor must explain that catalog entries are additive to the built-in pool, not replacements"
    )


def test_intent_validator_governance_uses_mode_argument() -> None:
    body = (ORCHESTRATORS_DIR / "intent-validator.md").read_text()
    section = body[body.index("## Governance"):]
    assert "Mode" in section
    assert "open questions" in section
