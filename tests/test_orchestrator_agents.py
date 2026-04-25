"""Tests for agents/orchestrators/{intent-validator,conductor,alignment-guard}.md.

The three orchestrator role definitions are the spine of the new architecture.
Each is a markdown file with frontmatter and a structured body. These tests
assert structural invariants — frontmatter completeness, required headings,
refusal-condition language, and adversarial-self-critique presence — so the
files don't silently drift away from the contract documented in
docs/artifact-contract.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATORS_DIR = REPO_ROOT / "agents" / "orchestrators"

ORCHESTRATORS = ["intent-validator", "conductor", "alignment-guard"]

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\s*\n", re.DOTALL)
KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")


def _load(name: str) -> str:
    path = ORCHESTRATORS_DIR / f"{name}.md"
    assert path.exists(), f"missing orchestrator file: {path}"
    return path.read_text()


def _frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    assert m, "agent file must start with --- frontmatter ---"
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = KV_RE.match(line)
        if not kv:
            continue
        out[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return out


@pytest.mark.parametrize("agent", ORCHESTRATORS)
def test_orchestrator_file_exists(agent: str) -> None:
    assert (ORCHESTRATORS_DIR / f"{agent}.md").exists()


@pytest.mark.parametrize("agent", ORCHESTRATORS)
def test_frontmatter_has_required_fields(agent: str) -> None:
    fm = _frontmatter(_load(agent))
    for field in ["name", "description", "tools", "model"]:
        assert field in fm, f"{agent}: missing frontmatter field: {field}"


@pytest.mark.parametrize("agent", ORCHESTRATORS)
def test_orchestrator_runs_on_opus(agent: str) -> None:
    """All three orchestrators are load-bearing decisions; they should run on Opus."""
    fm = _frontmatter(_load(agent))
    assert fm["model"] == "opus", f"{agent}: model must be 'opus' (got {fm['model']!r})"


def test_intent_validator_lists_required_intent_md_sections() -> None:
    body = _load("intent-validator")
    for section in [
        "## What it is",
        "## Who it's for",
        "## Concrete success",
        "## Constraints",
        "## Out of scope",
        "## Open questions",
    ]:
        assert section in body, f"intent-validator missing reference to required intent.md section: {section}"


def test_intent_validator_has_refusal_conditions() -> None:
    body = _load("intent-validator")
    assert "## Refusal conditions" in body
    # Must reference the placeholder-text refusal trigger.
    assert ("placeholder text" in body or '"TBD"' in body), (
        "intent-validator must refuse to write intent.md when sections contain only placeholders"
    )


def test_intent_validator_has_read_only_constraint() -> None:
    body = _load("intent-validator")
    # Patterns borrowed from claude-code-system-prompts: explicit prohibition on write Bash.
    assert "Read-only constraints" in body
    for forbidden in ["mkdir", "touch", "rm", "cp", "mv"]:
        assert forbidden in body, f"intent-validator's read-only block must list: {forbidden}"


def test_intent_validator_has_three_modes() -> None:
    body = _load("intent-validator")
    for mode_label in ["A: Greenfield", "B: Revision", "C: Pass-through"]:
        assert mode_label in body, f"intent-validator missing mode: {mode_label}"


def test_intent_validator_has_adversarial_self_critique() -> None:
    body = _load("intent-validator")
    assert "Adversarial self-critique" in body, (
        "intent-validator must include the adversarial self-critique section "
        "(borrowed from claude-code-system-prompts verification-agent pattern)"
    )


def test_conductor_has_three_submodes() -> None:
    body = _load("conductor")
    for sub in ["--mode=dispatch", "--mode=monitor", "--mode=integrate"]:
        assert sub in body, f"conductor missing sub-mode: {sub}"


def test_conductor_lists_required_dispatch_md_fields() -> None:
    body = _load("conductor")
    # Each task in dispatch.md must have all six fields.
    for field in ["Territory", "Inputs", "Outputs", "Verification", "Success criteria", "Escalation"]:
        assert field in body, f"conductor missing required dispatch.md field: {field}"


def test_conductor_forbids_writing_engineer_outputs() -> None:
    body = _load("conductor")
    assert "Conductor never writes engineer deliverables" in body or (
        "do not write engineer" in body.lower() or "do **not** write engineer" in body
    )
    # Must list at least three concrete artifacts the conductor cannot write.
    for forbidden in ["architecture.md", "spec.md", "workplan.md"]:
        assert forbidden in body, f"conductor must list {forbidden} as forbidden output"


def test_conductor_documents_convergence_loop_with_iteration_cap() -> None:
    body = _load("conductor")
    assert "Convergence loop" in body
    assert "3 convergence iterations" in body or "3 iteration" in body, (
        "conductor must cap convergence at 3 iterations (borrowed from agent-dispatch)"
    )


def test_conductor_has_adversarial_self_critique() -> None:
    body = _load("conductor")
    assert "Adversarial self-critique" in body


def test_alignment_guard_has_three_status_values() -> None:
    body = _load("alignment-guard")
    for status in ["PASS", "PASS-WITH-NOTES", "BLOCK"]:
        assert status in body, f"alignment-guard must document status: {status}"


def test_alignment_guard_has_two_modes() -> None:
    body = _load("alignment-guard")
    for mode in ["--mode=vision", "--mode=cross-check"]:
        assert mode in body, f"alignment-guard missing mode: {mode}"


def test_alignment_guard_severity_block_mapping_documented() -> None:
    body = _load("alignment-guard")
    assert "HIGH" in body and "MEDIUM" in body and "LOW" in body
    # The mapping must explicitly say HIGH → BLOCK.
    assert "HIGH" in body and "BLOCK" in body
    # Refusal-style language: do not soften HIGH to MEDIUM.
    assert "do not soften" in body.lower() or "Do not soften" in body


def test_alignment_guard_refuses_pass_under_specific_conditions() -> None:
    body = _load("alignment-guard")
    assert "Refusal conditions" in body
    # Allow for markdown bold (`must **not**`) and various phrasings.
    refusal_re = re.compile(r"must\s+(?:\*\*)?not(?:\*\*)?\s+write\s+(?:a\s+)?`?PASS`?", re.IGNORECASE)
    assert refusal_re.search(body), (
        "alignment-guard must contain explicit 'must not write PASS' refusal language"
    )


def test_alignment_guard_has_adversarial_self_critique_with_5_questions() -> None:
    body = _load("alignment-guard")
    assert "Adversarial self-critique" in body
    # The five canonical self-critique prompts.
    for marker in [
        "Verification avoidance",
        "Seduced by the first 80%",
        "Confirmation bias",
        "round a HIGH finding down",
        "three different reviewers",
    ]:
        assert marker in body, f"alignment-guard self-critique missing prompt: {marker}"


def test_orchestrator_agents_reference_workforce_paths_helper() -> None:
    """Each orchestrator must use scripts/workforce_paths.py for canonical write locations
    rather than hardcoding .workforce/ paths."""
    for agent in ORCHESTRATORS:
        body = _load(agent)
        assert "workforce_paths.py" in body or "workforce_paths" in body, (
            f"{agent}: must reference scripts/workforce_paths.py (not hardcoded .workforce/ paths)"
        )


@pytest.mark.parametrize("agent,artifact", [
    ("intent-validator", "intent.md"),
    ("conductor", "dispatch.md"),
    ("conductor", "integration.md"),
    ("alignment-guard", "alignment-report.md"),
])
def test_each_orchestrator_owns_its_declared_artifact(agent: str, artifact: str) -> None:
    body = _load(agent)
    assert artifact in body, f"{agent} must reference its owned artifact {artifact}"
