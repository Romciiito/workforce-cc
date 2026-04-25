#!/usr/bin/env python3
"""
spawn_payload.py — the JSON contract every spawned engineer terminal receives.

This module defines:

  * SpawnPayload  — dataclass describing one engineer dispatch (run id,
    engineer role, inputs, outputs, status file, deadline, retry tier,
    shared locks).
  * StatusRecord — dataclass mirroring the per-engineer status/<engineer>.json
    schema (state, ts, engineer, run_id, reason, artifacts).

Both have round-trip JSON via ``to_json()`` / ``from_json()``. The shape
is enforced by JSON Schema in ``catalogs/schema.json`` ... well, actually
status/<engineer>.json's schema is documented in ``docs/artifact-contract.md``
and asserted by tests.

The dataclasses are deliberately minimal. Any later fields (e.g. cost
estimate, model override, env-var allowlist) can be added with default
values without breaking existing engineers.

Usage from the conductor
------------------------

    from spawn_payload import SpawnPayload, RetryTier, new_run_id

    payload = SpawnPayload(
        run_id=new_run_id(),
        engineer="architect",
        inputs=["intent.md", "spec.md"],
        outputs=["architecture.md"],
        status_file=".workforce/status/architect.json",
        deadline_min=30,
        retry_tier=RetryTier.NARROW,
        shared_locks=[],
    )
    payload.to_json()  # → JSON string

Usage from a spawned engineer
-----------------------------

    payload = SpawnPayload.from_json(sys.stdin.read())
    # ... do the work ...
    StatusRecord(
        state=State.DONE, engineer=payload.engineer, run_id=payload.run_id,
        ts=now_iso(), artifacts=payload.outputs
    ).write(Path(payload.status_file))
"""

from __future__ import annotations

import dataclasses
import enum
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id(now: Optional[datetime] = None) -> str:
    """Return a `.workforce/runs/<ISO_TS>` run id (with `:` replaced for filesystem safety)."""
    ts = now or datetime.now(timezone.utc)
    safe = ts.strftime("%Y-%m-%dT%H-%M-%SZ")
    return f".workforce/runs/{safe}"


class RetryTier(enum.Enum):
    """Escalation tiers (borrowed pattern from agent-dispatch).

    NARROW  — same task, sharper hint. First retry.
    BROAD   — same task, wider context window. Second retry.
    FRESH   — same task, asked from a different angle entirely. Third retry.
    NONE    — no retry context (the initial dispatch).
    """

    NONE = "none"
    NARROW = "narrow"
    BROAD = "broad"
    FRESH = "fresh"

    @classmethod
    def parse(cls, value: Any) -> "RetryTier":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.NONE
        return cls(str(value))


class State(enum.Enum):
    """Engineer status states, written to status/<engineer>.json."""

    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"

    @classmethod
    def parse(cls, value: Any) -> "State":
        if isinstance(value, cls):
            return value
        return cls(str(value))


@dataclasses.dataclass
class SpawnPayload:
    """The contract the conductor passes to every engineer terminal."""

    run_id: str
    engineer: str
    inputs: list[str]
    outputs: list[str]
    status_file: str
    deadline_min: int = 30
    retry_tier: RetryTier = RetryTier.NONE
    shared_locks: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "engineer": self.engineer,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "status_file": self.status_file,
            "deadline_min": int(self.deadline_min),
            "retry_tier": self.retry_tier.value,
            "shared_locks": list(self.shared_locks),
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "SpawnPayload":
        # Defensive: fail loudly on missing required fields rather than silently
        # constructing a partial payload.
        for required in ("run_id", "engineer", "inputs", "outputs", "status_file"):
            if required not in data:
                raise ValueError(f"SpawnPayload: missing required field: {required}")
        return cls(
            run_id=str(data["run_id"]),
            engineer=str(data["engineer"]),
            inputs=list(data["inputs"]),
            outputs=list(data["outputs"]),
            status_file=str(data["status_file"]),
            deadline_min=int(data.get("deadline_min", 30)),
            retry_tier=RetryTier.parse(data.get("retry_tier")),
            shared_locks=list(data.get("shared_locks", [])),
        )

    @classmethod
    def from_json(cls, raw: str) -> "SpawnPayload":
        return cls.from_dict(json.loads(raw))


@dataclasses.dataclass
class StatusRecord:
    """Mirrors `.workforce/status/<engineer>.json`."""

    state: State
    engineer: str
    run_id: str
    ts: str = dataclasses.field(default_factory=now_iso)
    reason: str = ""
    artifacts: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "state": self.state.value,
            "ts": self.ts,
            "engineer": self.engineer,
            "run_id": self.run_id,
        }
        # Required when BLOCKED, optional otherwise.
        if self.reason or self.state is State.BLOCKED:
            out["reason"] = self.reason
        if self.artifacts:
            out["artifacts"] = list(self.artifacts)
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def write(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n")

    @classmethod
    def from_dict(cls, data: dict) -> "StatusRecord":
        for required in ("state", "engineer", "run_id"):
            if required not in data:
                raise ValueError(f"StatusRecord: missing required field: {required}")
        state = State.parse(data["state"])
        if state is State.BLOCKED and "reason" not in data:
            raise ValueError("StatusRecord: state=BLOCKED requires a 'reason' field")
        return cls(
            state=state,
            engineer=str(data["engineer"]),
            run_id=str(data["run_id"]),
            ts=str(data.get("ts", now_iso())),
            reason=str(data.get("reason", "")),
            artifacts=list(data.get("artifacts", [])),
        )

    @classmethod
    def from_json(cls, raw: str) -> "StatusRecord":
        return cls.from_dict(json.loads(raw))

    @classmethod
    def read(cls, path: Path) -> "StatusRecord":
        return cls.from_json(Path(path).read_text())
