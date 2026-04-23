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
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


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


def main() -> None:
    ap = argparse.ArgumentParser(description="Foundation pipeline runner")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Print ranked track plan")
    p_plan.add_argument("--workplan", default="workplan.md")
    p_plan.add_argument("--max-tracks", type=int, default=4)
    p_plan.add_argument("--project", default="this project")

    p_spawn = sub.add_parser("spawn", help="Spawn one track terminal")
    p_spawn.add_argument("--track", required=True)
    p_spawn.add_argument("--project", default="this project")
    p_spawn.add_argument("--mode", default="auto",
                         choices=["auto", "tmux", "background", "print"])

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


if __name__ == "__main__":
    main()
