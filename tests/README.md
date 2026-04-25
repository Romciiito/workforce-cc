# Tests

Pytest suite covering the deterministic helpers in `scripts/` and the
`install.sh` installer.

## Run

```bash
pip install pytest jinja2
pytest
```

## What's covered

| File | Covers |
|------|--------|
| `test_scaffold.py` | Stack scaffolding, env_prefix derivation, CI generation, idempotence (does not overwrite workplan), settings.local.json content |
| `test_health_score.py` | All five score dimensions, generic-agent detection, no-git fallback, defensive parsing of git output |
| `test_pipeline_runner.py` | Track classification, current-phase detection, ranking + clipping, CLI smoke |
| `test_export_to_workforce_agi.py` | Repo-root resolution (regression for the post-rebrand path bug), dry-run, full export, JS escaping |
| `test_suggest_skills.py` | Catalog reads, installed-vs-missing detection, unknown stacks, missing skills directory |
| `test_telemetry.py` | Opt-in no-op, JSONL append, multi-line append, invalid event rejection |
| `test_install_script.py` | End-to-end install/uninstall against fake `$HOME`, agent collision check |

## Adding a new test

1. Drop a `test_*.py` file in this directory.
2. If your test needs a temporary git repo with a real author config, pull
   in the `git_repo` fixture from `conftest.py` (use `make_commit(repo, msg)`
   to add commits).
3. Tests should not depend on the host's `~/.claude/` — the install
   suite uses `tmp_path` as a fake `$HOME` for that reason.

## CI

`.github/workflows/test.yml` runs the suite on Python 3.11/3.12/3.13 and
shellchecks `install.sh` on every push and pull request.
