# workforce-cc — common dev tasks.
#
# This Makefile codifies the operations contributors run repeatedly. Targets
# are deliberately thin wrappers around the underlying scripts/install.sh —
# the canonical invocations stay documented in README.md and the relevant
# scripts. The Makefile is convenience, not magic.
#
# Usage:
#   make help            # list targets
#   make test            # run the pytest suite
#   make install-dev     # pip install -e ".[test]"
#   make install         # ./install.sh (claude only, default profile)
#   make install-all     # ./install.sh --harnesses claude,cursor,codex,opencode,gemini
#   make uninstall       # ./install.sh --uninstall
#   make catalog-sync    # populate catalogs/ecc/ from a local upstream clone
#   make catalog-validate
#   make harness-apply   # apply harness adapters to current project
#   make lint            # syntax + shellcheck (if available)
#   make clean           # remove .pytest_cache, __pycache__, .tmp/

.DEFAULT_GOAL := help

PYTHON ?= python3
ROOT_DIR := $(shell pwd)

# ── Help ───────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Tests ──────────────────────────────────────────────────────────────────

.PHONY: test
test: ## Run the full pytest suite
	$(PYTHON) -m pytest

.PHONY: test-fast
test-fast: ## Run pytest with -x (stop on first failure)
	$(PYTHON) -m pytest -x

.PHONY: test-quiet
test-quiet: ## Run pytest with summary only
	$(PYTHON) -m pytest -q

# ── Install / dev setup ────────────────────────────────────────────────────

.PHONY: install-dev
install-dev: ## Install dev dependencies (pip install -e ".[test]")
	$(PYTHON) -m pip install -e ".[test]"

.PHONY: install
install: ## Install workforce-cc with default profile + claude harness
	./install.sh

.PHONY: install-all
install-all: ## Install with all five harnesses (claude, cursor, codex, opencode, gemini)
	./install.sh --harnesses claude,cursor,codex,opencode,gemini

.PHONY: install-minimal
install-minimal: ## Install minimal profile (just /sync)
	./install.sh --profile minimal

.PHONY: install-dry-run
install-dry-run: ## Preview what install.sh would do without writing
	./install.sh --dry-run

.PHONY: uninstall
uninstall: ## Remove everything install.sh wrote
	./install.sh --uninstall

# ── Catalogs ───────────────────────────────────────────────────────────────

.PHONY: catalog-sync
catalog-sync: ## Sync catalogs/ecc/ from a local upstream clone (set ECC_PATH=/path/to/upstream)
ifndef ECC_PATH
	@echo "ERROR: set ECC_PATH=/path/to/everything-claude-code clone"
	@exit 1
endif
	$(PYTHON) scripts/catalog_sync.py --from "$(ECC_PATH)"

.PHONY: catalog-validate
catalog-validate: ## Validate catalogs/<source>/index.json structure + license + bodies
	$(PYTHON) scripts/catalog_check.py validate

.PHONY: catalog-list
catalog-list: ## List all entries in catalogs/ecc/
	$(PYTHON) scripts/catalog_query.py list

.PHONY: catalog-drift
catalog-drift: ## Check catalogs/ecc/ for upstream drift (set ECC_PATH=/path/to/upstream)
ifndef ECC_PATH
	@echo "ERROR: set ECC_PATH=/path/to/everything-claude-code clone"
	@exit 1
endif
	$(PYTHON) scripts/catalog_check.py drift --from "$(ECC_PATH)"

.PHONY: mcp-list
mcp-list: ## List MCP server configs in catalogs/mcp/
	$(PYTHON) scripts/mcp_query.py list

# ── Harness adapters ───────────────────────────────────────────────────────

.PHONY: harness-apply
harness-apply: ## Apply harnesses listed in ~/.workforce-harnesses to current project
	@for h in $$(cat ~/.workforce-harnesses 2>/dev/null | tr ',' ' '); do \
		echo ">>> Applying harness: $$h"; \
		$(PYTHON) scripts/harness_install.py \
			--harness "$$h" \
			--project-dir . \
			--project-name "$$(basename $(ROOT_DIR))" \
			--stack python-fastapi; \
	done

.PHONY: harness-apply-all
harness-apply-all: ## Apply ALL five harness adapters to current project
	@for h in claude cursor codex opencode gemini; do \
		echo ">>> Applying harness: $$h"; \
		$(PYTHON) scripts/harness_install.py \
			--harness "$$h" \
			--project-dir . \
			--project-name "$$(basename $(ROOT_DIR))" \
			--stack python-fastapi; \
	done

# ── Lint / static checks ───────────────────────────────────────────────────

.PHONY: lint
lint: lint-bash lint-py ## Run all linters

.PHONY: lint-bash
lint-bash: ## Syntax-check + shellcheck (if available) install.sh + hooks/*.sh
	@bash -n install.sh && echo "  install.sh: bash syntax OK"
	@for f in hooks/*.sh; do bash -n "$$f" && echo "  $$f: bash syntax OK"; done
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck install.sh hooks/*.sh && echo "  shellcheck: clean"; \
	else \
		echo "  shellcheck: not installed (CI runs it)"; \
	fi

.PHONY: lint-py
lint-py: ## Smoke-check Python scripts compile
	@for f in scripts/*.py; do \
		$(PYTHON) -m py_compile "$$f" && echo "  $$f: compiles"; \
	done

# ── Cleanup ────────────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove .pytest_cache, __pycache__, .tmp/, and editable install metadata
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .tmp/

# ── Status / info ──────────────────────────────────────────────────────────

.PHONY: status
status: ## Show repo status (git, tests, harness beacon, profile beacon)
	@echo "=== git status ==="
	@git status --short
	@echo ""
	@echo "=== beacons ==="
	@if [[ -f ~/.foundation-path ]]; then \
		echo "  ~/.foundation-path     → $$(cat ~/.foundation-path)"; \
	else \
		echo "  ~/.foundation-path     → (not installed)"; \
	fi
	@if [[ -f ~/.workforce-profile ]]; then \
		echo "  ~/.workforce-profile   → $$(cat ~/.workforce-profile)"; \
	else \
		echo "  ~/.workforce-profile   → (legacy install or not installed)"; \
	fi
	@if [[ -f ~/.workforce-harnesses ]]; then \
		echo "  ~/.workforce-harnesses → $$(cat ~/.workforce-harnesses)"; \
	else \
		echo "  ~/.workforce-harnesses → (default: claude)"; \
	fi
	@echo ""
	@echo "=== test count ==="
	@$(PYTHON) -m pytest --collect-only -q 2>/dev/null | tail -1 || echo "  (run `make test` to verify)"
