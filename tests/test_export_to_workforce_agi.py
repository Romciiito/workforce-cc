"""Tests for scripts/export_to_workforce_agi.py.

Regression tests anchored on the post-rebrand layout — these are the
guardrail against the bug that originally shipped (REPO_ROOT pointing
two levels too high).
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_to_workforce_agi.py"


def _load_module():
    name = "export_to_workforce_agi"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, EXPORT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec so @dataclass can resolve cls.__module__ in sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_repo_root_resolves_to_project_root() -> None:
    """parents[1] must land on the repo root, not somewhere above it."""
    module = _load_module()
    assert (module.REPO_ROOT / "scripts" / "export_to_workforce_agi.py").exists()
    assert (module.REPO_ROOT / "agents" / "_shared").is_dir()


def test_agents_root_points_at_actual_agents_dir() -> None:
    module = _load_module()
    assert module.AGENTS_ROOT == module.REPO_ROOT / "agents"
    assert (module.AGENTS_ROOT / "_shared").is_dir()
    assert (module.AGENTS_ROOT / "foundation").is_dir()
    assert (module.AGENTS_ROOT / "workforce").is_dir()


def test_discover_agents_finds_every_pack() -> None:
    module = _load_module()
    agents = module.discover_agents()
    assert len(agents) >= 18  # 7 shared + 7 foundation + 5 workforce at minimum
    packs = {a.pack for a in agents}
    assert packs == {"shared", "foundation", "workforce"}
    # All discovered agents should reference an existing markdown file.
    for agent in agents:
        assert agent.source_path.exists()


def test_dry_run_lists_every_agent_without_writing(tmp_path: Path) -> None:
    out_dir = tmp_path / "skills-out"
    result = subprocess.run(
        [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--dry-run",
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "would export" in result.stdout
    assert not out_dir.exists(), "dry-run must not create the output directory"


def test_export_writes_one_file_per_agent(tmp_path: Path) -> None:
    out_dir = tmp_path / "skills-out"
    result = subprocess.run(
        [sys.executable, str(EXPORT_SCRIPT), "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "exported" in result.stdout
    assert out_dir.is_dir()
    js_files = sorted(out_dir.glob("*.js"))
    assert len(js_files) >= 18

    # Sample one — must be valid-looking JS with the expected exports.
    sample = js_files[0].read_text()
    assert "export default" in sample
    assert "triggerPatterns:" in sample
    assert "async handler(ctx)" in sample
    assert 'createdBy: "manual"' in sample


def test_safe_filename_strips_unsafe_chars() -> None:
    module = _load_module()
    name = module.safe_filename("foundation.weird name/with..stuff")
    assert "/" not in name
    assert name.startswith("foundation-")
    assert name.endswith(".js")


def test_render_skill_escapes_descriptions(tmp_path: Path) -> None:
    """Description text with quotes/newlines must produce valid JS."""
    module = _load_module()
    md = tmp_path / "weird.md"
    md.write_text(
        '---\n'
        'name: weird-agent\n'
        'description: "Has \'single\' and \\"escaped\\" quotes"\n'
        'tools: Read, Write\n'
        'model: sonnet\n'
        '---\n'
        '\n'
        'body\n'
    )
    fm = module.parse_frontmatter(md.read_text())
    assert fm is not None
    agent = module.Agent(
        raw_name="weird-agent",
        skill_name="custom.weird-agent",
        description=fm["description"],
        tools=module.split_tools(fm["tools"]),
        model=fm["model"],
        pack="custom",
        source_path=md,
    )
    rendered = module.render_skill(agent)
    # Valid JSON-quoted description must round-trip.
    desc_match = re.search(r"const DESCRIPTION = (.*?);", rendered, re.DOTALL)
    assert desc_match is not None
    json.loads(desc_match.group(1))  # raises if escaping is broken
