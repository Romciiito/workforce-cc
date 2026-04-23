#!/usr/bin/env python3
"""
telemetry.py — optional JSONL logger agents can append to.

A project opts in by creating ``.foundation-memory/`` at its root. If that
directory does not exist, this script is a no-op. Agents call it from their
Task Protocol step 8 with a short structured message.

Format:
  <project>/.foundation-memory/telemetry.jsonl   (one JSON object per line)

Not a metrics store — just a durable breadcrumb trail for later review.

Usage:
  python3 telemetry.py --project-dir . \\
      --agent backend-developer \\
      --event task-complete \\
      --task "REQ-F-012 — create /users endpoint" \\
      --duration-sec 420
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Foundation telemetry logger")
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--agent", required=True, help="Agent name (e.g. backend-developer)")
    ap.add_argument("--event", required=True,
                    choices=["task-start", "task-complete", "task-failed",
                             "agent-spawn", "phase-gate-passed",
                             "decision-recorded"])
    ap.add_argument("--task", default="", help="Task description (free text)")
    ap.add_argument("--duration-sec", type=float, default=None)
    ap.add_argument("--note", default="", help="Free-form note (≤ 200 chars)")
    args = ap.parse_args()

    root = Path(args.project_dir).resolve()
    mem_dir = root / ".foundation-memory"

    # Opt-in: silently no-op if not enabled
    if not mem_dir.exists():
        sys.exit(0)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": args.agent,
        "event": args.event,
        "task": args.task[:240],
        "note": args.note[:200],
    }
    if args.duration_sec is not None:
        record["duration_sec"] = round(float(args.duration_sec), 2)

    log_path = mem_dir / "telemetry.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
