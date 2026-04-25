"""Tests for the permission_mode field added to SpawnPayload (Chunk 27).

Pattern from leaked Claude Code source (multi-mode permission resolution
— default/plan/auto/bypass). Fresh implementation; semantics defined in
scripts/spawn_payload.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SP_SCRIPT = REPO_ROOT / "scripts" / "spawn_payload.py"
PR_SCRIPT = REPO_ROOT / "scripts" / "pipeline_runner.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sp():
    return _load("spawn_payload", SP_SCRIPT)


@pytest.fixture
def runner():
    return _load("pipeline_runner", PR_SCRIPT)


# ── Enum semantics ──────────────────────────────────────────────────────────


def test_permission_mode_has_four_values(sp) -> None:
    assert {m.value for m in sp.PermissionMode} == {"default", "plan", "auto", "bypass"}


def test_permission_mode_parse_handles_strings(sp) -> None:
    assert sp.PermissionMode.parse("default") is sp.PermissionMode.DEFAULT
    assert sp.PermissionMode.parse("plan") is sp.PermissionMode.PLAN
    assert sp.PermissionMode.parse("auto") is sp.PermissionMode.AUTO
    assert sp.PermissionMode.parse("bypass") is sp.PermissionMode.BYPASS


def test_permission_mode_parse_none_returns_default(sp) -> None:
    assert sp.PermissionMode.parse(None) is sp.PermissionMode.DEFAULT


def test_permission_mode_parse_unknown_raises(sp) -> None:
    with pytest.raises(ValueError):
        sp.PermissionMode.parse("yolo")


# ── SpawnPayload integration ─────────────────────────────────────────────────


def _payload(sp, **overrides):
    base = dict(
        run_id=".workforce/runs/x",
        engineer="architect",
        inputs=["intent.md"],
        outputs=["architecture.md"],
        status_file=".workforce/status/architect.json",
    )
    base.update(overrides)
    return sp.SpawnPayload(**base)


def test_default_payload_has_default_permission(sp) -> None:
    p = _payload(sp)
    assert p.permission_mode is sp.PermissionMode.DEFAULT


def test_payload_round_trip_preserves_permission_mode(sp) -> None:
    for mode in [sp.PermissionMode.DEFAULT, sp.PermissionMode.PLAN, sp.PermissionMode.AUTO, sp.PermissionMode.BYPASS]:
        p = _payload(sp, permission_mode=mode)
        rt = sp.SpawnPayload.from_json(p.to_json())
        assert rt.permission_mode is mode, f"round-trip failed for {mode}"


def test_payload_serialises_permission_mode_as_string(sp) -> None:
    p = _payload(sp, permission_mode=sp.PermissionMode.AUTO)
    payload_dict = json.loads(p.to_json())
    assert payload_dict["permission_mode"] == "auto"


def test_old_json_without_permission_mode_loads_with_default(sp) -> None:
    """Backward compat: payloads written before Chunk 27 still parse."""
    legacy = json.dumps({
        "run_id": ".workforce/runs/x",
        "engineer": "architect",
        "inputs": ["intent.md"],
        "outputs": ["architecture.md"],
        "status_file": ".workforce/status/architect.json",
        "deadline_min": 30,
        "retry_tier": "none",
        "shared_locks": [],
    })
    parsed = sp.SpawnPayload.from_json(legacy)
    assert parsed.permission_mode is sp.PermissionMode.DEFAULT


# ── Envelope rendering ───────────────────────────────────────────────────────


def test_envelope_default_mode_says_safe_one(runner, sp) -> None:
    p = _payload(sp, permission_mode=sp.PermissionMode.DEFAULT)
    out = runner.render_envelope(p, project="Acme")
    assert "default" in out
    # The default-mode body emphasises 'safe'.
    assert "safe one" in out.lower() or "Ask before" in out


def test_envelope_plan_mode_forbids_execution(runner, sp) -> None:
    p = _payload(sp, permission_mode=sp.PermissionMode.PLAN)
    out = runner.render_envelope(p, project="Acme")
    assert "plan-only" in out.lower() or "must not execute" in out.lower()


def test_envelope_auto_mode_skips_confirmations(runner, sp) -> None:
    p = _payload(sp, permission_mode=sp.PermissionMode.AUTO)
    out = runner.render_envelope(p, project="Acme")
    assert "autonomous" in out.lower() or "without asking" in out.lower()


def test_envelope_bypass_mode_documents_excursions(runner, sp) -> None:
    p = _payload(sp, permission_mode=sp.PermissionMode.BYPASS)
    out = runner.render_envelope(p, project="Acme")
    assert "bypass" in out.lower()
    assert "highest" in out.lower() or "outside the envelope" in out.lower()
    # Must explicitly require documentation of each excursion.
    assert "approach.md" in out


def test_envelope_each_mode_renders_only_its_own_text(runner, sp) -> None:
    """plan-mode rendering should not mention 'autonomous'; auto-mode shouldn't
    mention 'plan-only', etc. Catches a copy-paste bug where the if/elif chain
    drops through."""
    plan_out = runner.render_envelope(_payload(sp, permission_mode=sp.PermissionMode.PLAN), project="Acme")
    assert "plan-only" in plan_out.lower()
    assert "autonomous" not in plan_out.lower() or plan_out.lower().count("autonomous") <= 0
    assert "highest trust" not in plan_out.lower()

    auto_out = runner.render_envelope(_payload(sp, permission_mode=sp.PermissionMode.AUTO), project="Acme")
    assert "autonomous" in auto_out.lower()
    assert "plan-only" not in auto_out.lower()
    assert "highest trust" not in auto_out.lower()

    bypass_out = runner.render_envelope(_payload(sp, permission_mode=sp.PermissionMode.BYPASS), project="Acme")
    assert "bypass" in bypass_out.lower()
    assert "plan-only" not in bypass_out.lower()


def test_plaintext_fallback_includes_permission_mode(runner, sp) -> None:
    """The bash-3.2-compatible plaintext fallback must show permission_mode."""
    out = runner._plaintext_envelope({
        "run_id": ".workforce/runs/x",
        "engineer": "architect",
        "inputs": ["intent.md"],
        "outputs": ["architecture.md"],
        "status_file": ".workforce/status/architect.json",
        "deadline_min": 30,
        "retry_tier": "none",
        "shared_locks": [],
        "permission_mode": "auto",
        "project": "Acme",
    })
    assert "auto" in out.lower()
    assert "Permission mode" in out
