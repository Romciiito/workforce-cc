"""Tests for templates/agents/*.md.jinja after Chunk 20.

Six build-agent templates (backend-developer, frontend-developer,
devops-engineer, test-writer, code-reviewer, debugger) now carry the
engineer-with-judgment shape: an adversarial self-critique block + a
read-only-on-non-territory constraint, tailored per role.

Tests run two ways:
1. Static parametrised checks on the .jinja files themselves.
2. Render the templates with a sample context to ensure scaffold.py's
   StrictUndefined doesn't trip on any of the new sections.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates" / "agents"

BUILD_AGENTS = [
    "backend-developer",
    "frontend-developer",
    "devops-engineer",
    "test-writer",
    "code-reviewer",
    "debugger",
]


def _load_template(name: str) -> str:
    return (TEMPLATES_DIR / f"{name}.md.jinja").read_text()


# ── static checks ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent", BUILD_AGENTS)
def test_build_agent_has_adversarial_self_critique(agent: str) -> None:
    body = _load_template(agent)
    assert "## Adversarial self-critique" in body, (
        f"templates/agents/{agent}.md.jinja missing self-critique section"
    )


@pytest.mark.parametrize("agent", BUILD_AGENTS)
def test_build_agent_has_read_only_constraints(agent: str) -> None:
    body = _load_template(agent)
    assert "## Read-only constraints" in body, (
        f"templates/agents/{agent}.md.jinja missing read-only constraints"
    )


@pytest.mark.parametrize("agent", BUILD_AGENTS)
def test_build_agent_self_critique_lists_canonical_traps(agent: str) -> None:
    body = _load_template(agent)
    section = body[body.index("## Adversarial self-critique"):]
    next_heading = section.find("\n## ", 1)
    if next_heading >= 0:
        section = section[:next_heading]
    # Verification avoidance is canonical and required.
    assert "Verification avoidance" in section, (
        f"{agent} self-critique missing trap: Verification avoidance"
    )
    # The 'seduced by 80%' trap may be reframed per role (e.g. debugger uses
    # 'Symptom vs cause' which is the same warning in debugger language).
    has_eighty_or_equivalent = (
        "first 80%" in section
        or "Symptom vs cause" in section
        or "symptom vs cause" in section.lower()
    )
    assert has_eighty_or_equivalent, (
        f"{agent} self-critique missing the 'first 80%' / 'symptom vs cause' trap"
    )


@pytest.mark.parametrize("agent", BUILD_AGENTS)
def test_build_agent_uses_three_X_test(agent: str) -> None:
    body = _load_template(agent)
    has_three_test = any(
        phrase in body.lower()
        for phrase in [
            "three different",
            "three reviewers",
            "three engineers",
            "three architects",
            "three frontend engineers",
            "three backend engineers",
            "three test engineers",
            "three debuggers",
            "three-sre",
            "three sre",
        ]
    )
    assert has_three_test, f"{agent} self-critique should include a three-X-style test"


def test_debugger_includes_execution_trace_section() -> None:
    """debugger gets a special trace template — the bug-fix workflow's five-field shape."""
    body = _load_template("debugger")
    assert "Execution-trace methodology" in body or "execution trace" in body.lower()
    for field in ["Entry point", "Function call chain", "Root cause", "Fix site", "Verification"]:
        assert field in body, f"debugger trace missing field: {field}"


def test_code_reviewer_forbids_state_mutating_git() -> None:
    body = _load_template("code-reviewer")
    section = body[body.index("## Read-only constraints"):]
    assert "git push" in section
    assert "merge" in section.lower()


def test_devops_forbids_terraform_apply_without_authorization() -> None:
    body = _load_template("devops-engineer")
    section = body[body.index("## Read-only constraints"):]
    assert "terraform apply" in section.lower() or "kubectl delete" in section.lower()


def test_test_writer_forbids_modifying_production_source() -> None:
    body = _load_template("test-writer")
    section = body[body.index("## Read-only constraints"):]
    assert "production source" in section.lower() or "must not" in section.lower()


# ── render check (StrictUndefined) ───────────────────────────────────────────


def _render_template(template_name: str, ctx: dict) -> str:
    """Render the template with StrictUndefined, matching scaffold.py's behavior."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined  # type: ignore

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return env.get_template(f"{template_name}.md.jinja").render(**ctx)


_SAMPLE_CTX = {
    "project_name": "Acme",
    "stack": "python-fastapi",
    "env_prefix": "ACME",
    "key_libraries": "FastAPI, SQLAlchemy, asyncpg",
    "db_engine": "PostgreSQL 16",
    "auth_pattern": "JWT bearer + refresh-token rotation",
    "file_structure": "src/api/, src/database/, tests/",
    "security_rules": "All routes require auth except /healthz",
    "critical_rules": "",
}


@pytest.mark.parametrize("agent", BUILD_AGENTS)
def test_template_renders_under_strict_undefined(agent: str) -> None:
    """Chunk 20's new sections must not introduce any unrendered {{ var }}."""
    rendered = _render_template(agent, _SAMPLE_CTX)
    # No leftover Jinja delimiters.
    assert "{{" not in rendered, (
        f"{agent} renders with leftover '{{{{ ... }}}}' — likely an undefined variable"
    )
    assert "{%" not in rendered, f"{agent} has leftover '{{% ... %}}' control structures"


def test_render_includes_project_specific_env_prefix() -> None:
    rendered = _render_template("backend-developer", _SAMPLE_CTX)
    assert "ACME" in rendered, "env_prefix substitution failed"
