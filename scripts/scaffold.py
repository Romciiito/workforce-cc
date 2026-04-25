#!/usr/bin/env python3
"""
Foundation scaffold generator.
Renders Jinja2 templates + copies stack structure into the target project directory.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    print("ERROR: jinja2 not installed. Run: pip install jinja2", file=sys.stderr)
    sys.exit(1)


def derive_env_prefix(project_name: str) -> str:
    """Derive an UPPER_SNAKE_CASE env-var prefix from the project name.

    Many templates reference ``{{ env_prefix }}`` (e.g. APP_DATABASE_URL).
    We normalise the project name into a safe identifier and fall back to
    ``APP`` whenever the name has no usable characters.
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_").upper()
    if not cleaned or not cleaned[0].isalpha():
        return "APP"
    return cleaned


STACK_PERMISSIONS = {
    "python-fastapi": [
        "Bash(python3:*)", "Bash(pip:*)", "Bash(uv:*)", "Bash(alembic:*)",
        "Bash(uvicorn:*)", "Bash(pytest:*)", "Bash(git:*)", "Bash(docker:*)",
        "Bash(docker compose:*)", "Bash(psql:*)",
    ],
    "nextjs-fullstack": [
        "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(git:*)",
        "Bash(docker:*)", "Bash(docker compose:*)",
    ],
    "python-fastapi-nextjs": [
        "Bash(python3:*)", "Bash(pip:*)", "Bash(uv:*)", "Bash(alembic:*)",
        "Bash(uvicorn:*)", "Bash(pytest:*)", "Bash(npm:*)", "Bash(npx:*)",
        "Bash(node:*)", "Bash(git:*)", "Bash(docker:*)", "Bash(docker compose:*)",
        "Bash(psql:*)",
    ],
    "python-cli": [
        "Bash(python3:*)", "Bash(pip:*)", "Bash(uv:*)", "Bash(pytest:*)",
        "Bash(git:*)",
    ],
    "fullstack-desktop": [
        "Bash(python3:*)", "Bash(pip:*)", "Bash(uv:*)", "Bash(alembic:*)",
        "Bash(uvicorn:*)", "Bash(pytest:*)", "Bash(npm:*)", "Bash(npx:*)",
        "Bash(cargo:*)", "Bash(git:*)", "Bash(docker:*)", "Bash(docker compose:*)",
        "Bash(psql:*)", "Bash(redis-cli:*)",
    ],
    "microservices": [
        "Bash(python3:*)", "Bash(pip:*)", "Bash(uv:*)", "Bash(alembic:*)",
        "Bash(uvicorn:*)", "Bash(pytest:*)", "Bash(git:*)", "Bash(docker:*)",
        "Bash(docker compose:*)", "Bash(psql:*)", "Bash(redis-cli:*)",
    ],
    "react-native": [
        "Bash(python3:*)", "Bash(pip:*)", "Bash(uv:*)", "Bash(alembic:*)",
        "Bash(uvicorn:*)", "Bash(pytest:*)", "Bash(npm:*)", "Bash(npx:*)",
        "Bash(expo:*)", "Bash(npx react-native:*)", "Bash(git:*)",
        "Bash(docker:*)", "Bash(docker compose:*)", "Bash(psql:*)",
    ],
}


def render_template(env: Environment, template_name: str, ctx: dict) -> str:
    try:
        tmpl = env.get_template(template_name)
        return tmpl.render(**ctx)
    except Exception as e:
        print(f"  WARNING: Could not render {template_name}: {e}", file=sys.stderr)
        return ""


def render_string(text: str, ctx: dict) -> str:
    """Render Jinja2 expressions inside a plain string (used for structure.json file content)."""
    try:
        from jinja2 import Template
        return Template(text).render(**ctx)
    except Exception:
        return text


def create_stack_structure(project_dir: Path, templates_dir: Path, stack: str, ctx: dict) -> None:
    structure_file = templates_dir / "stacks" / stack / "structure.json"
    if not structure_file.exists():
        print(f"  WARNING: No structure.json for stack '{stack}' — skipping source dirs")
        return

    with open(structure_file) as f:
        structure = json.load(f)

    for d in structure.get("dirs", []):
        (project_dir / d).mkdir(parents=True, exist_ok=True)
        print(f"  + {d}/")

    for filepath, content in structure.get("files", {}).items():
        target = project_dir / filepath
        target.parent.mkdir(parents=True, exist_ok=True)
        rendered = render_string(content, ctx)
        if not target.exists():
            target.write_text(rendered)
            print(f"  + {filepath}")


def copy_agents(project_dir: Path, foundation_root: Path) -> None:
    agents_src = foundation_root / "agents"
    agents_dst = project_dir / ".claude" / "agents"
    agents_dst.mkdir(parents=True, exist_ok=True)
    if agents_src.exists():
        for agent_file in agents_src.glob("*.md"):
            dst = agents_dst / agent_file.name
            if not dst.exists():
                shutil.copy2(agent_file, dst)
                print(f"  + .claude/agents/{agent_file.name}")


def write_settings(project_dir: Path, stack: str) -> None:
    perms = STACK_PERMISSIONS.get(stack, STACK_PERMISSIONS["python-fastapi"])
    settings = {"permissions": {"allow": perms}}
    settings_path = project_dir / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if not settings_path.exists():
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        print("  + .claude/settings.local.json")


