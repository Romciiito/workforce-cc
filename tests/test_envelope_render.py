"""Tests for templates/agents/_envelope.md.jinja and pipeline_runner.render_envelope.

The envelope is the standard prompt every dispatched engineer terminal
receives. It must mention the engineer's role, declared inputs/outputs,
status file, deadline, and the adversarial-self-critique step. Tests
assert these structural invariants without locking in exact wording.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PR_SCRIPT = REPO_ROOT / "scripts" / "pipeline_runner.py"
SP_SCRIPT = REPO_ROOT / "scripts" / "spawn_payload.py"
TEMPLATE = REPO_ROOT / "templates" / "agents" / "_envelope.md.jinja"


def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runner():
    return _load_module("pipeline_runner", PR_SCRIPT)


@pytest.fixture
def payload_module():
    return _load_module("spawn_payload", SP_SCRIPT)


def _make_payload(payload_module, **overrides):
    base = dict(
        run_id=".workforce/runs/2026-04-25T17-00-00Z",
        engineer="architect",
        inputs=["intent.md", "spec.md"],
        outputs=["architecture.md"],
        status_file=".workforce/status/architect.json",
        deadline_min=30,
        retry_tier=payload_module.RetryTier.NONE,
        shared_locks=[],
    )
    base.update(overrides)
    return payload_module.SpawnPayload(**base)


def test_envelope_template_file_exists() -> None:
    assert TEMPLATE.exists(), f"envelope template missing at {TEMPLATE}"


def test_render_envelope_includes_engineer_name(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    assert "architect" in out


def test_render_envelope_includes_run_id(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    assert ".workforce/runs/2026-04-25T17-00-00Z" in out


def test_render_envelope_lists_every_input_and_output(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    assert "intent.md" in out
    assert "spec.md" in out
    assert "architecture.md" in out


def test_render_envelope_mentions_status_file(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    assert ".workforce/status/architect.json" in out


def test_render_envelope_mentions_deadline(runner, payload_module) -> None:
    p = _make_payload(payload_module, deadline_min=42)
    out = runner.render_envelope(p, project="Acme")
    assert "42" in out


def test_render_envelope_includes_approach_md_step(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    assert "approach.md" in out
    # Required headings the engineer must use.
    for heading in ["Goal restated", "Plan", "Risks", "Verification"]:
        assert heading in out


def test_render_envelope_includes_adversarial_self_critique(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    assert "Adversarial self-critique" in out


def test_render_envelope_includes_blocked_md_schema(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    assert "BLOCKED.md" in out
    for heading in ["What I tried", "Why blocked", "What unblocks me"]:
        assert heading in out


def test_render_envelope_retry_narrow_includes_narrow_guidance(runner, payload_module) -> None:
    p = _make_payload(payload_module, retry_tier=payload_module.RetryTier.NARROW)
    out = runner.render_envelope(p, project="Acme")
    assert "Narrow retry" in out


def test_render_envelope_retry_broad_includes_broad_guidance(runner, payload_module) -> None:
    p = _make_payload(payload_module, retry_tier=payload_module.RetryTier.BROAD)
    out = runner.render_envelope(p, project="Acme")
    assert "Broad retry" in out


def test_render_envelope_retry_fresh_includes_fresh_guidance(runner, payload_module) -> None:
    p = _make_payload(payload_module, retry_tier=payload_module.RetryTier.FRESH)
    out = runner.render_envelope(p, project="Acme")
    assert "Fresh retry" in out


def test_render_envelope_no_retry_does_not_show_retry_block(runner, payload_module) -> None:
    p = _make_payload(payload_module, retry_tier=payload_module.RetryTier.NONE)
    out = runner.render_envelope(p, project="Acme")
    # The retry guidance lines are gated; with retry_tier=none they shouldn't appear.
    assert "Narrow retry" not in out
    assert "Broad retry" not in out
    assert "Fresh retry" not in out


def test_render_envelope_includes_read_only_constraint(runner, payload_module) -> None:
    p = _make_payload(payload_module)
    out = runner.render_envelope(p, project="Acme")
    for forbidden in ["mkdir", "touch", "rm", "cp", "mv"]:
        assert forbidden in out


def test_render_envelope_falls_back_when_jinja_missing(monkeypatch, runner, payload_module) -> None:
    """Plain-text fallback must produce a usable prompt with all key fields."""
    # Force ImportError by hiding jinja2 from sys.modules during render.
    real_jinja = sys.modules.pop("jinja2", None)
    monkeypatch.setitem(sys.modules, "jinja2", None)  # hides real import
    try:
        p = _make_payload(payload_module)
        out = runner._plaintext_envelope({
            "run_id": p.run_id,
            "engineer": p.engineer,
            "inputs": p.inputs,
            "outputs": p.outputs,
            "status_file": p.status_file,
            "deadline_min": p.deadline_min,
            "retry_tier": p.retry_tier.value,
            "shared_locks": p.shared_locks,
            "project": "Acme",
        })
        assert "architect" in out
        assert "intent.md" in out
        assert "architecture.md" in out
        assert ".workforce/status/architect.json" in out
    finally:
        if real_jinja is not None:
            sys.modules["jinja2"] = real_jinja
