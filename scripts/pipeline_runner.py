#!/usr/bin/env python3
"""
pipeline_runner.py — helper for Foundation/Workforce orchestrators.

Two responsibilities:

  1. ``plan`` — given a workplan.md and a desired concurrency, print an
     ordered list of (track_name, opening_prompt) tuples the orchestrator
     should spawn as separate terminals.

  2. ``spawn`` — take one (track_name, opening_prompt) pair and start it
     in the best available execution channel (tmux > non-interactive
     ``claude --print`` > print instructions), without blocking the caller.

Design: the orchestrator agent still makes the decisions; this script only
turns those decisions into concrete shell commands, so the agent doesn't
re-implement tmux detection / OS shelling in every session.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

# Late-bind the new spawn-payload module so the legacy CLI (plan/spawn) keeps
# working even if spawn_payload.py is missing. The new subcommands import
# lazily inside their handlers.
_SCRIPT_DIR = Path(__file__).resolve().parent


TRACK_PATTERNS = {
    "backend":  ("backend", "api", "service", "db", "migration", "schema"),
    "frontend": ("frontend", "ui", "page", "component", "client"),
    "devops":   ("devops", "ci", "deploy", "docker", "infra", "pipeline"),
    "testing":  ("test", "qa", "e2e", "coverage"),
    "worker":   ("worker", "queue", "job", "cron", "schedule"),
    "mobile":   ("mobile", "ios", "android", "react native", "expo"),
}


def read_current_phase(workplan: Path) -> List[str]:
    """Return the list of ``- [ ]`` task lines from the first in-progress phase."""
    if not workplan.exists():
        sys.exit(f"workplan.md not found at {workplan}")

    phase_lines: List[str] = []
    in_current = False
    found_open_task = False

    for line in workplan.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Phase"):
            if in_current and found_open_task:
                break
            in_current = True
            phase_lines = [line]
            found_open_task = False
            continue
        if in_current:
            phase_lines.append(line)
            if line.lstrip().startswith("- [ ]"):
                found_open_task = True
    if not found_open_task:
        return []
    return phase_lines


def classify(line: str) -> str:
    lower = line.lower()
    for track, keywords in TRACK_PATTERNS.items():
        if any(k in lower for k in keywords):
            return track
    return "backend"


def plan(workplan: Path, max_tracks: int) -> List[Tuple[str, int]]:
    phase = read_current_phase(workplan)
    counts: dict[str, int] = {}
    for line in phase:
        stripped = line.lstrip()
        if stripped.startswith("- [ ]"):
            track = classify(stripped)
            counts[track] = counts.get(track, 0) + 1
    # Rank tracks by incomplete task count, clip to max_tracks.
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:max_tracks]
    return ranked


def opening_prompt(track: str, project: str) -> str:
    return (
        f"You are the {track} agent for {project}. "
        f"Read workplan.md. Pick up all {track} tasks in the current phase. "
        "Update workplan.md checkboxes as you complete each task. "
        "When every task you own is done, report back via decisions.md."
    )


def has_tmux_session() -> bool:
    if not shutil.which("tmux"):
        return False
    return "TMUX" in os.environ


def spawn_tmux(track: str, prompt: str, cwd: Path) -> None:
    session = "foundation"
    # ensure session exists
    r = subprocess.run(["tmux", "has-session", "-t", session],
                       capture_output=True)
    if r.returncode != 0:
        subprocess.run(["tmux", "new-session", "-d", "-s", session,
                        "-n", "orchestrator"])
    win = f"track-{track}"
    subprocess.run(["tmux", "new-window", "-t", session, "-n", win])
    subprocess.run(["tmux", "send-keys", "-t", f"{session}:{win}",
                    f"cd {cwd} && claude", "Enter"])
    # brief pause so Claude is ready before keystrokes
    subprocess.run(["sleep", "2"])
    subprocess.run(["tmux", "send-keys", "-t", f"{session}:{win}",
                    prompt, "Enter"])
    print(f"  + tmux window '{win}' ({session}:{win})")


def spawn_background_print(track: str, prompt: str, cwd: Path) -> None:
    log_dir = cwd / ".tmp"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"track-{track}.log"
    # shell-out with nohup so the caller doesn't block
    cmd = ["nohup", "claude", "--print", prompt]
    with log_path.open("w") as f:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=f,
                                start_new_session=True)
    print(f"  + background '{track}' — log: {log_path} — pid: {proc.pid}")


def spawn_instructions(track: str, prompt: str, cwd: Path) -> None:
    print(f"  Open a new terminal, then run:")
    print(f"    cd {cwd} && claude")
    print(f"  When Claude is ready, paste:")
    print(f"    {prompt}")


# ──────────────────────────────────────────────────────────────────────────────
# New subcommands (Chunk 4): envelope rendering, status polling, spawn-from-payload.
#
# These are additive. The legacy `plan` and `spawn` subcommands above are
# preserved unchanged so existing tests keep passing. A future chunk
# (Chunk 11) flips the default in `spawn` to render the envelope; until
# then the envelope is opt-in via `--prompt-style envelope`.
# ──────────────────────────────────────────────────────────────────────────────


def _load_spawn_payload_module():
    """Import scripts/spawn_payload.py without polluting the global namespace.

    Done lazily so the legacy CLI keeps working even if spawn_payload.py is
    deleted (it isn't, but the import was layered to make Chunk 4 strictly
    additive against the existing test suite).
    """
    import importlib.util

    sp_path = _SCRIPT_DIR / "spawn_payload.py"
    if not sp_path.exists():
        sys.exit(f"ERROR: scripts/spawn_payload.py missing at {sp_path}")
    spec = importlib.util.spec_from_file_location("spawn_payload", sp_path)
    if "spawn_payload" in sys.modules:
        return sys.modules["spawn_payload"]
    module = importlib.util.module_from_spec(spec)
    sys.modules["spawn_payload"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def render_envelope(payload, project: Optional[str] = None) -> str:
    """Render templates/agents/_envelope.md.jinja for the given SpawnPayload.

    Used by the conductor and by `spawn` when invoked with --prompt-style=envelope.
    Returns the rendered prompt as a string. Falls back to a plain-text
    envelope (no Jinja) if jinja2 isn't installed — the new architecture
    should not hard-require jinja2 at every spawn.
    """
    repo_root = _SCRIPT_DIR.parent
    template_path = repo_root / "templates" / "agents" / "_envelope.md.jinja"
    if not template_path.exists():
        sys.exit(f"ERROR: envelope template missing at {template_path}")

    ctx = {
        "run_id": payload.run_id,
        "engineer": payload.engineer,
        "inputs": list(payload.inputs),
        "outputs": list(payload.outputs),
        "status_file": payload.status_file,
        "deadline_min": int(payload.deadline_min),
        "retry_tier": payload.retry_tier.value,
        "shared_locks": list(payload.shared_locks),
        "project": project or "this project",
    }

    try:
        from jinja2 import Environment, FileSystemLoader, StrictUndefined  # type: ignore
        env = Environment(
            loader=FileSystemLoader(str(template_path.parent)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        return env.get_template(template_path.name).render(**ctx)
    except ImportError:
        # Plaintext fallback. Useful for environments where jinja2 isn't
        # installed and we still want the engineer to receive a usable prompt.
        return _plaintext_envelope(ctx)


def _plaintext_envelope(ctx: dict) -> str:
    """Plain-text fallback when jinja2 is unavailable. Functionally equivalent."""
    inputs_lines = "\n".join(f"  - {f}" for f in ctx["inputs"]) or "  - (none)"
    outputs_lines = "\n".join(f"  - {f}" for f in ctx["outputs"]) or "  - (none)"
    locks_lines = "\n".join(f"  - {f}" for f in ctx["shared_locks"]) or "  - (none)"
    return (
        f"You are the {ctx['engineer']} engineer for {ctx['project']}.\n\n"
        f"Run id:       {ctx['run_id']}\n"
        f"Retry tier:   {ctx['retry_tier']}\n"
        f"Deadline:     {ctx['deadline_min']} minutes\n\n"
        f"Inputs:\n{inputs_lines}\n\n"
        f"Outputs (your declared territory):\n{outputs_lines}\n\n"
        f"Shared locks (read-only):\n{locks_lines}\n\n"
        f"Status file: {ctx['status_file']}\n\n"
        "Procedure:\n"
        f"  1. Read every input.\n"
        f"  2. Write {ctx['run_id']}/{ctx['engineer']}/approach.md before producing outputs.\n"
        "  3. Execute. Stay inside your declared outputs.\n"
        "  4. Verify. Run the verification commands you committed to in approach.md.\n"
        "  5. Write the status file with state DONE | BLOCKED.\n\n"
        "If you cannot complete: write BLOCKED.md and exit cleanly.\n"
    )


# Status polling helpers ──────────────────────────────────────────────────────


def list_status_files(project_dir: Path) -> List[Path]:
    """Return all .workforce/status/*.json files in chronological order (mtime)."""
    status_dir = project_dir / ".workforce" / "status"
    if not status_dir.is_dir():
        return []
    return sorted(status_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)


def read_status(project_dir: Path) -> List[dict]:
    """Read every status file and return parsed records (oldest first)."""
    out: List[dict] = []
    for path in list_status_files(project_dir):
        try:
            out.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def status_table(records: List[dict]) -> str:
    """Pretty-print status records as a fixed-width table."""
    if not records:
        return "No engineers have reported status yet."
    rows = []
    rows.append(f"{'ENGINEER':<24} {'STATE':<10} {'TS':<25} REASON / ARTIFACTS")
    rows.append("─" * 80)
    for r in records:
        eng = (r.get("engineer") or "?")[:24]
        state = (r.get("state") or "?")[:10]
        ts = (r.get("ts") or "")[:25]
        if r.get("state") == "BLOCKED":
            tail = (r.get("reason") or "")[:30]
        else:
            arts = r.get("artifacts") or []
            tail = ", ".join(arts)[:30]
        rows.append(f"{eng:<24} {state:<10} {ts:<25} {tail}")
    return "\n".join(rows)


def all_done(records: List[dict], expected_engineers: Optional[List[str]] = None) -> bool:
    """Return True iff every expected engineer reported DONE.

    If `expected_engineers` is None, returns True iff every reporting engineer
    is DONE (no expectations about who should report).
    """
    if expected_engineers is not None:
        seen_done = {r["engineer"] for r in records if r.get("state") == "DONE"}
        return all(e in seen_done for e in expected_engineers)
    if not records:
        return False
    return all(r.get("state") == "DONE" for r in records)


def blocked_engineers(records: List[dict]) -> List[dict]:
    return [r for r in records if r.get("state") == "BLOCKED"]


def cmd_status(project_dir: Path, expected: Optional[List[str]], as_json: bool) -> int:
    records = read_status(project_dir)
    if as_json:
        payload = {
            "records": records,
            "all_done": all_done(records, expected),
            "blocked": [r["engineer"] for r in blocked_engineers(records)],
        }
        print(json.dumps(payload, indent=2))
        return 0
    print(status_table(records))
    print()
    if blocked_engineers(records):
        print("BLOCKED engineers:")
        for r in blocked_engineers(records):
            print(f"  - {r['engineer']}: {r.get('reason', '(no reason given)')}")
        return 1
    if expected and all_done(records, expected):
        print(f"WAVE COMPLETE — all {len(expected)} expected engineers reported DONE.")
        return 0
    if not expected and all_done(records):
        print("All reporting engineers reported DONE.")
        return 0
    print("Wave still in progress.")
    return 0


def cmd_blocked_scan(project_dir: Path, as_json: bool) -> int:
    """Walk runs/<ts>/<engineer>/BLOCKED.md and surface them."""
    runs_dir = project_dir / ".workforce" / "runs"
    blocked_files = sorted(runs_dir.rglob("BLOCKED.md")) if runs_dir.is_dir() else []
    if as_json:
        payload = [
            {"path": str(p.relative_to(project_dir)), "body": p.read_text()}
            for p in blocked_files
        ]
        print(json.dumps(payload, indent=2))
    else:
        if not blocked_files:
            print("No BLOCKED.md files found.")
            return 0
        for p in blocked_files:
            print(f"━━━ {p.relative_to(project_dir)} ━━━")
            print(p.read_text())
            print()
    return 0 if not blocked_files else 1


def cmd_render_envelope(payload_path: Path, project: Optional[str]) -> int:
    """Render the envelope for a saved SpawnPayload JSON file."""
    sp = _load_spawn_payload_module()
    payload = sp.SpawnPayload.from_json(Path(payload_path).read_text())
    print(render_envelope(payload, project=project))
    return 0


def synthesise_payload_for_track(track: str, project: str):
    """Build a sensible SpawnPayload from just a track name + project label.

    Used by `spawn` when invoked with the envelope prompt-style. Keeps the
    legacy track-based UX (one-flag spawn) but produces an envelope-shaped
    prompt for the engineer terminal. For richer dispatches, the conductor
    writes a full payload JSON and uses `spawn-payload` instead.
    """
    sp = _load_spawn_payload_module()
    run_id = sp.new_run_id()
    return sp.SpawnPayload(
        run_id=run_id,
        engineer=track,
        # Sensible defaults: every track-based engineer reads the workplan
        # and writes against decisions.md. Specific in/out lists belong in
        # a dispatch.md, not a one-shot track spawn.
        inputs=["workplan.md"],
        outputs=["decisions.md"],
        status_file=f".workforce/status/{track}.json",
        deadline_min=30,
        retry_tier=sp.RetryTier.NONE,
        shared_locks=["workplan.md"],
    )


def cmd_spawn_payload(payload_path: Path, mode: str, project: Optional[str]) -> int:
    """Spawn an engineer terminal using a SpawnPayload JSON file (envelope-rendered)."""
    sp = _load_spawn_payload_module()
    payload = sp.SpawnPayload.from_json(Path(payload_path).read_text())
    prompt = render_envelope(payload, project=project)
    cwd = Path.cwd()

    track = payload.engineer
    if mode == "auto":
        mode = "tmux" if has_tmux_session() else "background"
    if mode == "tmux" and not has_tmux_session():
        print("tmux not available / not inside a tmux session — falling back to background.")
        mode = "background"
    if mode == "tmux":
        spawn_tmux(track, prompt, cwd)
    elif mode == "background":
        spawn_background_print(track, prompt, cwd)
    else:
        spawn_instructions(track, prompt, cwd)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Foundation pipeline runner")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Print ranked track plan (legacy)")
    p_plan.add_argument("--workplan", default="workplan.md")
    p_plan.add_argument("--max-tracks", type=int, default=4)
    p_plan.add_argument("--project", default="this project")

    p_spawn = sub.add_parser(
        "spawn",
        help="Spawn one engineer terminal (envelope-by-default; --legacy-prompt for the old one-liner)",
    )
    p_spawn.add_argument("--track", required=True)
    p_spawn.add_argument("--project", default="this project")
    p_spawn.add_argument("--mode", default="auto",
                         choices=["auto", "tmux", "background", "print"])
    p_spawn.add_argument(
        "--prompt-style",
        default="envelope",
        choices=["envelope", "legacy"],
        help="envelope (default): render templates/agents/_envelope.md.jinja with a synthesised payload. "
             "legacy: the pre-Chunk-11 one-liner from opening_prompt().",
    )
    p_spawn.add_argument(
        "--legacy-prompt",
        action="store_true",
        help="Shorthand for --prompt-style=legacy.",
    )

    # New subcommands (Chunk 4) — additive; do not change legacy behavior.
    p_render = sub.add_parser(
        "render-envelope",
        help="Render the engineer task envelope from a SpawnPayload JSON file",
    )
    p_render.add_argument("--payload", required=True, type=Path)
    p_render.add_argument("--project", default=None)

    p_spawn_payload = sub.add_parser(
        "spawn-payload",
        help="Spawn an engineer terminal with the envelope-rendered prompt",
    )
    p_spawn_payload.add_argument("--payload", required=True, type=Path)
    p_spawn_payload.add_argument("--project", default=None)
    p_spawn_payload.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "tmux", "background", "print"],
    )

    p_status = sub.add_parser(
        "status",
        help="Read .workforce/status/*.json and print a status table",
    )
    p_status.add_argument("--project-dir", type=Path, default=Path.cwd())
    p_status.add_argument(
        "--expect",
        default="",
        help="Comma-separated list of expected engineer names. If passed, exits 0 only when each is DONE.",
    )
    p_status.add_argument("--json", dest="as_json", action="store_true")

    p_blocked = sub.add_parser(
        "blocked-scan",
        help="Walk .workforce/runs/<ts>/*/BLOCKED.md and surface their bodies",
    )
    p_blocked.add_argument("--project-dir", type=Path, default=Path.cwd())
    p_blocked.add_argument("--json", dest="as_json", action="store_true")

    args = ap.parse_args()

    if args.cmd == "plan":
        ranked = plan(Path(args.workplan), args.max_tracks)
        if not ranked:
            print("No parallelizable work in current phase.")
            return
        print("RANKED TRACKS (open tasks — highest first):")
        for track, n in ranked:
            print(f"  {track:<10} {n} tasks   →   "
                  f"prompt: {opening_prompt(track, args.project)}")

    elif args.cmd == "spawn":
        cwd = Path.cwd()
        # Resolve prompt style. --legacy-prompt is shorthand for the explicit form.
        prompt_style = "legacy" if args.legacy_prompt else args.prompt_style
        if prompt_style == "envelope":
            payload = synthesise_payload_for_track(args.track, args.project)
            prompt = render_envelope(payload, project=args.project)
        else:
            prompt = opening_prompt(args.track, args.project)
        mode = args.mode
        if mode == "auto":
            mode = "tmux" if has_tmux_session() else "background"
        if mode == "tmux":
            if not has_tmux_session():
                print("tmux not available / not inside a tmux session — "
                      "falling back to background mode.")
                mode = "background"
        if mode == "tmux":
            spawn_tmux(args.track, prompt, cwd)
        elif mode == "background":
            spawn_background_print(args.track, prompt, cwd)
        else:
            spawn_instructions(args.track, prompt, cwd)

    elif args.cmd == "render-envelope":
        sys.exit(cmd_render_envelope(args.payload, args.project))

    elif args.cmd == "spawn-payload":
        sys.exit(cmd_spawn_payload(args.payload, args.mode, args.project))

    elif args.cmd == "status":
        expect = [e.strip() for e in args.expect.split(",") if e.strip()] or None
        sys.exit(cmd_status(args.project_dir, expect, args.as_json))

    elif args.cmd == "blocked-scan":
        sys.exit(cmd_blocked_scan(args.project_dir, args.as_json))


if __name__ == "__main__":
    main()
