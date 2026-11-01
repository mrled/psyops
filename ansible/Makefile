.DEFAULT_GOAL := help

UV ?= uv

BETAECAN_ROLE := roles/betaecan
BETAECAN_PYTHON := $(BETAECAN_ROLE)/files $(BETAECAN_ROLE)/tests

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

.PHONY: sync
sync: ## Sync the Python environment from uv.lock (including lint tools)
	$(UV) sync --locked

.PHONY: venv
venv: sync ## Compatibility alias for sync

.PHONY: collections
collections: sync ## Install Galaxy collections (separate from uv dependencies)
	$(UV) run --locked ansible-galaxy collection install -r requirements.yml

.PHONY: install
install: collections ## Install the complete controller environment

# Use real vault credentials when available; otherwise allow offline syntax checks.
.PHONY: lint
lint: install ## Run ansible-lint
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} $(UV) run --locked ansible-lint

.PHONY: lint-betaecan
lint-betaecan: ## Check betaecan role Python lint, formatting, types, and Ansible lint
	$(UV) run --locked ruff check $(BETAECAN_PYTHON)
	$(UV) run --locked ruff format --check $(BETAECAN_PYTHON)
	$(UV) run --locked ty check --error-on-warning $(BETAECAN_PYTHON)
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} $(UV) run --locked ansible-lint $(BETAECAN_ROLE)

.PHONY: format-betaecan
format-betaecan: ## Format the betaecan role Python sources
	$(UV) run --locked ruff format $(BETAECAN_PYTHON)

.PHONY: test-betaecan
test-betaecan: ## Run betaecan cache and backup tests and controller-side smoke tests
	$(UV) run --locked python -m unittest discover -s $(BETAECAN_ROLE)/tests -p 'test_*.py'
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} $(UV) run --locked ansible-playbook -i localhost, $(BETAECAN_ROLE)/tests/render.yml

.PHONY: check-betaecan
check-betaecan: lint-betaecan test-betaecan ## Run all betaecan role checks

.PHONY: lock
lock: ## Refresh uv.lock after editing pyproject.toml
	$(UV) lock