def copy_workflows(project_dir: Path, templates_dir: Path) -> None:
    workflows_src = templates_dir / "workflows"
    workflows_dst = project_dir / "workflows"
    workflows_dst.mkdir(parents=True, exist_ok=True)
    if workflows_src.exists():
        for wf in workflows_src.glob("*.md"):
            dst = workflows_dst / wf.name
            if not dst.exists():
                shutil.copy2(wf, dst)
                print(f"  + workflows/{wf.name}")


STACK_CI_TEMPLATES = {
    "python-fastapi": ["ci-python.yml.jinja"],
    "nextjs-fullstack": ["ci-nextjs.yml.jinja"],
    "python-fastapi-nextjs": ["ci-python.yml.jinja", "ci-nextjs.yml.jinja"],
    "python-cli": ["ci-python.yml.jinja"],
    "fullstack-desktop": ["ci-python.yml.jinja", "ci-nextjs.yml.jinja", "ci-tauri.yml.jinja"],
    "microservices": ["ci-python.yml.jinja"],
    "react-native": ["ci-python.yml.jinja"],
}


def generate_ci(project_dir: Path, templates_dir: Path, stack: str, ctx: dict) -> None:
    ci_templates_dir = templates_dir / "github-actions"
    if not ci_templates_dir.exists():
        print("  WARNING: No github-actions templates dir found — skipping CI generation")
        return

    workflows_dir = project_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(ci_templates_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )

    # Always add deploy-staging.yml
    template_names = STACK_CI_TEMPLATES.get(stack, ["ci-python.yml.jinja"]) + ["deploy-staging.yml.jinja"]

    for tmpl_name in template_names:
        output_name = tmpl_name.replace(".jinja", "")
        target = workflows_dir / output_name
        if not target.exists():
            try:
                tmpl = env.get_template(tmpl_name)
                content = tmpl.render(**ctx)
                target.write_text(content)
                print(f"  + .github/workflows/{output_name}")
            except Exception as e:
                print(f"  WARNING: Could not render {tmpl_name}: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Foundation scaffold generator")
    parser.add_argument("--project-dir", required=True, help="Target project directory")
    parser.add_argument("--stack", required=True, help="Stack name (e.g. python-fastapi)")
    parser.add_argument("--project-name", required=True, help="Project name")
    parser.add_argument("--templates-dir", required=True, help="Path to foundation/templates/")
    parser.add_argument("--description", default="", help="One-line project description")
    parser.add_argument("--rules-file", default="", help="Path to claude-rules.md from workplan-builder")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    templates_dir = Path(args.templates_dir).resolve()
    foundation_root = templates_dir.parent

    if not templates_dir.exists():
        print(f"ERROR: templates dir not found: {templates_dir}", file=sys.stderr)
        sys.exit(1)

    # Load project-specific rules from workplan-builder output (if present)
    critical_rules = ""
    rules_path = Path(args.rules_file) if args.rules_file else project_dir / "claude-rules.md"
    if rules_path.exists():
        critical_rules = rules_path.read_text().strip()

    print(f"\nScaffolding '{args.project_name}' ({args.stack}) into {project_dir}\n")

    ctx = {
        "project_name": args.project_name,
        "stack": args.stack,
        "description": args.description,
        "critical_rules": critical_rules,
        "env_prefix": derive_env_prefix(args.project_name),
    }

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )

    # CLAUDE.md is always written/overwritten — it is the canonical project identity
    # file and must reflect the full pipeline output including project-specific rules.
    claude_target = project_dir / "CLAUDE.md"
    content = render_template(env, "CLAUDE.md.jinja", ctx)
    if content:
        claude_target.write_text(content)
        action = "↺" if (project_dir / "CLAUDE.md").exists() else "+"
        print(f"  {action} CLAUDE.md")

    # workplan.md — only if not already written by workplan-builder agent
    for tmpl_name, output_path in [
        ("workplan.md.jinja", "workplan.md"),
    ]:
        target = project_dir / output_path
        if not target.exists():
            content = render_template(env, tmpl_name, ctx)
            if content:
                target.write_text(content)
                print(f"  + {output_path}")

    # decisions.md — always create if not present (implementation journal for build agents)
    decisions_target = project_dir / "decisions.md"
    if not decisions_target.exists():
        content = render_template(env, "decisions.md.jinja", ctx)
        if content:
            decisions_target.write_text(content)
            print("  + decisions.md")

    # Render docs/claude/
    docs_dir = project_dir / "docs" / "claude"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for tmpl_name, output_name in [
        ("docs/architecture.md.jinja", "architecture.md"),
        ("docs/development.md.jinja", "development.md"),
        ("docs/design-decisions.md.jinja", "design-decisions.md"),
        ("docs/env-vars.md.jinja", "env-vars.md"),
    ]:
        target = docs_dir / output_name
        if not target.exists():
            content = render_template(env, tmpl_name, ctx)
            if content:
                target.write_text(content)
                print(f"  + docs/claude/{output_name}")

    # tools/ directory (WAT Layer 3)
    tools_dir = project_dir / "tools"
    tools_dir.mkdir(exist_ok=True)
    gitkeep = tools_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
        print("  + tools/.gitkeep")

    # workflows/ from templates
    copy_workflows(project_dir, templates_dir)

    # Stack-specific dirs + files
    create_stack_structure(project_dir, templates_dir, args.stack, ctx)

    # .github/workflows/ CI/CD
    generate_ci(project_dir, templates_dir, args.stack, ctx)

    # .claude/agents/
    copy_agents(project_dir, foundation_root)

    # .claude/settings.local.json
    write_settings(project_dir, args.stack)

    print(f"\nScaffold complete. Review workplan.md and fill in .env values.\n")


if __name__ == "__main__":
    main()
