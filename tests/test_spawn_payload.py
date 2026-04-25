"""Tests for scripts/spawn_payload.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "spawn_payload.py"


def _load():
    name = "spawn_payload"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_spawn_payload_round_trip() -> None:
    sp = _load()
    p = sp.SpawnPayload(
        run_id=".workforce/runs/2026-04-25T17-00-00Z",
        engineer="architect",
        inputs=["intent.md", "spec.md"],
        outputs=["architecture.md"],
        status_file=".workforce/status/architect.json",
        deadline_min=30,
        retry_tier=sp.RetryTier.NONE,
        shared_locks=[],
    )
    rt = sp.SpawnPayload.from_json(p.to_json())
    assert rt.engineer == p.engineer
    assert rt.inputs == p.inputs
    assert rt.outputs == p.outputs
    assert rt.deadline_min == 30
    assert rt.retry_tier is sp.RetryTier.NONE


def test_spawn_payload_missing_required_field_raises() -> None:
    sp = _load()
    with pytest.raises(ValueError, match="missing required field"):
        sp.SpawnPayload.from_dict({"engineer": "x", "inputs": [], "outputs": [], "status_file": ""})


def test_retry_tier_parses_strings() -> None:
    sp = _load()
    assert sp.RetryTier.parse("narrow") is sp.RetryTier.NARROW
    assert sp.RetryTier.parse("broad") is sp.RetryTier.BROAD
    assert sp.RetryTier.parse("fresh") is sp.RetryTier.FRESH
    assert sp.RetryTier.parse(None) is sp.RetryTier.NONE


def test_status_record_done_round_trip(tmp_path: Path) -> None:
    sp = _load()
    rec = sp.StatusRecord(
        state=sp.State.DONE,
        engineer="architect",
        run_id=".workforce/runs/x",
        artifacts=["architecture.md"],
    )
    path = tmp_path / "architect.json"
    rec.write(path)
    rt = sp.StatusRecord.read(path)
    assert rt.state is sp.State.DONE
    assert rt.engineer == "architect"
    assert rt.artifacts == ["architecture.md"]


def test_status_record_blocked_requires_reason() -> None:
    sp = _load()
    with pytest.raises(ValueError, match="state=BLOCKED requires"):
        sp.StatusRecord.from_dict({
            "state": "BLOCKED",
            "engineer": "x",
            "run_id": "y",
        })


def test_status_record_blocked_with_reason_round_trips(tmp_path: Path) -> None:
    sp = _load()
    rec = sp.StatusRecord(
        state=sp.State.BLOCKED,
        engineer="architect",
        run_id=".workforce/runs/x",
        reason="missing input: spec.md",
    )
    path = tmp_path / "architect.json"
    rec.write(path)
    rt = sp.StatusRecord.read(path)
    assert rt.state is sp.State.BLOCKED
    assert rt.reason == "missing input: spec.md"


def test_new_run_id_is_filesystem_safe() -> None:
    sp = _load()
    rid = sp.new_run_id(now=datetime(2026, 4, 25, 17, 0, 0, tzinfo=timezone.utc))
    assert rid == ".workforce/runs/2026-04-25T17-00-00Z"
    # Round-trip through Path — must not raise on any platform.
    Path(rid)


def test_status_record_state_strings_match_documented_values() -> None:
    """The artifact contract documents these exact strings."""
    sp = _load()
    assert sp.State.RUNNING.value == "RUNNING"
    assert sp.State.BLOCKED.value == "BLOCKED"
    assert sp.State.DONE.value == "DONE"


def test_status_record_includes_all_required_fields_when_serialised() -> None:
    sp = _load()
    rec = sp.StatusRecord(
        state=sp.State.DONE,
        engineer="architect",
        run_id=".workforce/runs/x",
        artifacts=["architecture.md"],
    )
    parsed = json.loads(rec.to_json())
    for required in ("state", "ts", "engineer", "run_id"):
        assert required in parsed, f"missing required field: {required}"
